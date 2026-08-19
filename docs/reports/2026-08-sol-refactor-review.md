# SOL 输出质量重构终审报告（2974f61 合并版）

- 日期：2026-08-20（mission 031 树状档首跑 · 验收 agent 收口）
- 审查对象：SOL 提交 2974f61（35 文件 +4197/-190），审查基准为合并后工作区 HEAD=0aa606d（含 a2d31b8 合并：029 模型路由 + 030 三修复）
- 审查方法：树状档（2 层）：3 个 opus 子树协调者 × 11 个 haiku 叶子（A1-A4 broker 模块 / B1-B4 scripts / C1-C3 雷达链路+调度）+ 1 个 codex 交叉验证 leaf（C4，默认档 routing=terra，聚焦 executor.py）。全程只读，未改任何仓库文件、未 commit。本报告由验收 agent 对全部 HIGH/MED 亲自读码复核证据（file:line ±10 行）后，完成跨子树去重与严重度统一校准。
- 严重度统一标尺：**HIGH**=现网可触发且实质危害（数据丢失/安全边界逃逸）；**MED**=声称 vs 实现不符/边界缺陷；**LOW**=测试假绿/可用性；**观察**=文档误导/低概率未证实。

## 总结论

SOL 报告的核心声称绝大部分经代码核对、实跑与交叉验证成立：四阶段雷达闭环（fetch→rank SHA/集合/字段精确比对、确定性 render、notify at-most-once 状态机）、调度收敛（环检测/blocked/invalid 传播、原子 attempt、双重路径检查）、注入互斥与 stale 接管（/proc stat 第 22 字段解析实测正确）、Skill ingest 门禁时序与 HARD/2 语义、codex 协议收紧、deploy 预检时序，均属实现与声称一致。**但存在 1 条 HIGH 安全边界逃逸**（check_skills Windows 平台 `/abs`/`C:foo` 漏检，门禁在其实际运行平台上 fail-open，可将 root 外文件读入摘要并泄漏哈希入报告）与 4 类声称偏差（notify 恢复原则、traceback 泄漏承诺三处空洞、Skill 安装状态事实漂移、"exit 0 即成功"修复的未声明前置条件）。**结论：不阻断合并（已在 HEAD），无凭据泄漏、无写/执行面；全部修复为小改动（合计约 15-20 行），建议按"小包直接修 + 挂账 Pi 部署窗口"两档落地。**

## 确认成立项清单（三子树合并）

1. **rank 上游闭环**：ranking_summary.json 记录上游 SHA-256/数量/arXiv ID 集合，validator 逐项比对 title/url/categories/abstract —— 成立（A1/C2 双核，test_radar_pipeline 5 个拒绝用例锁定）。
2. **确定性渲染**：radar_render 确定性算法 + 选择轨迹 —— 成立（A2/C2）。
3. **调度收敛**：依赖缺失/环检测 → invalid、上游终态失败 → blocked 传播 —— 成立（A4/C3 实测 6 组探针）。
4. **路径/attempt 安全**：解析期+运行期双重路径检查、`mkdir(exist_ok=False)` 原子 attempt —— 成立（A4；codex 独立判 `_allocate_attempt_dir` 无并发复用缺陷）。
5. **注入互斥与 stale 接管**：owner 含 host/boot_id/PID/starttime，第 22 字段解析经合成用例+真实 msys /proc 核对正确；并发接管实测单胜出 —— 成立（A3）。
6. **migration_guard 部署门禁**：/tmp 预检 + 退出码 + `set -e` 阻断，7 场景含退出码通过 —— 成立（A3）。
7. **Skill ingest 门禁时序**：manifest 结构 → required → used_by → 入口存在 → digest 比对，六条要求与 HARD/2 语义实跑证实，无绕过路径 —— 成立（B2）。
8. **codex 协议收紧**：valid/repaired/partial/invalid 状态机、partial/invalid 非零退出、失败保留 raw、dual-implement manifest 门禁不通过不执行测试 —— 成立（B3）。
9. **deploy 预检时序**：临时上传 → 执行门禁 → 线上覆盖/迁移，顺序锁定 —— 成立（B4）。
10. **模板咬合**：四阶段模板 mode/detail/validator 取值与 executor/taskfile 键集全部咬合；notify 模板 `mode: brief` 合法 —— 成立（C1）。
11. **测试基线**：合并版 broker 102 / scripts 154 unittest 实跑通过（B4 亲跑；Windows 上 3 个平台正当 skip）。

