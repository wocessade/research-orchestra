"""Orchestra Broker dispatcher：轮询任务文件 → 执行 → 状态入库 → 可选上报。"""
from __future__ import annotations

import json
import logging
import signal
import threading
import time
import urllib.request
from pathlib import Path

import db
import executor
import taskfile

log = logging.getLogger("dispatcher")

def load_config(path: str = "config.json") -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))

def read_host_stats() -> dict | None:
    """读本机负载/内存（供墨水屏设备区显示）：/proc/loadavg 首列 load1（1 位小数）、
    /proc/meminfo MemTotal/MemAvailable → mem_pct（整数百分比）。
    文件不存在或解析失败 → None（非 Linux 或容器内无 /proc）。"""
    try:
        load1 = float(Path("/proc/loadavg").read_text().split()[0])
        mem_lines = Path("/proc/meminfo").read_text().splitlines()
        total = next(int(l.split()[1]) for l in mem_lines if l.startswith("MemTotal:"))
        avail = next(int(l.split()[1]) for l in mem_lines if l.startswith("MemAvailable:"))
    except (OSError, ValueError, StopIteration):
        return None
    return {"load1": round(load1, 1), "mem_pct": round(100 * (1 - avail / total))}

def build_payload(conn, host_stats: dict | None = None) -> dict:
    """report_status 的 payload 纯函数：4 字段 + recent_tasks（最多 5 条，ts 降序）
    + host 负载/内存。host_stats 注入（测试用假值）；None 时读本机 /proc，
    读不到则不包含 host 键（旧 monitor / 无 /proc 环境向后兼容）。"""
    done = db.list_tasks(conn, "done")
    queued = len(db.list_tasks(conn, "queued"))
    running = len(db.list_tasks(conn, "running"))
    payload = {
        "broker_health": "ok",
        "queue_len": queued + running,
        "active_tasks": running,
        "blocked_tasks": len(db.list_tasks(conn, "blocked")),
        "invalid_tasks": len(db.list_tasks(conn, "invalid")),
        "last_task": done[-1][0] if done else None,
        "recent_tasks": [
            {"slug": slug, "status": status, "ts": ts}
            for slug, status, ts in db.list_recent(conn)
        ],
    }
    stats = host_stats if host_stats is not None else read_host_stats()
    if stats is not None:
        payload["host"] = stats
    return payload

def report_status(cfg: dict, conn) -> None:
    api = cfg.get("api_url")
    if not api:
        return
    payload = build_payload(conn)
    req = urllib.request.Request(
        api.rstrip("/") + "/api/orchestra",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Monitor-Token": cfg.get("monitor_token", ""),
        },
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:  # 上报失败不影响主循环
        log.warning("status report failed: %s", e)

def _reporter_loop(cfg: dict, stop_event: threading.Event) -> None:
    """独立上报线程（D15）：自持 SQLite 连接（WAL 支持与主循环并发读），
    每 poll_interval 秒上报一次；主循环同步执行长任务期间上报不中断。
    stop_event 置位（SIGTERM）后退出当前等待并结束循环（连接随线程关闭）。"""
    conn = db.init_db(cfg["db_path"])
    poll = float(cfg.get("poll_interval", 30))
    try:
        while not stop_event.is_set():
            try:
                report_status(cfg, conn)
            except Exception:  # 上报异常不影响上报节奏，下个周期重试
                log.exception("reporter loop error")
            stop_event.wait(poll)
    finally:
        conn.close()

def _rename_overwrite(src: Path, dst: Path) -> None:
    """rename 撞名幂等化：POSIX rename 覆盖；Windows 上目标已存在抛 FileExistsError，
    先删同名再重试。归档目标同名时内容为同一任务文件的旧副本，覆盖即幂等，
    不能抛穿 one_cycle（M-12）。"""
    try:
        src.rename(dst)
    except FileExistsError:
        dst.unlink()
        src.rename(dst)


