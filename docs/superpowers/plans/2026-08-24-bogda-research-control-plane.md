# Bogda Research Control Plane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把Bogda从B-lite执行与评审控制台扩展为具有三档科研自主模式、可恢复人工检查点、按任务科研协调Agent、真实Prefect影子控制和按需唤醒宿舍Worker的科研控制面。

**Architecture:** Prefect继续是唯一队列和执行状态源；Bogda只增加项目策略、冻结后的运行上下文、版本化科研决策和薄适配。Pi只常驻确定性服务，不运行通用LLM循环；科研协调Agent由Flow按任务启动，并在预算、工具和迭代上限内工作。

**Tech Stack:** Python 3.11–3.13、Prefect 3.8.3、FastAPI/Pydantic、React/TypeScript/Vite、pytest、Vitest、Playwright、Windows 10 Power Agent、WSL2 Prefect Worker。

**Spec:** `docs/superpowers/specs/2026-08-24-bogda-architecture-design.md`；控制台边界见 `docs/superpowers/specs/2026-08-24-bogda-console-design.md`。

## Global Constraints

- Gate 6的24小时窗口内不得修改RK3528上的Bogda、Prefect、systemd、认证或端口。
- Prefect是唯一执行状态源；不得增加第二套任务队列或Flow Run状态机。
- Prefect `Completed`只表示执行与必要产物完成，不表示科研结论成立。
- 模式修改只影响随后创建的运行；每个Run必须冻结当时的有效模式。
- `autonomous`仍不能自行批准科研结论、对外发布、新增采购或突破预算。
- Pi不得运行无人监督LLM agent loop；宿舍机不得因“管家常驻”而被禁止休眠。
- 第一轮不做全文证据扫描、通用插件系统或为未知未来输入增加复杂校验。
- 每项生产写能力必须先在mock或隔离的精确allowlist环境验收。

## 停机权与节奏契约

控制面可以推进任务，不能给科研工作定罪。本契约约束 Task 4、5、7、9；不新开 ARIS 依赖或 skill 搬运任务。硬件换箱、网口和供电由 owner 处理，不进入本计划的代码任务。

### 门类型

每个停机/验收条件必须标成恰好一类。复合条件拆开，禁止把 B 收成 A 后自称安全。

| 类型 | 判据 | 谁可以判 |
|---|---|---|
| Type-A（执行/客观） | 无品味的脚本也能给出同一答案：exit code、文件存在、队列抽干、预算计数触顶、审查器**被调用过** | Flow / 确定性校验器；执行器可自检 |
| Type-B（质量/正确/接受） | 需要领域判断：计划是否够、claim 是否成立、能否当结论、能否投稿 | 只能进入人工检查点。跨模型意见可当证据 Artifact，**不得**把 `scientific_status` 写成 `accepted` |

Type-A 通过只允许把 Prefect 执行态标为 `Completed`（且必要产物存在）。`scientific_status` 的 `accepted` / `rejected` / `inconclusive` 全是 Type-B。

### 恢复态

运行与阶段状态拆成 `done` 与 `accepted`：executor 写完产物是 `done`；对应 Type-B 门通过才是 `accepted`。resume 必须重开任何 `done` 但未接受的阶段，不得把中断当成已经审过。

### 预算与白名单（Task 5 骨架，Task 9 强制）

协调器与 `autonomous` 循环受四墙约束：`max_steps`、`max_model_calls`、`max_cost_cny`、允许实验类型。Task 9 另加路径 `edit-whitelist`：循环只能改名单内路径。任一越界只许暂停等待人，不许自批、不许破四类人工保留权（结论、对外发布、新增采购、破预算）。

### 时钟不当陪审团

Wake Bridge、健康/快照 timer、雷达调度只看 Type-A 外部事实（Worker 在线、队列非空、文件新鲜、预算剩余）。禁止用 interval / `/loop` 重跑 Type-B 技能。心跳可以 nudge 卡住的执行，不能 acquit。

### 本计划不列入

- 接入 ARIS 仓库或搬运其 skill 集
- overnight 全自动写论文流水线、默认 `AUTO_PROCEED`
- 控制面 NPU 推理、把 NPU 写成 `resource_class`
- OpenClaw / 7×24 管家 Agent / GPU watchdog / 多卡 wave 队列
- 为换箱或双网口编写采购/驱动任务（owner 硬件线）

待决（2026-08-28 owner，不开 Task 10）：需要**触发式 agent**——有事才拉起，闲时休眠不烧 token，替人做一部分简单决定。**dsh 能做什么要单独设计**，不与「触发式」混成已定方案。禁止常驻会话。

## Delivery Map

