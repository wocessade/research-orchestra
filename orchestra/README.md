# Orchestra — 科研编排调度中枢

以 Claude Code 为核心的科研-实验-论文框架（总 spec：docs/superpowers/specs/2026-08-18-research-orchestra-design.md）。

| 目录 | 用途 |
|------|------|
| config/rules.yaml | 人工约定（代码不读）；Broker 以任务卡与 broker/config.json 为准 |
| config/model-routing.json | 模型路由表（用户维护、系统只读，见「模型路由表」节） |
| config/skills.json | 外部 Skill 路径、入口、契约文件与锁定摘要 |
| tasks/ | 任务文件总线：CC 写入，Broker 轮询 |
| results/ | 执行器产出（attempt-N/ 目录：stdout/stderr/state.json） |
| logs/ | broker.log 与执行日志 |
| reports/ | CC 复查记录 |
| scripts/ | sync_push/pull、deploy_broker、backup_to_nas、`orchestra_check.py`（测试 + skill digest + tracked-ignored） |
| broker/ | Broker 源码（stdlib only，scp 部署到 RK3528） |
| templates/ | dsh 任务模板（nightly-radar 等，inject_daily 填充日期后注入） |

任务文件格式（严格）：

    # T-YYYYMMDD-<slug>
    executor: dsh | shell
    net: required | optional
    result: T-YYYYMMDD-<slug>
    timeout: <秒，1–86400，默认 3600>
    depends_on: T-...[, T-...]  # 可选；依赖完成前不执行、不消耗 attempt
    mode: execute | explore | decide | audit | brief  # 可选，默认 execute
    detail: brief | standard | deep                   # 可选，默认 standard
    required_outputs: result.json[, report.txt]       # 可选；必须存在且非空
    json_outputs: result.json                         # 可选；必须是合法 JSON
    validation_output: validation.json                # 可选；要求 {"status":"passed"}
    model: flash | pro       # dsh 模型档位（可选，见「模型路由表」节）
    ---
    <执行体：dsh 任务的 prompt 全文，或 shell 任务的命令>

本机解析（`broker/taskfile.py`）拒绝未知字段、重复 key、timeout 非 1–86400、`model` 非 `flash|pro`。**RK3528 在役副本须下次 `deploy_broker.sh` 才对齐。**

快速流程：写 tasks/T-*.md → sync_push.sh → 等 Broker 执行 → sync_pull.sh → CC 复查写 reports/。任务终态后 broker 自动把任务文件移入 tasks/archive/（本地 tasks/ 经 sync_pull 同步该状态）。

`mode` 和 `detail` 由 dsh 执行器转换为统一行为前缀：探索任务先发散再收敛，决策任务比较取舍，审查任务要求证据与反证，简报任务主动去重；shell 任务只记录这两个字段，不改变命令执行。

进程退出码 `0` 只代表执行器正常结束；声明了输出契约的任务还必须通过文件存在性、非空、JSON 解析和 `validation_output.status` 校验，才能标记为 `done`。校验结果写入每次 attempt 的 `state.json.output_validation`。

## 外部 Skill 契约

- `config/skills.json` 是外部 Skill 的唯一清单，记录路径、是否必需、调用入口、输入输出契约和 `expected_digest`
- `scripts/check_skills.py` 对 `contract_files` 计算 SHA-256；状态包括 `ok`、`missing`、`incomplete`、`unlocked`、`drifted`
- manifest 采用严格 schema：未知/缺失字段、重复 Skill ID、逃逸路径、入口未纳入契约文件、非法摘要均拒绝
- 检查：`python scripts/check_skills.py --strict`
- 首次确认版本后锁定：`python scripts/check_skills.py --lock-current --strict`
- 只有 Skill 已安装且入口完整时才会写入摘要；外部 Skill 更新后必须重新审查再锁定，不能静默接受漂移
- `run_card.py ingest` 在调用外部 engine 前强制读取该 manifest；必需 Skill 处于 missing/incomplete/unlocked/drifted 或 manifest 非法时均 `HARD` 退出。仓库不负责下载或安装外部 Skill