def _archive_task_file(f: Path, tasks_dir: Path) -> None:
    """终态任务文件移入 tasks/archive/，避免队列目录无限积压。"""
    archive = tasks_dir / "archive"
    archive.mkdir(exist_ok=True)
    _rename_overwrite(f, archive / f.name)


def _archive_by_slug(slug: str, tasks_dir: Path) -> None:
    path = tasks_dir / f"{slug}.md"
    if path.exists():
        _archive_task_file(path, tasks_dir)


def _find_dependency_cycles(specs: dict[str, taskfile.TaskSpec]) -> set[str]:
    """返回当前活动任务图中位于依赖环上的 slug。"""
    state: dict[str, int] = {}
    stack: list[str] = []
    cyclic: set[str] = set()

    def visit(slug: str) -> None:
        state[slug] = 1
        stack.append(slug)
        for dependency in specs[slug].depends_on:
            if dependency not in specs:
                continue
            if state.get(dependency, 0) == 0:
                visit(dependency)
            elif state.get(dependency) == 1:
                start = stack.index(dependency)
                cyclic.update(stack[start:])
        stack.pop()
        state[slug] = 2

    for slug in specs:
        if state.get(slug, 0) == 0:
            visit(slug)
    return cyclic


def _is_terminal(row: tuple | None, max_attempts: int) -> bool:
    if row is None:
        return False
    return row[1] in ("done", "blocked", "invalid") or (
        row[1] == "failed" and row[2] >= max_attempts
    )