| 波次 | 交付 | 运行态影响 |
|---|---|---|
| W1 | 模式策略、冻结语义、3101本地切换 | 仅本地，不接Pi |
| W2 | `manual`/`supervised`人工检查点 | 本地Prefect测试服务器 |
| W3 | 按任务科研协调Agent | mock LLM + 本地Flow |
| W4 | 3101真实Prefect S1/S2 | 需Gate 6和owner批准 |
| W5 | Wake Bridge、Power Agent、笔记本Worker | 当前笔记本模拟 |
| W6 | 宿舍机CPU接入与工作流迁移 | 硬件到位后 |
| W7 | `autonomous`受限循环和3100切换设计 | 前六波证据齐全后 |

---

### Task 1: 项目自主模式策略与解析（✅ `codex/bogda-autonomy-policy`）

**Files:**
- Create: `bogda/src/bogda/policy/store.py`
- Create: `bogda/src/bogda/policy/models.py`
- Modify: `bogda/src/bogda/contracts/models.py`
- Test: `bogda/tests/policy/test_store.py`

**Interfaces:**
- Produces: `AutonomyPolicy(global_default, project_overrides, revision)`；`resolve_mode(project_id) -> ResolvedAutonomyMode`；原子替换的单文件JSON策略存储。
- Constraint: 只保存策略，不保存Flow Run状态；未知项目使用全局默认；只接受`manual|supervised|autonomous`。

- [x] 写失败测试：默认模式、项目覆盖、revision冲突、损坏文件fail-closed。
- [x] 运行 `uv run --python 3.11 pytest tests/policy/test_store.py -v`，确认因模块不存在而失败。
- [x] 实现最小Pydantic模型和单机文件存储；写入采用临时文件后同卷替换，不增加数据库。
- [x] 重跑聚焦测试和 `uv run --python 3.11 pytest -m "not integration" -q`。
- [x] 提交 `feat(bogda): add autonomy policy resolution`。

### Task 2: 创建运行时冻结有效模式（✅ 合并于Task 1原子提交）

**Files:**
- Modify: `bogda/src/bogda/control/cli.py`
- Modify: `bogda/src/bogda/flows/shell_job.py`
- Modify: `bogda/src/bogda/contracts/models.py`
- Test: `bogda/tests/integration/test_vertical_slice.py`
- Test: `bogda/tests/control/test_cli.py`

**Interfaces:**
- Consumes: `resolve_mode(project_id)`。
- Produces: `JobRequest.autonomy_mode`在提交前解析并冻结；Flow只读取请求中的值，不回读可变策略。

- [x] 写失败测试：提交前后修改策略不改变已创建Run；新Run采用新revision。
- [x] 运行聚焦测试并确认旧代码固定`supervised`导致失败。
- [x] 在控制层解析模式并将`policy_revision`写入请求；删除demo硬编码模式。标签投影留给真实Deployment提交接口，当前纵向切片没有Deployment标签写入点。
- [x] 运行Bogda全量测试和本地Prefect纵向切片。
- [x] 以一个原子提交交付策略与冻结语义，避免中间提交产生“有策略但运行不冻结”的状态。

### Task 3: 3101自主模式API与切换控件（✅ `codex/bogda-console-autonomy-control`）

**Files:**
- Modify: `bogda-console/src/bogda_console/contracts/models.py`
- Create: `bogda-console/src/bogda_console/adapters/policy.py`
- Modify: `bogda-console/src/bogda_console/api/routes.py`
- Modify: `bogda-console/src/bogda_console/services/commands.py`
- Create: `bogda-console/frontend/src/components/AutonomyModeControl.tsx`
- Modify: `bogda-console/frontend/src/pages/OverviewPage.tsx`
- Modify: `bogda-console/frontend/src/pages/RunDetailPage.tsx`
- Test: `bogda-console/tests/backend/test_policy_commands.py`
- Test: `bogda-console/tests/frontend/autonomy-mode.test.tsx`

**Interfaces:**
- Produces: `GET /api/v1/autonomy-policy`和带`expectedRevision`的`PUT /api/v1/autonomy-policy/{projectId}`；成功后返回权威快照。
- UI copy: `手动`、`监督执行`、`范围内自主`；确认框明确“只影响后续新任务”。

- [x] 先写API和UI测试，包括只读profile禁用、revision冲突、作用域提示；接管时补充了真实策略后端不可用仍显示只读面板的失败测试并完成红绿循环。
- [x] 复核Grok遗留实现并补齐端口边界、可见作用域标题和只读降级语义。
- [x] 实现mock策略适配器、未接线真实适配器、命令服务和三段控件；`real-readonly`及`allowlisted-test`继续返回`canSetAutonomyMode=false`。
- [x] 导出OpenAPI并通过contract、build、后端、前端及完整Playwright矩阵。
- [x] 提交 `feat(console): add guarded autonomy controls`。

### Task 4: `manual`与`supervised`人工检查点