## Findings 汇总表（去重后：1 HIGH + 12 MED = 18 条子树 MED − 2 条跨子树合并 − 4 条校准降 LOW）

| ID | 严重度 | 位置 | 一句话 | 子树来源（多视角标注） |
|---|---|---|---|---|
| H-1 | HIGH | check_skills.py:38-47 | Windows 漏检 `/abs`、`C:foo` 两类绝对/逃逸路径，§2"拒绝绝对路径"门禁在 CC 机 fail-open，root 外文件被读入 SHA-256 摘要 | B1 独占（协调者实测探针 + 验收复核） |
| M-1 | MED | radar_notify.py:78-86,130-134 | 锁 O_EXCL 创建、finally 删除，窗口内 SIGKILL → stale 锁永久残留、无接管，该日期通知永久 unknown 直至人工 rm | **A2 + C2 双叶子独立命中**，C 协调者亲核 |
| M-2 | MED | radar_notify.py:81-86（配 95/98 行） | 锁在 + state 缺失（可证明发送器未启动=未发送）仍归 unknown 拒恢复，与"只恢复能证明未发送的失败"原则矛盾 | A2 独占（C 持不同看法，见 M-2 详节） |
| M-3 | MED | executor.py:200（配 137-138；taskfile.py:84-86） | validator 仅挂在 `required_outputs` 非空门后：声明 validator 但漏写 required_outputs 的任务 exit 0 即 done，语义校验静默跳过 | **A1 实测 + codex HIGH + C 协调者三视角命中**（codex 原定 HIGH，统一裁定 MED） |
| M-4 | MED | send_email.py:49-51 | sendmail 一切异常（含 552 配额类可重试瞬时拒信）归 exit 1 → unknown 永不重试；当日日报永久丢失 | A4 独占 |
| M-5 | MED | inject_daily.sh:48,86-89 | `while ! mkdir` 只容忍 EEXIST：ENOSPC/EIO 下 mv 失败被吞 → 无限循环，仅 systemd oneshot 超时兜底 | A3 独占（合成用例验证机制） |
| M-6 | MED | deploy_broker.sh:28 vs 72 | 门禁执行与 `systemctl restart` 之间多轮 scp/ssh，旧 broker 全程在跑：窗口内队列变化可绕过门禁（TOCTOU） | A3 独占；B4 独立将同族 cron 注入窗口判 LOW（见详节） |
| M-7 | MED | check_skills.py:220-222 | 深嵌套 manifest 抛 RecursionError（非 ValueError 子类）不在 except 元组 → traceback 泄漏，违背"不泄漏 traceback"声称 | B1 独占（实测确认） |
| M-8 | MED | check_skills.py:231-236 | `--lock-current` 的 write_text 在 try 之外：只读 manifest → PermissionError traceback + 退出码 1 而非 2 | B1 独占 |
| M-9 | MED | run_card.py:191-192,245-247（配 check_skills.py:123） | inspect_skill 在 try 外调用，contract 文件锁定/不可读 → OSError 穿透 do_ingest 的 `except ValueError` → 生产 ingest 链路 traceback、退出码 1 而非 HARD/2 | **B1 + B2 双叶子独立互证**（B2 模拟 PermissionError 实测 UNCAUGHT） |
| M-10 | MED | orchestra/reports/2026-08-output-quality-refactor.md:137,141-145 | 遗留风险 1/2 声称"本机不存在/未安装"两 Skill，实跑两 Skill 均已安装、状态 unlocked（digest 已算出）——恢复步骤与现状脱节 | B1 独占（验收 agent 亲查 ~/.claude/skills 证实） |
| M-11 | MED | codex_modes.py:463-489（配 216-234,256-262,306-329） | 字段校验只查 isinstance 不查非空：claim/trigger/impact 空串 + confidence 0.0 + evidence [] 的空壳 finding 判 protocol valid → ok，与"语义缺失必须区分"声称不符 | B3 独占 |
| M-12 | MED | dispatcher.py:166-168,97（根因 db.py:33） | 终态任务卡重放被静默归档永不执行、无日志无恢复；Windows 上 archive rename 撞名抛 FileExistsError → 整队列 30s 死循环 | C3 独占（实测 C6 复现） |

