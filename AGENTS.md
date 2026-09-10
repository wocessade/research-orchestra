# AGENTS.md — Research Orchestra

## 这是什么

科研**任务调度器**（不是自主科研体）：CC 编排 + **RK3528** Broker（7×24 队列，dsh/shell）+ 核桃派墨水屏/冷备 + Codex 副脑 + Tailscale + RK3528 兼职 NAS + Prefect（Bogda）+ 夜间文献雷达（23:30）。对外叙事与锐评回复见根 `README.md`、`docs/reports/2026-08-22-critique-replies.md`。

**bogda（`bogda/`）是 Prefect 继任者**：本地纵向切片可通过，受监督协调器在 batched 分支演进；现网 Orchestra 与 Prefect 都在 **RK3528**（`10.77.0.1` / `:4200`）。`bogda-console/` 是 Bogda 控制台影子重写（跑 `codex/bogda-console` 分支，不动旧 3100 数据）。xju-desktop 是独立仓库，勿当作 submodule/gitlink 纳入本仓库。

## 执行与指令范围

本文件是仓库级规则入口；CLAUDE.md 只引用这里。用户当前明确指令优先于本项目技能中的流程默认值；系统和开发者规则仍适用。技能不能扩大用户授权。

- 在已授权范围内完成读取、编辑、修复和必要验证；常规实现细节自行判断。缺失信息会改变研究结论、范围或授权时才提问，同时继续不依赖答案的工作。
- 禁止防御性写作和防御性编程：直接说明结论与证据，不添加假想风险免责声明；不写无依据的兜底或吞错。保留输入契约、凭据保护和下述 ingest 校验。
- 按实际任务选技能、读取当前阶段需要的 references。同一会话已读且未变化的内容不重复加载。多阶段或跨会话任务保留目标、当前状态、下一步和验证证据；不因文件数或“仔细做”强制启动整套流程。
- 按改动影响验证。文档改动检查引用、指令一致性和相关契约；代码改动运行对应模块测试。检查通过后，仅在新改动、失败或未决问题出现时扩大验证。
- 如技能导致暂停，指出具体文件、条款和缺失的授权；已有授权不重复询问。发送消息、提交投稿、push/merge/deploy、采购或生产状态变更须有覆盖该动作的明确授权。

## 按任务读取

| 任务 | 参考 |
|------|------|
| 项目现状与范围 | 本文件「当前挂账」；需要拓扑时读 README.md |
| Orchestra 运行、命令或运维 | orchestra/README.md |
| 架构验收或子系统状态追溯 | docs/superpowers/specs/2026-08-18-research-orchestra-design.md §13 |
| 排障或任务归档 | docs/lessons-learned.md；归档时追加实际新增的教训 |
| 恢复旧任务 | 对应 .tasks/ 中的 STATE 和必要的任务记录 |

结构查询优先使用可用且已索引的 CodeGraph：context 后按需 explore；符号查询用 search，调用关系用 callers/callees，影响用 impact。字面文本与 Markdown 指令审计用 rg/read。索引缺失、过期或工具不可用时使用文件搜索；初始化索引作为单独建议，不阻塞已有授权工作。

## 硬约束（红线）

- commit 不加 Co-Authored-By/署名行
- ~/.codex 残留只读；auth.json 绝不 copy/commit/打印内容
- 模型调度策略用户自理（fcc-server 管理端勿动）
- 删除/清理文件前必须先问用户
- 临时文件统一 D:\Temp，不进仓库
- 未跟踪目录（01thesis/、ml-notes/、FCC 脚本、.tasks/、pm3-mcp-server/、.proxmark3/、orchestra/results、logs）一律不入库
- GitHub 仓库 wocessade/research-orchestra 为 private；push 走已配置的 git 代理
- 凭据走环境变量/systemd env，绝不入库
- **不要擅自 `check_skills.py --lock-current`**（digest 锁定须 owner 明确开口）

## 关键链路速查（Orchestra 历史；现网见当前挂账）

