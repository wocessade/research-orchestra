# CLAUDE.md — Research Orchestra 项目（D:\pythonProject）

## 这是什么

科研**任务调度器**（不是自主科研体）：CC 编排 + **RK3528** Broker（7×24 队列，dsh/shell）+ 核桃派墨水屏/冷备 + Codex 副脑 + Tailscale + RK3528 兼职 NAS + Prefect（Bogda）+ 夜间文献雷达（23:30）。对外叙事与锐评回复见根 `README.md`、`docs/reports/2026-08-22-critique-replies.md`。

**bogda（`bogda/`）是 Prefect 继任者**：本地纵向切片可通过，受监督协调器在 batched 分支演进；现网 Orchestra 与 Prefect 都在 **RK3528**（`10.77.0.1` / `:4200`）。`bogda-console/` 是 Bogda 控制台影子重写（跑 `codex/bogda-console` 分支，不动旧 3100 数据）。xju-desktop 是独立仓库，勿当作 submodule/gitlink 纳入本仓库。

## 新会话接手规则（重要）

接到本项目任何任务前，先读：
1. `orchestra/README.md` — 系统运行手册（命令/链路/运维）
2. `docs/superpowers/specs/2026-08-18-research-orchestra-design.md` §13 — 总 spec 检查清单与各子系统状态
3. `README.md` — 现状页（拓扑/挂账；**不再**维护 mission 流水、测试计数、Hermes 倒推）
4. `docs/lessons-learned.md` — 系统运行教训库（**每个 mission 归档时必须把新教训追加进去**）

按任务范围再读对应 mission 档案：`.tasks/completed/NNN_*`（MISSION/STATE/DECISIONS/BRIEF/AUDIT，编号见目录）。

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

## 关键链路速查

- 派任务：T-*.md 任务卡 → `orchestra/scripts/sync_push.sh` → RK3528 broker 队列执行 → attempt-N 落盘
- 状态：RK3528 reporter 每 30s POST 核桃派 usage-monitor（X-Monitor-Token 鉴权）→ 墨水屏融合面板
- 雷达：每晚 23:30 注入四阶段任务（`templates/nightly-radar-{fetch,rank,render,notify}.md` → 10/20/30/40，depends_on 串联），晨间 QQ 邮箱日报；评分五维为唯一权威（pipeline 六维弃用，仅精读/归档场景调用）；日报 top5 精读走 nature-reader
- 定时：03:00 冷备到核桃派 / 04:17 NAS 盘内备份 / 周日 04:00 housekeeping
- 双 agent：`orchestra/scripts/codex_exec.py` + `codex_modes.py`（互审/双实现/claim 核验）；本机 codex 冷启动 ~2min，互审建议 --timeout ≥900
- 模型路由：任务卡 `model: flash|pro` 字段（dsh --patch）；codex 三档由 CC 查 `orchestra/config/model-routing.json` 透传。改路由表不会自动改已注入的卡
- `orchestra/config/rules.yaml`：**Broker 不读**；改了不会改调度
- 并发两档：标准档（4-8 路扁平，030 已实战）/ 树状档（2 层×≤3 子树×≤12 叶子，031 首跑）；opus 只接口+统一 commit，agent 不 commit；约定 `docs/superpowers/specs/2026-08-20-concurrent-work-modes.md`
- 测试：`unittest discover` 分别在 `orchestra/broker` 与 `orchestra/scripts`（以及改到的 `console/`）跑；不要把个数手抄进文档
- ingest：`jsonschema` + `academic-shared/research/metrics.schema.json` fail-closed；schema 在 `skills.json` 契约中
- 控制台：`http://127.0.0.1:3100/`（`python orchestra/console/console_feed.py serve`）；数据刷新 `python orchestra/console/console_feed.py refresh`
  - **留言三栏**：告警/最新由 `refresh` 从 status+radar 派生（离线、同步失败、雷达阶段失败、任务失败、雷达摘要），不要手写日常状态。**待决**用首页输入框（`POST /api/pending`）或仍可写 `messages.md` 的 `- 待决：`。agent 只有在需要 owner 拍板时才加待决；收束口头复述。挂账权威仍是本文件「当前挂账」。删 `- 待决：` 行或点「撤掉」即撤卡。不要每 10 分钟往 `messages.md` 刷日程提醒。
  - 个人日程：控制台首页可增删改，或改 `orchestra/console/console-schedule.toml` 的 `[[personal]]`；系统层（雷达/备份）只读。用法见 `orchestra/console/README.md`
  - **日程将近提醒**：读 `console-schedule.toml` 或 `status.json` 的 `upcoming_personal`（未来 14 天未完成个人事项）。会话开头或收束时：48 小时内必须口头提醒，7 天内顺带一句，8–14 天轻提一次。不要每 10 分钟往 `messages.md` 刷提醒。