**校准降级 4 条（子树原 MED → LOW，理由见 LOW 表）**：A-MED-4（executor→validator 接缝零测试）、A-MED-5（validate_fetch/render 负向分支未测，A1 已实测实现正确）、B-M5（"无 traceback"测试不断言 stderr）、B-M7（deploy 成功路径无行为测试，属覆盖缺口非代码缺陷）。

## HIGH/MED 详细小节（验收 agent 逐条亲读证据）

### H-1 check_skills.py Windows 路径逃逸（HIGH）

- **证据**：`_validate_relative_file`（38-47 行）四个拒绝条件：`path.is_absolute()`、`"\\" in value`、`value != path.as_posix()`、`"."/ ".." in parts`。Windows 上 `Path("/abs").is_absolute()` 为 False（无盘符根视为 drive-relative），parts 为 `("\\","abs")` 无 `.`/`..`，as_posix 恒等 → 全部通过；`Path("C:foo")` drive-relative，parts 无 `.`/`..` → 通过。随后 `_skill_digest`（115-125 行）`path = root / relative`：`root / "/abs"` → `D:\abs`（夺根）、`root / "C:foo"` → `C:foo`（换盘），对 root 外文件做 is_file 探测 + read_bytes + SHA-256，摘要值写入 lock/report 输出。B 协调者实测探针：`/abs`、`C:foo` 均 ACCEPTED；`C:/foo`、`C:\foo`、`../` 等其余形态正确拒绝。验收 agent 亲读确认机理与行号。
- **触发场景**：manifest 的 entrypoints/contract_files 含 `/abs` 或 `C:foo`（协作 PR 或笔误均可）；该门禁的实际运行平台正是 Windows CC 机。
- **影响界定**：仅读侧——任意本地文件的存在性探测 + SHA-256 哈希泄漏进报告/lock 文件（无内容外泄、无写、无执行）；同 manifest 在 4B（Linux）会被正确拒绝，跨平台行为不一致削弱门禁可信度。
- **修复建议**：拒绝条件追加 `path.drive or path.root` 即可跨平台闭环（1 行），并补 `/abs`、`C:foo`、UNC 探针测试。

### M-1 radar_notify.py stale 锁残留无接管（MED · 双视角命中）

- **证据**：锁在 78 行 `O_EXCL` 创建；80-86 行 FileExistsError → unknown rc=2 且不 unlink；130-134 行 finally 仅正常退出时删除。78-95 行窗口内 SIGKILL（executor.py:212 killpg 已亲见）后：锁残留、state 未写或已写 sending，下次运行 69-73 或 80-86 均 rc=2，无人删锁。与 inject_daily.sh 的 owner+starttime 接管形成鲜明对比（同类防护未推广）。测试仅覆盖 sent/skip/not_sent/ambiguous 正常路径。
- **触发场景**：broker 在发送窗口（SMTP ≤30s×2 段或 executor 300s 超时 killpg）被重启/断电/OOM。
- **影响**：该日期晨间日报永久卡死 unknown，恢复需人工 rm 锁文件且无文档。
- **修复建议**：FileExistsError 分支先查 state 文件：state 缺失 → 安全可接管（删 stale 锁重试）；state=sending → 维持 unknown（模糊，拒绝正确）。或锁内写 owner 后启动时按 starttime 判定接管（对齐 inject_daily）。

