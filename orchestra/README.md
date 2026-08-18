# Orchestra — 科研编排调度中枢

以 Claude Code 为核心的科研-实验-论文框架（总 spec：docs/superpowers/specs/2026-08-18-research-orchestra-design.md）。

| 目录 | 用途 |
|------|------|
| config/rules.yaml | 执行器分派规则与降级顺序（CC 分派前读） |
| config/model-routing.md | 模型调度策略表（用户维护，系统只读） |
| tasks/ | 任务文件总线：CC 写入，Broker 轮询 |
| results/ | 执行器产出（attempt-N/ 目录：stdout/stderr/state.json） |
| logs/ | broker.log 与执行日志 |
| reports/ | CC 复查记录 |
| done/ | 归档 |
| scripts/ | sync_push.sh / sync_pull.sh（scp 同步） |
| broker/ | Broker 源码（stdlib only，scp 部署到 4B） |

任务文件格式（严格）：

    # T-YYYYMMDD-<slug>
    executor: dsh | shell
    net: required | optional
    result: T-YYYYMMDD-<slug>
    timeout: <秒，默认 3600>
    ---
    <执行体：dsh 任务的 prompt 全文，或 shell 任务的命令>

快速流程：写 tasks/T-*.md → sync_push.sh → 等 Broker 执行 → sync_pull.sh → CC 复查写 reports/ → 归档 done/。