## 当前挂账（更新日期 2026-09-02）

- **阶段定位（用户定调）**：【术】已足够，转入【道】——新任务优先论文/研究实体；执行重心 Bogda。纯 Orchestra 基建只记挂账
- **Skill digest：owner 暂不锁**（2026-08-22 起）。`academic-shared` 为 required 且 `expected_digest` 未写；engine 契约已改过。`check_skills --strict` / 真实 `run_card.py ingest` 会 HARD。需要入账时再开口锁定，agent 不得自行 `--lock-current`
- **exam-watch 已上线**（RK3528 timer 轮询雨课堂 → console 告警融合）。缺口：盒子上 `orchestra-exam-watch.service.d/env.conf` 需手工从 broker 的复制（deploy 脚本只 WARN）
- Pi/RK 部署窗口：deploy_broker.sh 已含 exam-watch；taskfile 收紧、artifact 校验、taskkill 树杀等与仓库对齐仍挂
- Bogda Gate 6：**通过**（2026-08-31，trial `20260830T154019Z`）。见 [`docs/reports/2026-08-31-bogda-rk3528-gate6-final-acceptance.md`](docs/reports/2026-08-31-bogda-rk3528-gate6-final-acceptance.md)
- Gate 7：**S1 只读影子 + S2 专用白名单写入已通过**（合入 `e79f79b`）。不是 3100 切换，不是生产科研任务。证据 [`2026-09-01-bogda-gate7-entry-decision.md`](docs/reports/2026-09-01-bogda-gate7-entry-decision.md)、[`S1`](docs/reports/2026-09-01-bogda-console-s1-real-shadow.md)、[`S2`](docs/reports/2026-09-01-bogda-console-s2-allowlisted-shadow.md)。盒子上仍留 S2 验收资源 `bogda-s2-acceptance-20260901-...`（未删）
- **下一跳（runner 到手前软件已合）**：NOW-06 已并入本线。3101 **托管在 RK3528**（`bogda-console.service`，loopback + `tailscale serve --http=3101`；首发 `real-readonly`/`observer`）。dsh 运维只许 `/opt/bogda-console/maintain.sh`。owner 接 runner 后按 [`2026-09-02-bogda-runner-handshake.md`](docs/reports/2026-09-02-bogda-runner-handshake.md) 填精确白名单。**仍缺** DEF-03 真 checkpoint。**不要**接 Wake Bridge、**不要**改 3100、**不要**把研究任务丢进 `pi-service`。部署 [`2026-09-02-bogda-console-on-rk3528.md`](docs/reports/2026-09-02-bogda-console-on-rk3528.md)
- **Orchestra 冻结（2026-09-02）**：现网已 `disable --now orchestra-timer.timer`（夜间雷达停）。**未停**：broker、exam-watch、backup、housekeeping、Samba、3100、Prefect。恢复：`sudo systemctl enable --now orchestra-timer.timer`。记录 [`2026-09-02-orchestra-pre-runner-freeze.md`](docs/reports/2026-09-02-orchestra-pre-runner-freeze.md)
- SSH：维护优先 Tailscale `rk3528` / `100.78.158.80`；直连 `10.77.0.1` 可能 host key 失败
- 4B 已空：Orchestra + Samba NAS + Bogda 均在 RK3528（`10.77.0.1` / `\\10.77.0.1\nas` / Prefect `:4200`）。4B 可断电。
- 入学前（2026-09-08）：宿舍–实验室 Tailscale 实测；4B 弱密码已改（2026-08-20），核桃派 pi 密码待上线后同步
- 雷达→Zotero 直连推迟到开学后再设计（`docs/superpowers/plans/2026-08-20-radar-digest-reading-note.md`）
- **GUI 控制台 v2 主入口 3100**（Homepage v1 仅回退）；留言=`orchestra/console/messages.md`；`ORCHESTRA_MONITOR_TOKEN` 已配用户环境变量（值绝不入库/入对话）。v1.5 tailnet 手机访问 3100 仍挂账。Bogda 3101 见上条（盒子 Tailscale）
- 锐评有意不做：全文证据扫描器、原子 `releases/<sha>` 发布、Hermes / OpenClaw
- 待用户拍板：SD 旧副本删除、512G SSD 用途、宿舍 NAS、QQ bot、**触发式 agent 与 dsh 能力面**（闲时不烧 token；dsh 白名单未设计）
- 宿舍 runner：**采购暂停**（2026-08-30，硬件涨价）。该层暂由第二台笔记本顶替；**未**接 Prefect `dorm-x86`、Wake Bridge、或提高并发。RFC 三档预算不再当采购清单
- 注释惯例：xju-desktop（以及未来的独立仓库）只以文档引用，不 gitlink 嵌入；会话调试产物统一 D:\Temp\.codex-session