### M-2 radar_notify.py 可证明未发送却归 unknown（MED · A/C 分歧记录）

- **证据**：state="sending" 写于 95 行，subprocess 起于 98 行。崩溃落在取锁（78）后、写状态（95）前：state 缺失 ⟹ 发送器从未启动 ⟹ 可证明未发送；但下次运行走 80-86 行归 unknown 并永久拒绝，与 SOL 报告根因表"只恢复能够证明尚未发送的失败"（L32）直接矛盾。SOL 报告 §5（L115-116）同时明写"锁冲突仍视为 unknown"——实现与 §5 一致、与根因表原则冲突。
- **分歧记录**：C 子树认为状态机拒绝与 at-most-once 设计一致、缺口只在残留治理（即 M-1）；A 子树认为对"state 缺失"这一可证明子集拒绝恢复违反报告自述原则。两者并存：修复 M-1 的"state 缺失→安全接管"方案同时消除本条的实质后果。
- **触发场景**：崩溃恰落在 78-95 行的毫秒级小窗口（M-1 的窄子集）。

### M-3 validator 静默跳过（MED · 三视角命中，codex 原 HIGH 裁定 MED）

- **证据**：executor.py:200 `elif spec.required_outputs:` 是 `validate_task_outputs` 唯一调用点；validator 调用（137-138）在其内部。taskfile.py:84-86 仅白名单校验，无 validator⟹required_outputs 耦合约束（93-97 行仅约束 json/validation_output）。A1 实测：validator-only 卡 status=done、output_validation=not_configured。
- **触发场景**：手写任务卡/未来模板只写 validator 忘写 required_outputs。现役四模板与 tasks/ 6 卡均双声明——当前不可达，属契约缺口。
- **裁定理由**：codex 定 HIGH 是因为"exit 0 即成功"修复被绕过；统一裁定 MED 因为现网模板全部合规、触发需作者失误，且后果为校验缺失而非数据损坏。
- **修复建议**：taskfile 解析期强制 validator ⟹ required_outputs 非空（镜像 93-95 行同款约束，1-2 行）。

### M-4 send_email.py 可重试拒信永不重试（MED）

- **证据**：send_email.py:46-51 `with s: s.sendmail(...)` 的 `except Exception` → 打印后 return 1。SMTPRecipientsRefused(550)/SMTPDataError(552)/SMTPSenderRefused 均并入。radar_notify.py:109-125 对非 10 退出码归 unknown 拒绝重试。
- **触发场景**：QQ 邮箱配额瞬时拒信（552）、451 类临时拒信 → 当日日报永久丢失。550 永久拒信重试也无益，但 552 类放弃重试是真实损失，与"可证明未发送应可重试"原则不符。
- **修复建议**：区分确定性拒信（SMTPRecipientsRefused/SMTPDataError 捕获 → exit 10 + 原因）与连接中断类模糊失败（保留 exit 1），无需改 notify 状态机。

### M-5 inject_daily.sh 非 EEXIST mkdir 失败死循环（MED）

- **证据**：48 行 `while ! mkdir "$marker" 2>/dev/null`；循环体 49-54 空 owner 重试 20 次（~1s）；随后 stale 接管分支 76-85 因 old_owner 空（marker 不存在）不满足 → 87 行 `mv "$marker" "$stale" 2>/dev/null` 静默失败（`if` 条件内，`set -e` 不救）→ 回到 48 行无限循环。
- **触发场景**：12 行 `mkdir -p` 成功后磁盘才不可写（SD 卡写满/EIO/RO 重挂）→ 当晚注入失败、雷达漏跑，仅 systemd oneshot 超时兜底。
- **修复建议**：循环内 `[ -d "$marker" ] || { echo "marker unavailable"; exit 1; }` 区分 EEXIST 与其他错误（1-2 行）。

### M-6 deploy_broker.sh 门禁→restart TOCTOU（MED · 偏轻）

