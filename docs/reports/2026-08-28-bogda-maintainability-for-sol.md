# Bogda 可维护性缺口（给 SOL）

> **历史清单。** Gate 6 已于 2026-08-31 通过，Gate 7 S1/S2 影子已通过。下文 08-28/08-30 口径不要当现网挂账。仍有效的是：不要切 3100、不要把触发式 agent 当成已拍板、不要把「第二台笔记本在」当成宿舍机已接入。

日期：2026-08-28；补记：2026-08-30  
作者：Grok（08-28 清单）；08-30 对照现网恢复更新状态  
读者：SOL  
目的：把已核实的维护债务写成可逐条验收的清单。**当时不要当 Gate 6 通过，不要切 3100，不要把触发式 agent 设计成已拍板。**

**08-30 已落地（仍不是 Gate 6）：** 工作台顶部改为单一「当前事实」；`bogda/README.md` 写了「改调度改哪边」；`pi-service` 活文档标明冻结名；server/worker remount 自愈已上盒并拉起 Prefect；`deploy_broker.sh` 注释改为现网 RK3528。记录：`docs/reports/2026-08-30-bogda-rk3528-prefect-restore.md`。

现网：RK3528，SSH 优先 `100.78.158.80`，Prefect `:4200`，数据 `/mnt/nas/.bogda`，池名仍 `pi-service`。  
Gate 6 失败轮：`20260828T064220Z`。新 24h trial **未开**。

不要在恢复后的日常维护里重装 Bogda、改并发、或碰 live `prefect.db` / `bogda.env` 内容。新 trial / reboot / 离线 fsck 仍须另开口。

---

## 不要做

- 宣布 Gate 6 / Gate 7 通过；接 3101 真 Prefect 写入（须 Gate 6 + owner 批 S1/S2）。
- 把「触发式 dsh 做短决策」写成已定方案。owner 只要：**触发式 agent、闲时休眠不烧 token**；**dsh 能力面必须另开设计**，未批准前不接到 `pi-service`。
- 常驻 LLM / OpenClaw / 7×24 管家；在控制面跑论文代码或 CUDA。
- 为了「好看」把 `pi-service` 改名为 `rk3528-service` 而不改 worker unit、Prefect 池和 bundle 测试（会弄坏现网）。
- 删除 `/home/liuxfs/bogda-stage-55b4d9b`、健康 jsonl、快照、`last-backup`。

---

## P0 — 接班文档说谎（改文档即可）

工作台 `docs/reports/2026-08-24-bogda-stage6-workboard.md` 顶部 8-28 补记是对的，**下面「当前快照」仍是 8-24 事实**，会把下一会话带沟里。

| 声称（过时） | 现况 |
|---|---|
| Git `4d8e470` 未 push | `main` 已含 RK3528 文档提交（至少 `6bbe54a`），以 `git log` 为准 |
| Gate 6 进行中 72h、trial `20260824T083454Z` | 该轮 **未通过**；现网 trial `20260828T064220Z`、**24h** |
| 「Grok：72小时后 Gate 6 操作」 | 截止改为明天 14:42；受控 reboot **仍须 owner 开口** |
| 恢复顺序仍写 ssh 4B / 72h 已过不等于通过 | 只读目标改为 `10.77.0.1`；24h 已过也不等于通过 |

验收：工作台只保留**一份**「当前事实」表；过时段落标明「历史，勿执行」。恢复顺序 5 步与 8-28 补记一致。

---

## P1 — 命名债务（代码+测试，可分两步）

现网主机是 RK3528，契约仍叫 Pi。这是刻意冻结，但维护成本已经显现（文档每处都要加注）。

| 符号 | 位置 |
|---|---|
| `work_pool = "pi-service"` | `bogda/deploy/pi/manifest.toml`、`bogda/src/bogda/ops/bundle.py` `EXPECTED_VALUES` |
| `bogda-pi-worker.service` | `bogda/deploy/pi/systemd/`、`EXPECTED_UNITS` |
| 目录 `deploy/pi/`、runbook 文件名 `pi-shadow-runbook.md` | 路径 |

**建议 SOL 先做文档层、不要改池名：** 在 `bogda/README.md` 和 runbook 用一小节写死「`pi-service` = 控制面轻任务池，与树莓派无关」。若 owner 以后要改名，必须：Prefect 建新池或 rename、改 unit `ExecStart`、改 `EXPECTED_VALUES`、改 bundle 测试、盒子上 `systemctl daemon-reload`——**Gate 6 窗后 + owner 批**。

