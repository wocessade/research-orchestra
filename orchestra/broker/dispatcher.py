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

def report_status(cfg: dict, conn) -> None:
    api = cfg.get("api_url")
    if not api:
        return
    done = db.list_tasks(conn, "done")
    queued = len(db.list_tasks(conn, "queued"))
    running = len(db.list_tasks(conn, "running"))
    payload = {
        "broker_health": "ok",
        "queue_len": queued + running,
        "active_tasks": running,
        "last_task": done[-1][0] if done else None,
    }
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

def one_cycle(cfg: dict, conn, run=None, check_net_fn=None) -> dict:
    """单轮：注册新任务 → 重排队失败任务 → 执行 queued。run/check_net_fn 供测试注入。"""
    run = run or executor.run_task
    check_net_fn = check_net_fn or executor.check_net
    tasks_dir = Path(cfg["tasks_dir"])
    max_attempts = int(cfg.get("max_attempts", 2))

    specs: dict[str, taskfile.TaskSpec] = {}
    for f in sorted(tasks_dir.glob("T-*.md")):
        try:
            spec = taskfile.parse_taskfile(f)
        except ValueError as e:
            log.error("跳过非法任务文件: %s", e)
            continue
        specs[spec.slug] = spec
        db.register_task(conn, spec.slug, spec.net, spec.result_dir)

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
        status, error = run(spec, str(tasks_dir), cfg["results_dir"],
                            dsh_profile=cfg.get("dsh_profile", "headless"))
        db.finish_task(conn, slug, status, error)
        executed.append(slug)
        log.info("task %s -> %s (%s)", slug, status, error or "-")
    return {"executed": executed, "skipped_net": skipped_net}

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    signal.signal(signal.SIGTERM, lambda *a: (_ for _ in ()).throw(SystemExit(0)))
    cfg = load_config()
    conn = db.init_db(cfg["db_path"])
    n = db.recover_running(conn)
    if n:
        log.info("recovered %d running task(s) -> failed", n)
    poll = float(cfg.get("poll_interval", 30))
    log.info("broker started (poll=%ss, db=%s)", poll, cfg["db_path"])
    while True:
        try:
            one_cycle(cfg, conn)
            report_status(cfg, conn)
        except Exception:
            log.exception("cycle error")
        time.sleep(poll)

if __name__ == "__main__":
    main()