- **证据**：门禁于 28 行（PREFLIGHT）执行、`systemctl restart` 于 72 行，之间 35-71 行多轮 scp/ssh/systemctl，旧 broker 全程在跑（67 行 enable --now 对 active service 是 no-op，注释自认）。
- **触发场景**：部署窗口恰逢 23:30 注入或人工投卡，队列状态变化可绕过门禁；重启后 recover_running→failed→requeue 使旧卡（无 required_outputs）跑一次旧单体流程。
- **影响**：后果有限（一次旧流程运行，无数据损坏），触发面窄。B4 独立将"预检→inject 上传间 cron 注入"同族窗口判 LOW（秒级、手工部署、报告未声称持续门禁）——两窗口同属"快照式门禁"固有语义，A3 定 MED 系考虑窗口时长（分钟级多轮 ssh）与旧流程重跑。
- **修复建议**：门禁通过后、覆盖在役文件前先 `systemctl stop`（或 restart 前置），窗口归零（1 行移位）。

### M-7 check_skills.py RecursionError traceback 泄漏（MED）

- **证据**：220 行 `json.loads` 深嵌套抛 RecursionError（RuntimeError 子类，非 ValueError），不在 222 行 except 元组 `(OSError, UnicodeError, json.JSONDecodeError, ValueError)` 内 → traceback 直达 stderr、退出码 1 而非 2。B1 实测确认子类关系。
- **触发场景**：约 20 万层嵌套 manifest（恶意或事故性）。
- **修复建议**：except 元组追加 `RecursionError`（或 RuntimeError），1 词。

### M-8 check_skills.py --lock-current 写失败 traceback（MED）

- **证据**：231-236 行 `write_text` 在 try（219-229）之外；manifest 只读属性 → PermissionError traceback、退出码 1 而非契约的 2。
- **触发场景**：仓库文件被只读属性保护时执行 --lock-current。
- **修复建议**：write 包进结构化错误处理（与 222 行同款输出），3-5 行。

### M-9 run_card.py ingest 链路 OSError 穿透（MED · 双叶子互证）

- **证据**：resolve_ingest_engine 的 try（173-177）只包 json.loads + validate_manifest；191 行 `inspect_skill` 在 try 外，其内部 `_skill_digest` 的 `read_bytes`（check_skills.py:123）抛 OSError 不被 do_ingest 的 `except ValueError`（245）捕获 → 生产 ingest 链路 traceback、退出码 1 而非 HARD/2。B2 模拟 PermissionError 实测 UNCAUGHT traceback。
- **触发场景**：contract 文件被独占锁定（Windows 杀软扫描窗口）、权限不可读、is_file 与 read_bytes 间隙被删。
- **修复建议**：do_ingest/resolve_ingest_engine 捕获 OSError → 结构化 HARD + 退出码 2（或 inspect_skill 内部将 OSError 归 incomplete），3-5 行。

### M-10 SOL 报告 Skill 状态事实漂移（MED · 偏轻）

- **证据**：SOL 报告 137 行（验证表）"required Skill 状态为 missing"、141-145 行（遗留风险 1/2）"本机不存在 ~/.claude/skills/academic-research-engine""nature-literature-pipeline 同样未安装"。验收 agent 亲查：两 Skill 目录均在 `~/.claude/skills/` 下（entrypoints 齐全），skills.json expected_digest 仍为 null → 实跑状态为 **unlocked**（B1 实跑：actual_digest 已算出、--strict RC=1）。
- **触发场景**：任何人按报告 141-144 行执行恢复/验收步骤会被引导去找不存在的"缺失 Skill"。
- **边界说明**：门禁阻断方向仍正确（unlocked → HARD，fail-closed）；恢复动作不变（用户审查后 --lock-current --strict）。SOL 环境当日措辞可能成立，对合并后本机是事实性漂移。
- **修复建议**：勘误 137/141-145 行为"已安装、状态 unlocked"；用户提供 Skill 审查后 --lock-current --strict 解除门禁时同步更新。