**Files:**
- Create: `bogda/src/bogda/contracts/decisions.py`
- Create: `bogda/src/bogda/flows/research_checkpoint.py`
- Modify: `bogda/src/bogda/flows/shell_job.py`
- Modify: `bogda-console/frontend/src/pages/RunDetailPage.tsx`
- Test: `bogda/tests/flows/test_research_checkpoint.py`
- Test: `bogda-console/tests/frontend/checkpoints.test.tsx`

**Interfaces:**
- Produces: 版本化`ResearchDecision(kind, verdict, rationale, decided_by, decided_at)` Artifact；检查点类型固定为`plan_approval|experiment_approval|scientific_review`。
- Semantics: `manual`每一步进入检查点；`supervised`只在计划、关键实验和科学判断暂停；拒绝后Flow终止但不伪造系统失败。
- Gate contract: `plan_approval`、`experiment_approval`、`scientific_review` 均为 Type-B；产物存在与命令成功是 Type-A，不得单独结束科学判断。阶段恢复区分 `done` / `accepted`。跨模型评语若写入 Artifact，不能把科研状态标为 `accepted`。

- [x] 写失败测试覆盖批准恢复、拒绝终止、重复提交冲突和重启后仍可恢复。
- [x] 写失败测试：Type-A 完成不能把 `scientific_status` 从 `unreviewed` 改成 `accepted`；resume 时 `done` 未接受的检查点仍暂停。
- [x] 运行测试确认检查点Flow不存在。
- [x] 用Prefect原生暂停/恢复语义和Artifact实现，不创建本地状态机。
- [x] 在3101详情页展示证据、影响与批准/拒绝按钮；不得提供列表一键批准。
- [x] 运行Bogda集成测试、控制台backend/frontend测试和构建。
- [x] 提交 `feat(bogda): add human research checkpoints`。

### Task 5: 按任务科研协调Agent（先实现supervised）

**Files:**
- Create: `bogda/src/bogda/agents/contracts.py`
- Create: `bogda/src/bogda/agents/coordinator.py`
- Create: `bogda/src/bogda/flows/research_cycle.py`
- Create: `bogda/tests/agents/test_coordinator.py`
- Create: `bogda/tests/flows/test_research_cycle.py`

**Interfaces:**
- Produces: `ResearchPlan`、`ExperimentProposal`、`AgentBudget(max_steps, max_model_calls, max_cost_cny)`和`CoordinatorResult`。
- Agent可调用工具必须由任务允许列表提供；第一版只输出计划和实验建议，不自行修改代码、采购或发布。
- Gate contract: 协调器可 DRIVE（写计划、提实验、耗预算）；Type-B 一律变成检查点。预算四墙任一触顶进入人工检查点，不进入自批循环。

- [x] 写mock-model失败测试：预算耗尽、未知工具、无必要产物、请求关键实验批准。
- [x] 写失败测试：模型输出“计划已足够/结果支持结论”不能跳过 Type-B 检查点或改写 `scientific_status`。
- [x] 运行测试确认agent包不存在。
- [x] 实现有限状态协调器；每一步写结构化Artifact，达到任一预算上限立即进入人工检查点。
- [x] 实现`supervised`研究Flow：目标→计划→人工批准→执行→结果摘要→科研评审。
- [x] 使用假模型和临时目录完成集成测试，确认不存在无限循环。
- [x] 提交 `feat(bogda): add supervised research coordinator`。

### Task 6: 真实Prefect S1与精确allowlist S2

**Files:**
- Modify: `bogda-console/README.md`
- Create: `bogda-console/docs/real-shadow-runbook.md`
- Modify: `bogda-console/tests/integration/test_local_prefect.py`
- Create: `docs/reports/2026-08-28-bogda-console-real-shadow.md`

**Interfaces:**
- S1只读连接Pi Prefect；S2只允许专用测试Deployment、schedule、queue和pool ID。
- 前置条件: Gate 6通过，owner分别批准S1和S2；不得将S2 allowlist指向Orchestra或生产研究任务。

- [ ] 在本地Prefect harness补充模式读取、检查点和评审追加集成测试。
- [ ] 先运行S1，只比较3101与Prefect权威数据并保存差异。
- [ ] owner批准S2后，创建专用测试资源并填写精确allowlist。
- [ ] 验证提交、取消、暂停/恢复、模式修改、检查点和评审；逐项回读权威状态。
- [ ] 保存3100前后可达、Pi资源和无生产资源变更证据。
- [ ] 提交 `docs(bogda): record real console shadow evidence`。

### Task 7: Wake Bridge、Power Agent协议和笔记本模拟

**Files:**
- Create: `bogda/src/bogda/power/protocol.py`
- Create: `bogda/src/bogda/power/wake_bridge.py`
- Create: `bogda-power-agent/`（独立Windows服务项目，具体语言在其子spec批准后确定）
- Test: `bogda/tests/power/test_wake_bridge.py`
- Create: `docs/superpowers/specs/2026-08-28-bogda-power-agent-design.md`

