# 2026-08 输出质量改造报告

日期：2026-08-20  
状态：实现完成，提交前本地验证通过；外部 Skill 运行门禁因本机未安装目标 Skill 而按设计关闭

## 目标与范围

本轮在既有未提交改造上完成以下收口：

1. `skills.json → run_card.py ingest` 强制门禁；
2. 外部 Skill manifest 严格校验与测试；
3. Codex/雷达 Prompt 质量回归集；
4. `deploy_broker.sh` 新运行文件上传与旧雷达模板迁移；
5. README 与当前实现一致；
6. 保留并验证既有输出质量改造：任务模式、产物契约、雷达阶段化、Codex 严格协议；
7. 收口审查项：注入互斥与崩溃恢复、rank 上游闭环、通知结果分类、dual manifest 执行门禁、旧单体任务迁移门禁。

约束遵守：

- 未下载、未安装任何外部 Skill；
- 未修改外部 Skill 文件。

## 原问题与根因

| 原问题 | 根因 | 修改 | 为什么这样改 |
|---|---|---|---|
| Prompt 输出重复、结尾可预测且过短 | 生成、评分、格式化和通知被塞进单一 Prompt，同时用“一句话”“简短回答”等刚性规则压缩内容 | 引入 `mode/detail`，取消人工句数上限，要求证据、反证、不确定性和置信度；增加静态 Prompt 回归集 | 生成阶段需要保留探索空间，严格性应由 Schema 和校验器提供，而不是靠压缩自然语言 |
| 进程 `exit 0` 即被视为任务成功 | 执行器只检查进程状态，不验证 artifact 的存在、结构和语义 | 增加 `required_outputs/json_outputs/validation_output/validator`，由执行器在终态前校验 artifact | 把“程序跑完”和“结果可用”分开，避免空文件、坏 JSON 或语义失败被误报为成功 |
| Codex 输出可被宽松修复后继续成功 | 协议状态没有进入 CLI 顶层失败判断，字段类型、范围和文件 manifest 一致性不足 | 收紧 `valid/repaired/partial/invalid` 协议；`partial/invalid` 非零退出；失败保留 raw；双实现 manifest 与磁盘核对，非法时不运行任何生成代码测试 | 可修复格式错误与语义缺失必须区分，不能用解析成功掩盖不完整结果，更不能执行未通过清单门禁的生成代码 |
| 雷达单体任务难以恢复且 LLM 同时负责机械排序 | 抓取、评分、选取、渲染和通知耦合，任一步失败都会重跑全部流程，排序结果缺少确定性 | 拆成 `fetch → rank → render → notify`；render 改为确定性 Python；增加独立语义 validator | 阶段化降低重试成本，确定性算法让相同输入得到相同 Top 5 和选择轨迹 |
| 新论文评分容易隐含作者、机构、引用量和来源偏见 | 质量信号与任务相关性混在总分中，新论文又天然缺少引用数据 | 总分只由 topic/method/applied/archival 构成；novelty 仅控制探索槽位；声望和来源只保留为质量信号 | 避免对新论文和非主流来源施加隐藏先验，同时保留人工复核所需信息 |
| 通知重试可能重复发送或永久丢失 | 临时 marker 不能表达“正在发送但结果未知”，且所有非零退出都被混为模糊结果 | 持久记录 `sending/sent/not_sent/unknown`，使用锁文件；发送器明确报告未发送时进入可重试 `not_sent`，其余模糊结果进入 `unknown` 并拒绝自动重发 | 在保留 at-most-once 安全边界的同时，只恢复能够证明尚未发送的失败 |
| 依赖缺失、依赖环或上游失败会让下游永久 queued | 调度器只有“等待依赖完成”，没有图合法性和失败传播 | 增加缺失依赖与环检测，非法任务进入 `invalid`，终态失败下游进入 `blocked` | 让队列能够闭环收敛，并明确区分任务自身非法与被上游阻断 |
| result、artifact 路径和 attempt 分配存在逃逸或竞态 | 仅做字符串级路径检查，attempt 目录采用先检查后创建 | 解析期和运行期双重安全路径检查，拒绝 symlink 逃逸；attempt 用原子 `mkdir(exist_ok=False)` 分配 | 防止任务写出结果根目录，也避免并发 worker 复用同一 attempt |
| 外部 Skill 由硬编码路径直接调用，版本不可追踪 | 缺少统一 manifest、入口完整性和内容摘要门禁 | 新增严格 `skills.json`、`check_skills.py`，并让 `run_card.py ingest` 在 subprocess 前强制检查 | 外部依赖必须显式、可审计、可锁定；缺失或漂移时宁可阻断也不静默执行 |
| 四阶段模板部署可能漏文件、产生半套任务或中断旧任务 | 部署清单和注入过程都缺少完整性事务边界，迁移也未检查旧单体任务状态 | 注入采用同日期原子 marker、owner 清理和 stale 接管；owner 在 Linux 加入进程 starttime 防 PID 复用；部署先只把门禁传到 `/tmp`，预检通过后才覆盖在役文件 | 防止并发、崩溃或 PID 复用导致半发布，并保证预检失败时远端运行文件仍是部署前版本 |
| rank 产物可能脱离实际 fetch 输入 | 仅校验评分文件自身结构和摘要计数，没有验证上游候选集合 | `ranking_summary.json` 记录上游原始字节 SHA-256 和输入数量；validator 核对 SHA、数量、完整 arXiv ID 集合，并按 ID 精确比较 `title/url/categories/abstract` | 让 fetch → rank 形成可复验闭环，防止漏评、增评、字段交换/伪造或读取错误 attempt |

## 主要改造