### M-11 codex_modes.py 空内容壳判 valid（MED）

- **证据**：463-473 行字段校验只查 `isinstance(value, str)`，空串通过；`_normalize_confidence(0.0)` → 0.0（256-262 行，0.0≤0.0≤1.0 成立）；`_validate_evidence([])` → []（306-329 行，空数组无项可查）；无 missing/invalid → protocol status=valid → `_with_protocol_outcome` 置 status=ok（336-337 行）。
- **触发场景**：codex 输出结构完整但内容全空的互审壳（或退化输出）被当有效采信，与 SOL 报告"可修复格式错误与语义缺失必须区分"声称不符。
- **影响**：下游可见空字段，无执行面；修复小：schema 层对 claim/trigger/impact 加非空校验（3 行）。

### M-12 dispatcher 终态重放静默归档 + Windows 死循环（MED）

- **证据**：db.py:33 `INSERT OR IGNORE` 保终态行；dispatcher.py:166-168 对 `_is_terminal` 行（done/blocked/invalid、或 attempts 用尽 failed）直接 `_archive_task_file` —— 无日志、无恢复路径；97 行 `f.rename(archive / f.name)` 在 Windows 上撞同名 archive 抛 FileExistsError → one_cycle 异常 → main:284-285 捕获后整队列每 30s 重复报错循环。C3 实测 C6 复现。
- **触发场景**：任务因依赖拼错判 invalid 后修正重放同名 T-*.md（POSIX 上 rename 覆盖、任务永不再跑）；同日重注入已完成任务（inject_daily.sh:108 的 `[ -f "$task" ] && continue` 不覆盖"文件被归档后重注入"路径）。
- **影响**：Pi（Linux）上为静默归档+任务永不执行+无日志（最危险处是"静默"）；Windows 上另有开发机队列死循环。
- **修复建议**：归档前记录日志并写入归档原因；Windows rename 撞名改为幂等处理（先删同名或捕获 FileExistsError）。

## 声称 vs 实现偏差清单

1. **notify 恢复原则**：SOL L32"只恢复能够证明尚未发送的失败" vs radar_notify.py:80-86"锁在+state 缺失（可证明未发送）归 unknown 拒恢复"（M-2）；L115-116 §5 又明写"锁冲突仍视为 unknown"——报告内部两处表述与实现之间呈三方张力，需在修复时统一口径。
2. **Windows 路径拒绝**：SOL §2"拒绝绝对路径、反斜线、`.`/`..`" vs check_skills.py:38-47 在 Windows 漏检 `/abs`（drive-relative 根）与 `C:foo`（drive-relative）两类（H-1）。同一段代码在 Linux 完全成立——平台分叉是偏差根因。
3. **traceback 泄漏承诺**：SOL §2"不泄漏 traceback"存在三处空洞——RecursionError（M-7）、--lock-current 写失败（M-8）、run_card ingest 的 inspect_skill OSError（M-9）。三处均为"except 元组/范围设计时只覆盖了预想错误类型"。
4. **Skill 安装状态漂移**：SOL 验证表与遗留风险 1/2 的"missing/未安装"与合并后本机"已安装、unlocked"不符（M-10）。方向正确、事实过时。
5. **"exit 0 即成功"修复的未声明前置条件**：SOL L28 声称"由执行器在终态前校验 artifact"，未声明 validator 仅在 required_outputs 非空时生效（M-3）——声称覆盖全部任务，实现覆盖声明了 required_outputs 的任务。
6. **send_email 边界**：M-4 是偏差清单 1 的下游实例——"可证明未发送"（服务器明确拒收）被实现归为"模糊 unknown"，其中 552 配额类本可重试。

## 审查覆盖与局限