**Interfaces:**
- Wake Bridge只观察`dorm-x86`待领取Run、Worker在线状态和冷却时间；只发WoL，不修改Flow状态。
- Power状态固定为`sleep|compute|gaming|maintenance`；科研模式与电源模式互不推断。
- Gate contract: Wake Bridge 与健康探测只做 Type-A（在线、待领取、冷却）。直连网段与 Wi-Fi 上路由 owner 准备；软件只假设两条通路可达，不把双 RJ45 写成硬依赖。timer 不得对科研结论或审查技能开火。

- [ ] 先编写并批准Power Agent子spec，明确认证、休眠锁、游戏切换和崩溃恢复。
- [ ] 为Wake Bridge写失败测试：离线有任务只唤醒一次、冷却期去重、在线不唤醒、失败保留Scheduled/Late。
- [ ] 实现纯协议和mock适配，在当前笔记本验证，不要求7×24。
- [ ] 验证gaming停止领取新任务但不强杀正在运行任务，任务结束后释放休眠锁。
- [ ] 保存笔记本模拟证据；不得在此任务启用GPU队列。
- [ ] 提交 `feat(bogda): add tested dorm wake protocol`。

### Task 8: 宿舍CPU Worker与真实工作流迁移

**Files:**
- Create: `docs/superpowers/plans/2026-09-01-bogda-dorm-worker.md`
- Create: `docs/reports/2026-09-01-bogda-dorm-worker-acceptance.md`
- Modify: 每个获批迁移工作流对应的`bogda/src/bogda/flows/`文件
- Test: 每个工作流对应的`bogda/tests/flows/`测试

**Interfaces:**
- 前置条件: 宿舍机到位；Win10/WSL2、Tailscale、直连网口和WoL分别验收。
- CPU队列先开放且宿舍Worker总并发固定为1；GPU队列在显卡和CUDA栈验收前保持暂停。

- [ ] 编写宿舍Worker独立计划并记录机器、网络和回退基线。
- [ ] 验证离线排队、WoL、上线领取、attempt产物、结束休眠和gaming模式。
- [ ] 选择一个低风险真实科研Flow迁移，双跑并比较RunResult，不迁移在途任务。
- [ ] 雷达、通知、备份和其他研究Flow逐类重复“契约测试→shadow→owner批准→切换”。
- [ ] 当3101真实shadow与回退证据齐全后，另写3100切换spec；本任务不直接改端口。
- [ ] 提交每类工作流独立验收记录，保持可逐项回滚。

### Task 9: 受限`autonomous`循环

**Files:**
- Modify: `bogda/src/bogda/agents/coordinator.py`
- Modify: `bogda/src/bogda/flows/research_cycle.py`
- Modify: `bogda-console/frontend/src/pages/RunDetailPage.tsx`
- Test: `bogda/tests/agents/test_autonomous_budget.py`
- Test: `bogda/tests/flows/test_autonomous_cycle.py`

**Interfaces:**
- Consumes: 已稳定的检查点、预算和宿舍执行链。
- Produces: 在预设`max_steps`、`max_model_calls`、`max_cost_cny`和允许实验类型内提出并执行后续实验；越界一律暂停等待人。
- Gate contract: 强制 `edit-whitelist`；循环可在四墙内 enqueue 下一枪（Type-A 完成即可继续），不可把 Type-B 门判成通过。默认全局模式仍为 `supervised`；3101 开放“范围内自主”需 owner 显式批准。

- [ ] 写性质测试：任意模型输出都不能突破四类人工保留权或预算上限。
- [ ] 写失败测试：白名单外写盘被拒；timer/heartbeat 触发不能把 `scientific_status` 标为 `accepted`。
- [ ] 写确定性场景测试：阴性结果迭代、无信息增益停止、预算耗尽、采购请求和发布请求。
- [ ] 实现最小循环，不增加长期记忆服务或通用插件框架。
- [ ] 在隔离项目跑完整演练并由独立模型复核证据。
- [ ] owner显式批准后才让3101开放“范围内自主”；默认仍为`supervised`。
- [ ] 提交 `feat(bogda): add bounded autonomous research cycle`。

## Review and Release Gates

每个Task必须单独通过：聚焦测试、相关项目全量测试、`git diff --check`、独立代码审查。Task 3、4、6和9还必须完成浏览器交互与可访问性验收。Task 6以后任何真实设备或生产写操作都需要owner当次明确批准。

不得将“计划已写”“mock通过”“Gate 6通过”描述为完整Bogda已经完成。正式产品完成要求Task 1–8完成；Task 9是全自动能力的最终开放门。