### 1. Skill ingest 门禁

`orchestra/scripts/run_card.py` 在调用 `validate_experiment_card.py` 和
`ingest_run.py` 前读取严格 manifest，并要求：

- manifest 结构合法；
- 恰好存在一个 `academic-research-engine`；
- 该 Skill 标记为 required；
- `used_by` 显式声明 `orchestra/scripts/run_card.py ingest`；
- Skill 目录和入口存在；
- 当前契约摘要与 `expected_digest` 完全一致。

`missing`、`incomplete`、`unlocked`、`drifted` 均以 `HARD`、退出码 2
阻断 ingest，且不会启动外部脚本。`--engine-dir` 仅允许覆盖迁移/测试路径，
不能绕过 manifest 摘要。

### 2. 严格 manifest

`orchestra/scripts/check_skills.py` 新增严格 schema，拒绝：

- 根对象或 Skill 条目的未知/缺失字段；
- 空 Skill 列表、重复 Skill ID；
- 非布尔 `required`；
- 空字符串数组、重复路径；
- 绝对路径、反斜线、`.`/`..` 路径；
- 未纳入 `contract_files` 的入口；
- 非小写 64 位 SHA-256；
- 空输入/输出契约。

CLI 对 I/O、编码、JSON 和 schema 错误输出结构化 `status=invalid`，退出码 2，
不泄漏 traceback。

### 3. Prompt 质量回归

新增：

- `orchestra/scripts/tests/prompt_quality_cases.json`
- `orchestra/scripts/tests/test_prompt_quality.py`

回归集锁定以下质量要求：

- 互审必须包含证据、触发条件、影响、反证、置信度、不确定性和验证方法；
- claim 核验允许 `unsure`，保留反证和缺失上下文；
- 双实现只写 `codex_impl`，最终回复为严格 manifest；
- 雷达排名保留证据、反证、未知项和置信度，不把作者/机构声望等来源先验计入总分；
- 禁止用简单“简短回答”规则压缩必要证据。

### 4. Broker 部署与模板迁移

`orchestra/scripts/deploy_broker.sh` 现会上传：

- `artifact_validators.py`
- `radar_render.py`
- `radar_notify.py`
- `migration_guard.py`
- `nightly-radar-fetch.md`
- `nightly-radar-rank.md`
- `nightly-radar-render.md`
- `nightly-radar-notify.md`

远端部署时先只把 `migration_guard.py` 上传到 `/tmp`，由临时副本检查活动任务文件和
SQLite。若旧单体任务处于 `queued`、`running` 或尚未耗尽重试次数的 `failed`，部署在
覆盖任何线上代码、模板或 unit 前退出；只有预检通过后才上传在役文件并删除遗留
`templates/nightly-radar.md`。顺序测试锁定“临时上传 → 执行门禁 → 线上上传/迁移”。

### 5. 审查项安全闭环

- `inject_daily.sh` 用原子 `mkdir` 获取同日期 marker，owner 包含 host/boot ID/PID/starttime；
  Linux 从 `/proc/<pid>/stat` 第 22 字段核对 PID+starttime，避免 PID 复用把 stale marker
  误判为活锁；无 `/proc` 时保守回退 PID 检查。清理前核对完整 owner，崩溃后的 stale
  marker 由后续进程原子接管，已发布阶段保留并补齐缺失阶段。
- rank validator 从结果目录定位同日期 fetch，选择最新通过语义校验且 `done` 的 attempt，
  对 `input_sha256`、`input_count`、输出数量和 arXiv ID 集合做闭环校验，并按
  `arxiv_id` 精确比较 `title/url/categories/abstract` 原始字段。
- `radar_notify.py` 仅把发送器约定退出码 10 视为明确 `not_sent` 并允许重试；
  普通非零退出、既有 `sending` 和锁冲突仍视为 `unknown`。
- `codex_modes.py dual-implement` 在 manifest schema、路径、去重和磁盘文件集合全部通过前
  不调用共享测试 runner。
- deploy 的旧任务门禁从 `/tmp` 临时副本执行，且位于任何线上文件/模板覆盖之前。

### 6. README 一致性

`orchestra/README.md` 已补充严格 manifest、ingest 门禁、Prompt 回归集、
部署迁移行为和四阶段雷达说明。根 `README.md` 已更新当前测试规模、配置入口
和本报告索引。

## 验证结果

执行环境使用独立可用的 Python toolchain，避开宿主 PATH 中失效的 Python shim。

| 验证 | 结果 |
|---|---|
| scripts 全量 unittest | 154 tests，OK |
| broker 全量 unittest | 88 tests，OK |
| Python `compileall`（orchestra + usage-monitor） | 通过 |
| `bash -n`（仓库内 8 个 shell 脚本） | 通过 |
| 默认 `check_skills.py --strict` | 退出 1，required Skill 状态为 missing（符合门禁设计） |

## 遗留风险

1. 本机不存在 `~/.claude/skills/academic-research-engine`，仓库 manifest 的
   `expected_digest` 仍为 `null`；因此真实 ingest 当前会被阻断。恢复前必须由用户
   在受控环境提供并审查既有 Skill，再显式执行 `--lock-current --strict`。本轮按约束
   未下载或安装 Skill。
2. `nature-literature-pipeline` 同样未安装，但其 `required=false`，不阻断 ingest。
3. 部署脚本仅做静态和 shell 语法验证，未连接 4B 执行真实部署；远端旧模板删除、
   systemd 重启和四阶段运行仍需部署窗口验证。
4. Prompt 回归集验证关键契约词和结构，不等同于真实模型质量评测；模型升级后仍需
   用固定输入做端到端样本复核。