## 夜间文献雷达（mission 023）

- 每日 23:30 `orchestra-timer.timer` 触发 `inject_daily.sh`，幂等注入四个依赖任务：`10-fetch → 20-rank → 30-render → 40-notify`；同日期以原子 marker 目录互斥，marker owner 记录 host、boot ID、PID 和 Linux `/proc/<pid>/stat` starttime，Linux 上按 PID+starttime 防止 PID 复用误判，无 `/proc` 的测试/非 Linux 环境保守回退为 PID 存活检查；失败只清理自己的 marker，崩溃遗留 marker 可由下一次注入安全接管并补齐缺失阶段
- `fetch` 只抓取并去重，产出 `papers_all.json`；`rank` 只评分，产出带证据、反证、不确定项和置信度的 `scored_papers.json`，validator 按 `arxiv_id` 核对每篇上游 `title/url/categories/abstract` 原始字段完全一致，并核对条目数、完整 arXiv ID 集合及原始文件 SHA-256
- `render` 确定性校验分数后生成 `digest.json` / `digest.txt` / `top5.json` / `validation.json`，Top 5 包含综合、探索和多样性槽位
- `notify` 是纯 shell 阶段，只在 `validation.status=passed` 后发送邮件；持久 `sending/sent/not_sent/unknown` 状态与锁文件提供 at-most-once 语义，发送器明确报告 `not_sent` 时允许任务重试，结果不明确时仍拒绝自动重发
- 阶段间通过 `depends_on` 串联：上游失败时下游等待且不消耗 attempt，各阶段可独立重试
- 周日 04:00 housekeeping：清理 14 天前 dsh 会话、磁盘余量告警（邮件）；日志 logrotate 7 天
- **权威裁决（2026-08-20 固化）**：评分以雷达五维（topic/method/applied/archival，novelty 控探索槽位）为**唯一权威**，声望/引用/来源不进总分；`nature-literature-pipeline` 的六维评分（含 Source Quality 声望维度）在 orchestra 语境**弃用**，仅保留其 PDF 精读与 Zotero/Obsidian 归档增量；其雷达/邮件功能不重复实现（兼容度分析 `docs/reports/2026-08-skills-orchestra-compat.md`）
- **日报→精读→周报闭环（2026-08-20 固化）**：晨间日报 top5 → 按需 `nature-reader` 精读（CC 侧中英对照 reader，产物入 Obsidian 笔记）→ `nature-weekly-review` 周报聚合组会材料；交互型 skill 不进 dsh（headless 无交互 UI）

## 实验管线闭环（mission 025 / 总 spec §6.2）

- 实验卡（`.research/experiments/EXP-*/card.md`）新增 `## Commands` 段：无头可执行命令、`# arm: <id>` 臂标记、数值只来自 run artifact（最后一条命令产 metrics.json，符合 metrics.schema.json）
- 闭环：卡 → CC 审查 → Broker 入队 → shell/dsh 无头执行 → metrics.json → `run_card.py ingest` 入账（engine ingest_run.py）→ CC 复查写 reports/（数字只引用 ingest artifact 路径）
- `scripts/run_card.py commands <card.md> [--arm ID]` 提取卡命令生成任务文件；`scripts/run_card.py ingest <metrics.json> --card <card.md> --research-root <root> [--skills-manifest config/skills.json]` 入账（先过严格 Skill 契约门禁，engine 三脚本只被调用不改动）
- 验收 demo：`orchestra/demo/`（EXP-001 对照实验，研究根隔离在 demo/.research/）；验收报告 `reports/2026-08-experiment-loop-acceptance.md`

## 仪表盘链路（mission 026 / 总 spec §6.4）

- 数据流：RK3528 Broker reporter 线程每 30s `POST /api/orchestra`（recent_tasks + host 负载/内存）→ 核桃派 usage-monitor 融合面板（状态条 + 最近任务 + 设备区 + DeepSeek/天气行）；Windows sync 脚本上报 last_sync
- 鉴权：`X-Monitor-Token`（盒子与核桃派间流转；核桃派 override.conf / RK3528 config.json，均不入库）
- 面板刷新纪律：内容变化才全刷；last_report 时间戳与负载抖动只走局刷（D10/D14）
- 验收：`reports/2026-08-dashboard-acceptance.md`（reviewed: ok，含 D15 运行中帧）