- 派任务：T-*.md 任务卡 → `orchestra/scripts/sync_push.sh` → RK3528 broker 队列执行 → attempt-N 落盘
- 状态：RK3528 reporter 每 30s POST 核桃派 usage-monitor（X-Monitor-Token 鉴权）→ 墨水屏融合面板
- 雷达：原定每晚 23:30 注入四阶段任务（2026-09-02 已冻结；此处仅说明恢复后的链路）（`templates/nightly-radar-{fetch,rank,render,notify}.md` → 10/20/30/40，depends_on 串联），晨间 QQ 邮箱日报；评分五维为唯一权威（pipeline 六维弃用，仅精读/归档场景调用）；日报 top5 精读走 nature-reader
- 定时：03:00 冷备到核桃派 / 04:17 NAS 盘内备份 / 周日 04:00 housekeeping
- 双 agent：`orchestra/scripts/codex_exec.py` + `codex_modes.py`（互审/双实现/claim 核验）；本机 codex 冷启动 ~2min，互审建议 --timeout ≥900
- 模型路由：任务卡 `model: flash|pro` 字段（dsh --patch）；codex 三档由 CC 查 `orchestra/config/model-routing.json` 透传。改路由表不会自动改已注入的卡
- `orchestra/config/rules.yaml`：**Broker 不读**；改了不会改调度
- 并发：仅在当前运行环境允许、子任务独立且收益明确时委派；协调者负责接口和集成，子 agent 不 commit。历史并发档位见 `docs/superpowers/specs/2026-08-20-concurrent-work-modes.md`，不作为当前模型或并发数默认值。
- 测试：`unittest discover` 分别在 `orchestra/broker` 与 `orchestra/scripts`（以及改到的 `console/`）跑；不要把个数手抄进文档
- ingest：`jsonschema` + `academic-shared/research/metrics.schema.json` fail-closed；schema 在 `skills.json` 契约中
- 控制台：`http://127.0.0.1:3100/`（`python orchestra/console/console_feed.py serve`）；数据刷新 `python orchestra/console/console_feed.py refresh`
  - **留言三栏**：告警/最新由 `refresh` 从 status+radar 派生（离线、同步失败、雷达阶段失败、任务失败、雷达摘要），不要手写日常状态。**待决**用首页输入框（`POST /api/pending`）或仍可写 `messages.md` 的 `- 待决：`。agent 只有在需要 owner 拍板时才加待决；收束口头复述。挂账权威仍是本文件「当前挂账」。删 `- 待决：` 行或点「撤掉」即撤卡。不要每 10 分钟往 `messages.md` 刷日程提醒。
  - 个人日程：控制台首页可增删改，或改 `orchestra/console/console-schedule.toml` 的 `[[personal]]`；系统层（雷达/备份）只读。用法见 `orchestra/console/README.md`
  - **日程将近提醒**：读 `console-schedule.toml` 或 `status.json` 的 `upcoming_personal`（未来 14 天未完成个人事项）。会话开头或收束时：48 小时内必须口头提醒，7 天内顺带一句，8–14 天轻提一次。不要每 10 分钟往 `messages.md` 刷提醒。

## 当前挂账（更新日期 2026-09-11）

- **到校接机（2026-09-10，交接点→续接已通过 checkpoint 验收）**：Y7000 2021H / `19041@100.73.48.81` 已接通 SSH、WSL2 Ubuntu、NAS 和 `dorm-x86`，并发 1；自主 smoke Completed，WSL 重启后 NAS/worker 自动恢复通过。WSL 自 2026-09-11 起由 S4U 开机任务无登录启动（InteractiveToken 任务为兜底）。checkpoint 真机验收**已通过**：两次 key 修复（artifact key + pause key，共用 `_kind_slug` 归一化）已部署 runner/RK，run `11505d2b` 两次真实 Paused→恢复→Completed；失败证据 `66d4a924`（v1）、`cff1fc6b`（v2）保留。3101 展示与白名单核对通过，**DEF-03 未申报**。先读 [`runner 工作交接`](docs/reports/2026-09-10-bogda-runner-handoff.md) 与 `.tasks/active/059_bogda-campus-runner/STATE.md`。

