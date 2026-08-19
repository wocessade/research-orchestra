"""Orchestra Broker dispatcher：轮询任务文件 → 执行 → 状态入库 → 可选上报。"""
from __future__ import annotations

import json
import logging
import signal
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

def _archive_task_file(f: Path, tasks_dir: Path) -> None:
    """终态任务文件移入 tasks/archive/，避免队列目录无限积压。"""
    archive = tasks_dir / "archive"
    archive.mkdir(exist_ok=True)
    f.rename(archive / f.name)

def one_cycle(cfg: dict, conn, run=None, check_net_fn=None) -> dict:
    """单轮：注册新任务 → 重排队失败任务 → 执行 queued → 终态任务文件归档。
    run/check_net_fn 供测试注入。"""
    run = run or executor.run_task
    check_net_fn = check_net_fn or executor.check_net
    tasks_dir = Path(cfg["tasks_dir"])
    max_attempts = int(cfg.get("max_attempts", 2))

    specs: dict[str, taskfile.TaskSpec] = {}
    for f in sorted(tasks_dir.glob("T-*.md")):
        try:
            spec = taskfile.parse_taskfile(f)
        except ValueError as e:
            # 解析失败按 .bad 归档（哨兵审计 INFO-4：否则每 30s 刷一条错误日志）
            archive = tasks_dir / "archive"
            archive.mkdir(exist_ok=True)
            log.error("非法任务文件 %s 已按 .bad 归档: %s", f.name, e)
            f.rename(archive / (f.name + ".bad"))
            continue
        specs[spec.slug] = spec
        db.register_task(conn, spec.slug, spec.net, spec.result_dir)
        # 已终态的历史任务文件（如升级前的 done）同样归档，防积压
        row = db.get_task(conn, spec.slug)
        if row and (row[1] == "done" or (row[1] == "failed" and row[2] >= max_attempts)):
            _archive_task_file(f, tasks_dir)

    db.requeue_failed(conn, max_attempts)

    executed, skipped_net = [], []
    for slug, _st, _a, net_req, _e in db.list_tasks(conn, "queued"):
        spec = specs.get(slug)
        if spec is None:
            # 任务文件被删：claim 递增 attempts 后置 failed，避免 attempts=0 被
            # requeue_failed 永久循环（哨兵审计发现）
            if db.claim_task(conn, slug):
                db.finish_task(conn, slug, "failed", "task file missing")
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
        if row and (row[1] == "done" or (row[1] == "failed" and row[2] >= max_attempts)):
            f = tasks_dir / f"{slug}.md"
            if f.exists():
                _archive_task_file(f, tasks_dir)
    return {"executed": executed, "skipped_net": skipped_net}

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    signal.signal(signal.SIGTERM, lambda *a: (_ for _ in ()).throw(SystemExit(0)))
    cfg = load_config()
    conn = db.init_db(cfg["db_path"])
    poll = float(cfg.get("poll_interval", 30))
    log.info("broker started (poll=%ss, db=%s)", poll, cfg["db_path"])
    while True:
        try:
            # 每轮先回收上轮异常遗留的 running → failed（审计 CONCERN-4：
            # one_cycle 同步执行，正常时轮初必无 running；有则必是崩溃残留）
            n = db.recover_running(conn)
            if n:
                log.info("recovered %d running task(s) -> failed", n)
            one_cycle(cfg, conn)
            report_status(cfg, conn)
        except Exception:
            log.exception("cycle error")
        time.sleep(poll)

if __name__ == "__main__":
    main()