def one_cycle(cfg: dict, conn, run=None, check_net_fn=None) -> dict:
    """单轮：注册新任务 → 重排队失败任务 → 执行 queued → 终态任务文件归档。
    run/check_net_fn 供测试注入。"""
    run = run or executor.run_task
    check_net_fn = check_net_fn or executor.check_net
    tasks_dir = Path(cfg["tasks_dir"])
    max_attempts = int(cfg.get("max_attempts", 2))

    specs: dict[str, taskfile.TaskSpec] = {}
    for f in sorted(tasks_dir.glob("T-*.md")):
        parts = f.name.split("-")
        if len(parts) >= 5 and parts[2:4] == ["nightly", "radar"]:
            marker = tasks_dir / f".radar-inject-{parts[1]}"
            if marker.exists():
                continue
        try:
            spec = taskfile.parse_taskfile(f)
        except ValueError as e:
            # 解析失败按 .bad 归档（哨兵审计 INFO-4：否则每 30s 刷一条错误日志）
            archive = tasks_dir / "archive"
            archive.mkdir(exist_ok=True)
            log.error("非法任务文件 %s 已按 .bad 归档: %s", f.name, e)
            _rename_overwrite(f, archive / (f.name + ".bad"))
            continue
        specs[spec.slug] = spec
        db.register_task(conn, spec.slug, spec.net, spec.result_dir)
        # 已终态的历史任务文件（如升级前的 done / 重放同名任务卡）同样归档，
        # 防积压；必须留日志说明归档原因，不能静默吞掉（M-12）
        row = db.get_task(conn, spec.slug)
        if _is_terminal(row, max_attempts):
            log.info("归档 %s：终态重放（status=%s），不再执行", f.name, row[1])
            _archive_task_file(f, tasks_dir)

    db.requeue_failed(conn, max_attempts)

    invalid_dependencies = []
    cycle_slugs = _find_dependency_cycles(specs)
    for slug, spec in specs.items():
        current = db.get_task(conn, slug)
        if current is not None and current[1] != "queued":
            continue
        missing = [
            dependency for dependency in spec.depends_on
            if dependency not in specs and db.get_task(conn, dependency) is None
        ]
        reasons = []
        if slug in cycle_slugs:
            reasons.append("dependency cycle")
        if missing:
            reasons.append("missing dependencies: " + ", ".join(missing))
        if reasons:
            error = "; ".join(reasons)
            db.finish_task(conn, slug, "invalid", error)
            invalid_dependencies.append({"slug": slug, "error": error})
            _archive_by_slug(slug, tasks_dir)

    executed, skipped_net, waiting_dependencies, blocked_dependencies = [], [], [], []
    for slug, _st, _a, net_req, _e in db.list_tasks(conn, "queued"):
        spec = specs.get(slug)
        if spec is None:
            # 任务文件被删：claim 递增 attempts 后置 failed，避免 attempts=0 被
            # requeue_failed 永久循环（哨兵审计发现）
            if db.claim_task(conn, slug):
                db.finish_task(conn, slug, "failed", "task file missing")
            continue
        incomplete = []
        blockers = []
        for dependency in spec.depends_on:
            row = db.get_task(conn, dependency)
            if row is None:
                blockers.append(f"{dependency}: missing")
            elif row[1] in ("blocked", "invalid"):
                blockers.append(f"{dependency}: {row[1]}")
            elif row[1] == "failed" and row[2] >= max_attempts:
                blockers.append(f"{dependency}: failed after {row[2]} attempts")
            elif row[1] != "done":
                incomplete.append(dependency)
        if blockers:
            error = "blocked by dependencies: " + "; ".join(blockers)
            db.finish_task(conn, slug, "blocked", error)
            blocked_dependencies.append({"slug": slug, "error": error})
            _archive_by_slug(slug, tasks_dir)
            continue
        if incomplete:
            waiting_dependencies.append({
                "slug": slug,
                "dependencies": incomplete,
            })
            continue
        if net_req == "required" and not check_net_fn():
            skipped_net.append(slug)
            continue
        if not db.claim_task(conn, slug):
            continue
        try:
            status, error = run(spec, str(tasks_dir), cfg["results_dir"],
                                dsh_profile=cfg.get("dsh_profile", "headless"))
        except Exception as e:
            # 执行器异常也必须落库，否则任务永久卡 running 直到重启（哨兵审计 CONCERN-4）
            log.exception("task %s executor crashed", slug)
            status, error = "failed", f"executor exception: {e}"
        db.finish_task(conn, slug, status, error)
        executed.append(slug)
        log.info("task %s -> %s (%s)", slug, status, error or "-")
        row = db.get_task(conn, slug)
        # 终态（done，或 attempts 用尽的 failed）→ 归档任务文件
        if _is_terminal(row, max_attempts):
            f = tasks_dir / f"{slug}.md"
            if f.exists():
                _archive_task_file(f, tasks_dir)
    return {
        "executed": executed,
        "skipped_net": skipped_net,
        "waiting_dependencies": waiting_dependencies,
        "blocked_dependencies": blocked_dependencies,
        "invalid_dependencies": invalid_dependencies,
    }

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    cfg = load_config()
    conn = db.init_db(cfg["db_path"])
    poll = float(cfg.get("poll_interval", 30))
    stop_event = threading.Event()

    def _on_sigterm(*_a):
        stop_event.set()  # 通知 reporter 线程退出
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _on_sigterm)
    log.info("broker started (poll=%ss, db=%s)", poll, cfg["db_path"])
    # D15：独立 reporter 线程——主循环 one_cycle 同步执行长任务期间（可分钟级）
    # 无上报会造成面板 90s 阈值误判「Broker 离线」；reporter 自持 WAL 连接按
    # poll 周期持续上报，与主循环解耦。主循环不再调用 report_status（防双报）。
    # recover_running 仍在主循环内先于任务执行；reporter 首帧即使抢先上报
    # 崩溃残留，30s 后自动纠正。
    threading.Thread(target=_reporter_loop, args=(cfg, stop_event),
                     name="reporter", daemon=True).start()
    log.info("reporter thread started (interval=%ss)", poll)
    while True:
        try:
            # 每轮先回收上轮异常遗留的 running → failed（审计 CONCERN-4：
            # one_cycle 同步执行，正常时轮初必无 running；有则必是崩溃残留）
            n = db.recover_running(conn)
            if n:
                log.info("recovered %d running task(s) -> failed", n)
            one_cycle(cfg, conn)
        except Exception:
            log.exception("cycle error")
        time.sleep(poll)

if __name__ == "__main__":
    main()