验收（本波）：仓库内「Pi 即主机」的**活文档**不再把 4B 写成现网；历史 Gate 报告不动。

---

## P1 — bundle 冻结合约过死

`bogda/src/bogda/ops/bundle.py`：`EXPECTED_VALUES` 定长、`load_manifest` 忽略额外键、`validate_bundle` 扫 `deploy/pi/` 全文禁 `/mnt/broker` 和 `orchestra-`。影子期 fail-closed 是对的，但**加一个说明性 toml 键或注释里的 orchestra 字样都会红**。

建议：允许 toml 里 `#` 注释（已可以）和**显式忽略的文档键**（如 `host_note`），或把「禁止 orchestra 字符串」从「任意文件全文」收窄到 unit/env，避免 README 级注释误伤。不要放松路径、user、`work_pool`、四条 env。

验收：现有 `tests/ops/test_bundle.py` 仍全绿；新增测试证明「文档用注释说明 RK3528」不会 `validate_bundle` 失败。

---

## P1 — 真机 Python/venv 不可移植（记文档+检查脚本，窗内不重装）

教训 51–52：从 4B 拷来的 `.venv` shebang 曾指向 `/root/.local/share/uv/python`，Armbian 上要改到 `/opt/uv-python/...`，否则 203/EXEC。

建议：`bogda/docs/pi-shadow-runbook.md` Gate 2/3 加一条只读检查：`head -1 /opt/bogda/.venv/bin/prefect` 不得包含另一台机器的 uv 路径。可选：仓库加 `python -m bogda.ops.health` 类的 **本地能跑的路径探针**（测假 shebang 文本），不要 SSH 写盒子。

验收：runbook 有检查命令；窗内 **不** `uv sync` 覆盖 `/opt/bogda`。

---

## P2 — 双控制台、双调度

| 面 | 职责 | 债务 |
|---|---|---|
| `orchestra/` + 3100 | 现网任务、雷达、dsh | 真任务仍在这里 |
| `bogda/` Prefect | 影子控制面 | 未接真实研究 Flow |
| `bogda-console/` 3101 | 分支 `codex/bogda-console`，mock/只读 | 与 3100 行为分叉；合并/回归未做（README Deferred） |

建议：写一页「改调度改哪边」速查（10 行）：雷达/exam-watch → Orchestra；Prefect UI/worker → RK3528 `:4200`；3101 未授权不接真 API。放到 `bogda/README.md` 或 `orchestra/README.md` 互链。不要开始 3100 切换设计。

验收：新人只读 README 能回答「今晚雷达挂了 ssh 哪台、哪套 timer」。

---

## P2 — 部署脚本注释仍像备机

`orchestra/scripts/deploy_broker.sh` 已支持 `ORCHESTRA_ENABLE_TIMERS`，但注释仍写「1=现网 4B；0=RK3528 备机并行」。现网是 RK3528 且 timer 为 1。

验收：注释改为「1=现网（RK3528）enable 全部 timer；0=并行机禁止双开雷达」。默认值保持 1。

---

## P3 — owner 待设计（SOL 只列问题，不发明方案）

触发式 agent（架构 §16.1）：

1. 触发源：timer / Flow / 人 / 告警？  
2. 闲时如何保证无进程、不占模型会话？  
3. dsh 允许的工具、任务卡字段、超时、并发（与 Prefect worker limit 1 如何互斥）？  
4. 哪些决定可自动落（Type-A），哪些必须停（Type-B：值不值得读、结论、对外发、采购）？  
5. 复用 Orchestra `executor: dsh` 还是 Prefect 拉起独立入口？

SOL 若写设计稿：只出选项+利弊+推荐，**标明待 owner 拍板**，不要改 `deploy/pi` unit。

---

## 建议求解顺序

1. ~~P0 工作台「当前事实」去歧义~~（2026-08-30 已改工作台顶部）。
2. ~~P1 活文档命名说明~~（`bogda/README.md` / runbook banner）；bundle 注释误伤仍可选。
3. ~~P2 README 速查 + `deploy_broker.sh` 注释~~（2026-08-30）。
4. P3 触发式 agent 设计稿（无代码）——仍待 owner。
5. Gate 6：**失败轮已收口**；Prefect 已恢复。新 trial / reboot / restore **等 owner**。离线 SMART/fsck 未做。

内核（contracts/flows/ops 测试）不是本清单的修复对象；问题在接班面、冻结合约和双栈，不在「Python 写得乱」。