## GUI 控制台（mission 034 / 总 spec 汇合面）

- **v2 默认入口**：自研浅色 SPA `http://127.0.0.1:3100/`（与 glue 八产物同端口）。Homepage `:3000` 配置保留回退，不再作为主路径。
- glue `console/console_feed.py`：refresh 每 10 分钟 + serve 127.0.0.1:3100，stdlib only
- 数据流：usage-monitor `GET /api/dashboard`（只读）→ status.json（含 `upcoming_personal`）；sync_pull 本地快照 → radar.json（可按日期回看）；console-schedule.toml → 双 ICS；个人层可在 UI 增删改（系统层只读）；messages.json = messages.md 待决 + refresh 派生的告警/最新
- Agent 协议与使用说明：`console/README.md`。**控制台不派任务。** 新会话不会自动把 3100 当必经入口。

## 双 agent（CC × Codex）（mission 027 / 总 spec §6.3）

- 直调封装：`scripts/codex_exec.py run <prompt文件|-> [--model X] [--timeout N] [--out DIR] [--json-out PATH] [--skip-git-check]`——`codex exec --json` 直调：NDJSON 事件解析、超时树杀（Windows taskkill /T）、7 类错误分类（authentication / rate_limit / network / trust / sandbox / not_installed / unknown）、git 信任检查（非 git 目录自动加 `--skip-git-repo-check`）。exit code：0=ok 1=失败 2=未装 3=超时 4=认证失败
- 三模式：`scripts/codex_modes.py mutual-review <diff文件> [--context 文件] [--timeout N] [--out review.json]`——codex 审 diff，返回带证据、触发条件、影响、反证、置信度和验证测试的 findings；`scripts/codex_modes.py dual-implement <spec文件> --impl-dir <CC实现目录> --tests-dir <测试目录> [--timeout N] [--out dual.json]`——codex 在 `<impl-dir>/codex_impl` 写平行实现，manifest 合法且与磁盘闭环后才对两实现运行同一测试套件并机械比对分歧（behavior/interface/style）；`scripts/codex_modes.py claim-check <claims.json> [--cc-verdicts 文件] [--timeout N] [--out claims.json]`——codex 逐条 verdict（true/false/unsure），并返回证据、反证、缺失上下文和置信度
- 输出：modes 各 `--out` 为含 status/findings|divergences|claims 的 JSON；成功结果不重复嵌入 `raw`，失败结果保留原始文本用于诊断；`protocol.status` 区分 `valid`、`repaired`、`partial`、`invalid`，并记录格式修复、丢弃条目、缺失字段和非法字段；codex_exec `--out` 落 text.txt + events.jsonl（原始事件流）
- 验收：历史代码独立审（broker/executor.py）命中率 3/3 = 100%（3 findings 全真问题、0 误报 0 风格、全为新问题）；报告 `reports/2026-08-codex-dual-agent-acceptance.md`
- 运维注意：本机 codex 冷启动 ~128s（WS 重连回退），互审类调用建议 `--timeout 900`+（验收实测 1800 成功）；编排默认 300/600/300（互审/claim/双实现）；超时与认证等错误分类含义见 codex_exec.py `_CLASSIFIERS`
- 模型：`--model` 透传 codex，模型选择用户自理（总 spec §8 策略表）
- Prompt 质量回归集：`scripts/tests/prompt_quality_cases.json` + `test_prompt_quality.py`，锁定证据/反证/不确定性/置信度、严格 JSON 契约和禁止臆造等关键质量要求

## 模型路由表（mission 029 / 总 spec §8）

- 表：`config/model-routing.json`（用户维护、系统只读；值为抽象档位键，具体模型名在执行侧）。改表不会自动改已经注入的任务卡。
- dsh：任务卡头 `model: flash|pro` → executor 映射 `--patch /mnt/broker/dsh-patches/{model}.yml`（patch 缺失任务 failed）
- codex：CC 查表传 `--model`（Luna 杂活 / Terra 默认 / Sol 关键场景；production-fix 归 CC）
- 纪律：长实验任务卡 `timeout` 必填