- **阶段定位（用户定调）**：【术】已足够，转入【道】——新任务优先论文/研究实体；执行重心 Bogda。纯 Orchestra 基建只记挂账
- **Skill digest：owner 暂不锁**（2026-08-22 起）。`academic-shared` 为 required 且 `expected_digest` 未写；engine 契约已改过。`check_skills --strict` / 真实 `run_card.py ingest` 会 HARD。需要入账时再开口锁定，agent 不得自行 `--lock-current`
- **exam-watch 已随 Orchestra 停用（2026-09-10）**。旧部署缺口保留历史：盒子上 `orchestra-exam-watch.service.d/env.conf` 需手工从 broker 的复制（deploy 脚本只 WARN）。
- Pi/RK 部署窗口：deploy_broker.sh 已含 exam-watch；taskfile 收紧、artifact 校验、taskkill 树杀等与仓库对齐仍挂
- Bogda Gate 6：**通过**（2026-08-31，trial `20260830T154019Z`）。见 [`docs/reports/2026-08-31-bogda-rk3528-gate6-final-acceptance.md`](docs/reports/2026-08-31-bogda-rk3528-gate6-final-acceptance.md)
- Gate 7：**S1 只读影子 + S2 专用白名单写入已通过**（合入 `e79f79b`）。不是 3100 切换，不是生产科研任务。证据 [`2026-09-01-bogda-gate7-entry-decision.md`](docs/reports/2026-09-01-bogda-gate7-entry-decision.md)、[`S1`](docs/reports/2026-09-01-bogda-console-s1-real-shadow.md)、[`S2`](docs/reports/2026-09-01-bogda-console-s2-allowlisted-shadow.md)。盒子上仍留 S2 验收资源 `bogda-s2-acceptance-20260901-...`（未删）
- **Bogda 落地（2026-09-11）：软件接线全部完成并现网验收通过**。RK 单机持库（`/var/lib/bogda/*.sqlite`）+ runner 走 HMAC 窄接口（`/api/v1/store/*`，域分离签名 ±300s 重放窗；`tailscale serve` 必须用 MagicDNS 名，裸 IP 404）；预算权威全在 console 侧（真余额 usage 源），runner 只持 HTTP 适配器；日志布局改为 `attempts_root/{run_id}/attempt-N`（NAS 共享根，3101 可读）；3101 开放为 `allowlisted-test`/`owner` + 精确 `ALLOWED_DEPLOYMENT_IDS`/`ALLOWED_WORK_POOL_NAMES`。验收证据：checkpoint v3 `11505d2b`、日志 `a5048474`、console 决定 `5937cbe8`、付费审批 `f6ca6906`（凭证 `46b0ea93`）、usage-unknown `e530ab0a`、FINISHED 快路径 `772b94e6`；报告 [`2026-09-11-bogda-landing-acceptance`](docs/reports/2026-09-11-bogda-landing-acceptance.md)。**真实 dsh 已装并真实验收（2026-09-11 追加）**：node22 + `@deepseek-ai/dsh@0.1.0-rc.7` 于 runner，认证走 runner.env 注入，usage.json 由 `~/.local/bin/dsh` 桥（会话日志 token 提取，钱由 bogda 自算）产出；run `3157b68c` 真实付费调用 Completed（actual 0.02271 CNY，账本 reserve 2→reconcile 全链，余额 34.12）。**自主策略已接线**：`LocalAutonomyPolicyAdapter` + `BOGDA_AUTONOMY_POLICY_PATH`（allowlisted-test+owner 可写，revision 并发保护，现网 rev 0→1 验证）。**DEF-03 已申报通过（同日，owner 指令）**：3101 接替 3100 落地，证据链见报告。**剩余运维项**：AtStartup 冷开机触发确认、宿舍–实验室跨网络实测、真实科研任务实投。保持 Wake Bridge 不接、研究任务不进 pi-service、旧 3100 不恢复。
- **Orchestra 已停用（2026-09-10）**：按 owner 要求，RK3528 的 broker、雷达、exam-watch、旧冷备、housekeeping 服务/定时器已停止，broker 与四个 timer 均 verified inactive/disabled；本机 `OrchestraConsoleRefresh` 已 disabled，3100 无监听。保留旧数据。Bogda Prefect/worker/3101、Samba、NAS 独立备份与 Prefect 快照继续运行。接机记录见 [`2026-09-10-bogda-campus-onboarding.md`](docs/reports/2026-09-10-bogda-campus-onboarding.md)；9 月 2 日仅停雷达的状态已被本条取代。
- SSH：维护优先 Tailscale `rk3528` / `100.78.158.80`；直连 `10.77.0.1` 可能 host key 失败
- 4B 已空：Samba NAS 与 Bogda 在 RK3528；Orchestra 已停用、历史数据仍保留。4B 可断电。
- owner 已到校（2026-09-10）：手机热点下管理机、RK3528、runner 的 Tailscale 已互通；宿舍–实验室跨网络实测仍待完成。4B 弱密码已改（2026-08-20），核桃派 pi 密码待上线后同步。
- 雷达→Zotero 直连推迟到开学后再设计（`docs/superpowers/plans/2026-08-20-radar-digest-reading-note.md`）
- **旧 GUI 3100 已停用（2026-09-10）**，本机刷新任务 disabled，无监听；历史留言保留 `orchestra/console/messages.md`。**由 Bogda 3101 接替，接替验收 2026-09-11 完成（DEF-03 申报通过）**：精确白名单写入、付费审批/recovery/日志/自主策略均已由 3101 承担。
- 锐评有意不做：全文证据扫描器、原子 `releases/<sha>` 发布、Hermes / OpenClaw
- 待用户拍板：SD 旧副本删除、512G SSD 用途、宿舍 NAS、QQ bot、**触发式 agent**（闲时不烧 token；盒子 `brief` 入队未接）。3101 聊天框连 worker dsh **已否**（离机审批用 3101 按钮 + NAS inbox）
- 宿舍 runner：第二台笔记本 Y7000 已作为 `dorm-x86` 接入，pool/queue/deployment/worker 并发 1；新硬件采购仍暂停。付费链已**真实 dsh 验收**（2026-09-11，run `3157b68c`）；真实科研任务实投仍待首次。无人值守自启依赖 S4U 开机任务（已部署）；宿舍网络掉线需人工恢复，不自愈。
- 注释惯例：xju-desktop（以及未来的独立仓库）只以文档引用，不 gitlink 嵌入；会话调试产物统一 D:\Temp\.codex-session