- **覆盖到位**：SOL 提交 35 文件中，broker 全部运行模块（artifact_validators/radar_render/radar_notify/inject_daily/migration_guard/dispatcher/db/send_email/executor/taskfile）、scripts 全部（check_skills/run_card/codex_modes/deploy_broker/skills.json）、四阶段模板均有叶子审查；测试文件 test_executor/test_radar_pipeline/test_dispatcher/test_inject_daily/test_migration_guard/test_check_skills/test_deploy_broker/test_run_card/test_codex_modes/test_prompt_quality 有叶子过目。
- **无人完整过目的文件**：
  - `orchestra/broker/tests/test_taskfile.py`（178 行改动）：无叶子系统审查，仅 codex 交叉验证顺带读 136-256 行；1-135 行（parse 基础/depends_on/mode-detail 测试）无人复核。验收 agent 抽查发现：**validator 字段解析路径（taskfile.py:84-86）在测试中零覆盖**（无任何 test_validator_* 用例），且 `test_model_field_not_validated`（249 行）将"model 不校验"钉为现状（与 C-L3 呼应）。
  - `orchestra/README.md`：SOL §6"README 与当前实现一致"声称无人核对。
  - 根 `README.md`：仅 codex 顺带读 18-42/82-91 行。
- **A2 叶子 LOW/观察原文缺失**：A2 的 5 LOW + 2 观察（radar_render/notify 健壮性类）协调者催收两次未回收，仅 2 条 MED 有独立亲核；本报告 LOW/观察清单对该区域为保守口径，可能存在与 C 子树观察的重复未被去重。
- **codex leaf 事故说明**：第 1 次 run codex 本体成功但 `print(out_json)` 于 Windows GBK 控制台崩溃（exit 1，非认证/超时）；第 2 次设 `PYTHONIOENCODING=utf-8` 成功（status=ok，320s/47 events）。运行期间遭遇 5 次 reconnect timeout（WebSocket→HTTPS fallback）、MCP 审批策略拦截 codegraph（退化为 rg/Get-Content）。codex 的 4 条实质发现（validator 门/M-3、patch 路径/L-3、taskkill/L-2、TOCTOU/L-4）方向全部属实，无假阳性。
- **未做**：不重跑测试套件（合并版 102/154 已由子树实跑）；未在 4B 上验证部署与通知链路（SOL 遗留风险 3 仍挂账）。

## 修复建议优先级

**小包 A（可直接修复，合计约 15-20 行代码 + 补测试，建议一次提交）**：
- H-1：check_skills 拒绝条件加 `path.drive or path.root`（1 行）+ 3 个探针测试。
- M-1/M-2：notify FileExistsError 分支先查 state——缺失→安全接管删锁重试；sending→维持 unknown（1 次修复覆盖两窗）。
- M-3：taskfile 解析期强制 validator ⟹ required_outputs 非空（镜像 93-95 行）。
- M-4：send_email 区分确定性拒信（exit 10）与模糊失败（exit 1）。
- M-5：inject_daily 循环内 `[ -d "$marker" ] || { echo; exit 1; }`。
- M-7/M-8/M-9：三处 traceback 空洞（except 加 RecursionError；write_text 入结构化处理；run_card 捕 OSError → HARD/2）。
- M-11：codex_modes 对 claim/trigger/impact 加非空校验。
- M-12：dispatcher 归档加日志 + Windows rename 幂等化。
- M-6：deploy 门禁后先 `systemctl stop`。
- M-10：SOL 报告 137/141-145 行勘误（或与 --lock-current 解除门禁同步更新）。
- 补测试：make_spec 加 validator 参数 + executor→validator 接缝用例；validate_fetch/validate_render 负向分支（14 个拒绝分支）；test_check_skills 加 stderr 断言；test_deploy_broker 成功路径行为测试；test_taskfile 补 validator 用例。

**挂账 B（Pi 部署窗口项，与既有挂账合并）**：
- 小包 A 修复后的 Pi 侧部署验证（SOL 遗留风险 3 未变）。
- notify 崩溃残留演练（kill 于发送窗口 → 验证接管/清理路径）。
- inject_daily 在 4B 真实 /proc 的首跑（starttime 路径）。
- A2 缺失的 5 LOW + 2 观察原文回收补录（可随手完成）。