## 部署连接（当前家庭网络）

- **RK3528（现网）**：直连 `10.77.0.1/30`；USB Wi-Fi `liudfs`（LAN DHCP 会变）。SSH 优先 Tailscale `rk3528` / `100.78.158.80`（直连 host key 可能失败）；亦可用 `liuxfs@10.77.0.1`
- 用法：`ORCHESTRA_SSH_HOST=10.77.0.1 [ORCHESTRA_REMOTE_ROOT=/home/liuxfs/broker-data] bash scripts/deploy_broker.sh`（现网 timer 默认 `ORCHESTRA_ENABLE_TIMERS=1`。**2026-09-02 起雷达暂停**：盒子上 `orchestra-timer.timer` 已 disable；backup/exam-watch 仍 enable。不要为恢复雷达而把现网改成 `ENABLE_TIMERS=0`。记录 [`../docs/reports/2026-09-02-orchestra-pre-runner-freeze.md`](../docs/reports/2026-09-02-orchestra-pre-runner-freeze.md)）
- 切机记录：[`docs/rk3528-standby-cutover.md`](docs/rk3528-standby-cutover.md)。树莓派 4B 已停 Orchestra/NAS/Bogda，可断电。Prefect 运维见 [`../bogda/docs/pi-shadow-runbook.md`](../bogda/docs/pi-shadow-runbook.md)（Gate 6 已通过；USB remount 合同仍有效）
- 部署脚本先只把 `migration_guard.py` 临时上传到远端 `/tmp` 并检查任务文件及 SQLite；预检通过后才覆盖在役代码。发现 queued/running/仍可重试 failed 的旧单体雷达任务时，部署在任何线上文件覆盖前退出
- **现网 REMOTE_ROOT = `/home/liuxfs/broker-data`**。`/mnt/broker` 在 RK3528 上指向该目录（executor 仍写 `/mnt/broker/dsh-patches/`）
- **Tailscale**：RK3528=`rk3528`(100.78.158.80)、核桃派=`walnutpi`(100.64.2.60)、Windows=`laptop-w0cessade`。旧 4B 名 `liuxfs`(100.111.75.58) 不再当调度。`ORCHESTRA_SSH_HOST` 为 env 驱动
- **学校网络切换：见 `orchestra/docs/school-network-switch.md`**（入学前必读）

## 冷备链（NAS 方案 A）

- 核桃派（192.168.0.200）为冷备接收端：`~/backup/broker/`（rsync over ssh，免密）+ samba 共享 `\\192.168.0.200\backup`（user pi）
- RK3528 每日 03:00 `orchestra-backup.timer` 触发盒子上 `/home/liuxfs/broker/backup_to_nas.sh`（repo 副本在 scripts/，deploy_broker.sh 同步传载；增量镜像 + SQLite 快照，源路径随 REMOTE_ROOT 改写）
- 部署拓扑：RK3528=宿舍（Broker + NAS + Prefect），核桃派=实验室（展示+异地冷备）
- 验收报告：`reports/2026-08-cold-backup-acceptance.md`

## RK3528 兼职 NAS（原 4B / mission 026 D16 / 西数 250G）

- 盘：西数 250G ext4 `LABEL=nas-data` UUID `d105381a-d80e-47b0-8bb4-2a8c4b56600f`，挂 RK3528 USB3 → `/mnt/nas`（fstab UUID+nofail）
- 共享：samba `\\10.77.0.1\nas`（user liuxfs；密码在盒子上，不落库）。Tailscale `\\100.78.158.80\nas`
- 备份：`nas_backup.sh`（rsync broker results/logs → `/mnt/nas/backup/broker/`）+ `nas-backup.timer` 每日 04:17；源码 `orchestra/nas/`
- 定位：冷备 NAS（入学后宿舍 NAS 预演）；高性能文件服务仍按总 spec §14 触发 N100 评估
