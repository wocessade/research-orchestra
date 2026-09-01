# Bogda 必要延期工作登记册

状态：活文档
建立日期：2026-08-29
适用范围：Phase C 之后的 Stage D、Stage E、Gate 6 与正式切换

## 使用规则

这里只登记“目标要成立就必须完成、但当前阶段有意不做”的事项，不收集泛泛优化或不确定愿望。每次阶段验收必须：

1. 关闭已经完成的条目并附 commit/报告；
2. 把新发现的必要延期项加入表中；
3. 不得用“以后再说”替代触发条件和验收标准；
4. 未经 owner 明确授权，不把延期项偷渡进生产环境。

## 已承诺的当前续作（不是无限期延期）

| ID | 工作 | 当前承诺 | 完成证据 |
|---|---|---|---|
| NOW-01 | Phase C Task 5–6：Prefect 挂起边界、fake 集成验收与维护者交接 | 已完成本地交接；真实部署/生产验证仍见 DEF-02/03/12 | [Phase C acceptance 报告](2026-08-29-bogda-paid-model-runtime-acceptance.md)、一次最终 Bogda full suite、Orchestra 兼容测试 |
| NOW-02 | Stage D：owner 可操作的前端裁决面与状态可视化 | **本报告关闭 mock 剖面**；真实 usage/调度仍见 DEF-01/03 | [Stage D acceptance](2026-08-29-bogda-owner-console-acceptance.md)、浏览器/前端/契约矩阵 |
| NOW-03 | Stage E：运行接线与迁移前验收 | Task 1–4：ledger、paid-call+SQLite、官方余额 **live GET**、本机 Flash/Pro dsh stdout `pong`。缺 `usage.json` 精确对账。真 suspend 未做。Gate 6 **已通过**；Gate 7 的 3101 real Prefect S1 只读与 S2 exact-allowlist 专用写入均已通过，仍不代表生产切换 | [Stage E 开工](2026-08-30-bogda-stage-e-start.md)、[Gate 7 entry](2026-09-01-bogda-gate7-entry-decision.md)、[S1](2026-09-01-bogda-console-s1-real-shadow.md)、[S2](2026-09-01-bogda-console-s2-allowlisted-shadow.md) |
| NOW-04 | Gate 6 收尾 | **已完成。** trial `20260830T154019Z` 覆盖 24h08m56s，275 个样本零缺口、零 API/DB/OOM 失败；受控 reboot、正常 fsck/mount、独立 restore 与最终日志复核全部通过 | [最终验收](2026-08-31-bogda-rk3528-gate6-final-acceptance.md)、[e2fsck/重试日志](2026-08-30-bogda-rk3528-e2fsck-remediation.md) |
| NOW-05 | Runner 开工包本地准入 | `admit_runner_packet` + 6 个契约测试已过。未接线到 Prefect worker / 3101 | [spec](../superpowers/specs/2026-08-30-bogda-runner-dsh-design.md) §5.7、[计划](../superpowers/plans/2026-08-30-bogda-runner-packet.md) |

## 必要延期项

| ID | 必要结果 | 当前不做的原因 | 启动触发 | owner/前端操作面 | 目标阶段与验收 |
|---|---|---|---|---|---|
| DEF-01 | 接入真实只读 usage/balance API，包括鉴权、币种、120 秒新鲜度与不可达 fail-closed | **本地 3101 契约/API/UI 已接线**；live GET 曾于 2026-08-30 成功，但 Mission 048 未再次调用真实来源 | 在 real-readonly profile 配置 `DEEPSEEK_API_KEY` 后做只读验收 | 模型策略页显示账户余额、快照时间、来源、新鲜度和独立错误状态 | Stage E；本地测试/构建与 mock UI 已闭环；生产只读验收仍待 |
| DEF-02 | 真实 dsh/DeepSeek Flash 与 Pro 最小 smoke，确认 argv、patch、`usage.json` 和 provider exact cost | argv/patch/stdout **已通**（pong）。**无** `usage.json`；owner 于 2026-08-31 明确精确 token 回执不是当前必要项 | 需要按 token 精确对账、优化历史 p90，或余额差额不足以判断实际费用时 | 结果页链接 receipt；缺失时继续显示 `usage_unknown`，不得当作免费成功 | Stage E 后续；当前保留预留、禁止同 call 自动重试的 fail-closed 行为 |
| DEF-03 | Prefect deployment、持久化结果存储与 worker 重调度的真实 suspend/resume 验证 | Gate 7 S2 已证明专用 deployment 的 submit/cancel/review 与 schedule/queue 命令；本轮专用 pool 无 worker，未产生开放 checkpoint，不能冒充 suspend/resume 或 checkpoint 裁决已验收 | 配置专用 worker、持久化结果存储与可回滚运行环境后 | 运行详情显示挂起原因、恢复条件、deployment/run 链接；开放 checkpoint 只对精确 allowlist run 显示独立裁决控件 | Stage E；worker 被释放，恢复后同一冻结 envelope 重检且只写一次 resume 事件；独立 `canDecideCheckpoint` 在真实开放 checkpoint 上通过批准/拒绝与权威回读；本轮边界见 [S2](2026-09-01-bogda-console-s2-allowlisted-shadow.md) |
| DEF-04 | usage unknown 的真实接线闭环：把 core 持久恢复状态映射到 real profile 的 owner API/窗口 | **本轮已完成 core SQLite 四状态、人工费用对账、唯一新 call id、mock API/UI 与结构化事件；尚未完成 core→console 生产 transport** | 第一条需要通过 real profile 人工恢复的 provider 调用前 | 决策中心已有“先对账、确认重试、终止”窗口；真实接线不得改变字段、revision 或禁止同 call 重试语义 | Stage E；真实 usage-unknown case 可跨重启进入窗口，动作回写 core，事件完整且同 call 不重复付费；本轮证据见 [acceptance](2026-08-31-bogda-price-aware-owner-control-acceptance.md) |
| DEF-05 | 将进程内 SingleFlight ledger、call claim、recovery case 与终态事件投递替换为跨进程原子预留/持久 outbox；预留同时持久化并校验 intent、模型层级与价格上下文 | 当前 SQLite reservation 仍跨多个提交边界，异常可能只留在进程内；仓促补丁反而会制造双事实源 | worker 并发大于 1、跨进程恢复或正式多节点执行前 | 全局策略页只展示并发/锁状态；不能提供绕过锁的普通开关 | Stage E/切换前；在每个持久化边界注入崩溃后，相同 call 不重复付费，恢复上下文不可由调用方篡改，终态事件最终且仅投递一次 |
| DEF-06 | 将已验证的峰谷计划器接入真实 scheduler/dispatcher，并提供“继续等/按高峰新预算立即跑/取消” | **本轮已完成与预计工作量、运行时长、deadline、北京时间峰谷窗口关联的纯计划器与边界测试；生产调度执行和 owner 三选一命令尚未接线** | real profile 开始自动安排付费运行前 | 创建/确认窗口需显示计划启动、当前价格窗口、预计节省、deadline 风险和 owner 三选一 | Stage E；实际 dispatcher 使用冻结计划，跨峰谷/deadline 重算可复现且不会绕过预算批准；本轮证据见 [acceptance](2026-08-31-bogda-price-aware-owner-control-acceptance.md) |
| DEF-07 | 完整 owner 前端：决策中心、创建运行、启动确认、运行详情、项目策略、全局策略 | **Stage D mock 已交付**；真实 profile 仍禁写 | Phase C 已完成；后续只补真实接线 | 明确展示三种 autonomy 合作方式、intent、Auto/Flash/Pro、预算、价格、恢复条件、日志/产物 | Stage D mock 关闭于 [acceptance](2026-08-29-bogda-owner-console-acceptance.md)；真实写入仍要 Gate 6 + S1/S2 |
| DEF-08 | 前端显式开关与不可关闭安全基线 | **Stage D mock 已交付** | 与 DEF-07 同步完成 | 可选偏好与不可关闭基线已在 `/model-policy` 分开 | 来源/修订号/恢复继承与冲突重确认已有前端+浏览器测试 |
| DEF-09 | 价格目录生命周期：到期前更新、来源审计、失效 fail-closed、前端告警 | 当前目录 `review_by=2026-09-28`，不会自动更新 | 到 review_by 前或 DeepSeek 价格变更时 | 全局策略页显示版本、来源、生效/复核日期；失效时给更新入口 | Stage E 运维；新旧版本回归、未知版本拒绝、无猜价 |
| DEF-10 | 实际消耗反馈到 workload 估算、历史 p90、安全系数和后续调用预算 | 当前只完成单次精确对账，尚未形成历史反馈闭环 | 有足够真实调用样本后 | 运行详情显示预测/实际偏差；策略页显示调整依据，不自动扩大当前预算 | Stage E 后续；偏差告警与下一次预测变化可复现 |
| DEF-11 | Orchestra → Bogda 单向生产迁移与第三维兼容映射，最终冻结 Orchestra 为只读历史 | 迁移期禁止双调度/双事实源；当前只复用契约/patch 语义 | Stage D/E 独立验收完成并由 owner 批准切换 | 切换窗口显示任务范围、兼容映射、回滚点和不可逆影响 | Gate 6/切换阶段；任务转换测试、无 Bogda runtime import Orchestra、3100/3101 事实源不冲突 |
| DEF-12 | 生产运维接线：密钥注入、systemd/worker、日志保留、备份/恢复、告警和回滚 | remount 自愈两份 unit 已于 2026-08-30 热修；仍禁止无授权 `install.sh`、改 `bogda.env`、动 live `prefect.db` | 新 Gate 6 变更窗和备份确认 | 运维窗口显示目标主机/服务/版本/回滚；敏感值永不回显 | Gate 6；runbook 演练、健康检查、回滚验证、秘密扫描通过 |
| DEF-13 | 运行产物生命周期：prompt/stdout/stderr/receipt 的权限、保留期、清理与科研可复现引用 | Phase C 只定义落盘与脱敏，没有生产保留策略 | 正式产生真实科研产物前 | 运行详情提供可点击引用和权限状态；清理必须是显式受控动作 | Stage E；保留/清理不破坏事件引用，秘密扫描与恢复抽查通过 |
| DEF-14 | 高风险科学/外部动作统一审批：结果 accepted/rejected/inconclusive、发布、采购、新增支出 | 决策跑道 mock 已有；真实科研结论仍走 RunResult 评审，不把 Prefect Completed 当成 accepted | 真实决策源接入后回归 | 每个窗口显示证据、费用/质量影响、不可逆后果和日志摘要 | Stage D mock 路径已测；生产审批仍待 Stage E |
| DEF-15 | RK3528 USB/SSD 稳定性整改并重跑 Gate 6 | **已关闭。** 静态 e2fsck 1.47.0、正常依赖 fsck/mount、remount 自愈、受控 reboot、独立 restore 和 24 小时重试均完成 | 已于 trial `20260830T154019Z` 到期后核验 | 运维证据保留目标设备、UUID、检查器版本、恢复目录与 trial 编号；通过依据不是单次 API 200 | Gate 6 于 2026-08-31 通过；证据见[最终验收](2026-08-31-bogda-rk3528-gate6-final-acceptance.md) |
| DEF-16 | 超过 20 CNY 的预算在 owner 批准后形成不可伪造、可重放审计的核心审批凭证，并允许同一冻结 envelope 继续准入 | `BudgetGuard` 已对 envelope 授权额或实际预留额 `>20 CNY` fail-closed 为 `owner_approval_required`，且运行时只能收紧该安全上限；真实 model-control/decision store 尚未接到核心 admission | 第一次需要执行 `>20 CNY` 的真实运行前 | 决策中心展示 envelope、模型、峰谷、余额和批准上限；批准后生成绑定 run/pricing/revision 的凭证 | Stage E；伪造/过期/错 run 凭证拒绝，合法凭证只消费一次，事件日志完整 |
| DEF-17 | 运行详情可读取受控的原始 stdout/stderr/结构化运行日志，而不只显示 metadata URI | 当前 UI 能看 budget events、结果版本和产物引用，但没有安全的日志内容 API；不能把 URI 引用冒充“日志已可读” | 真实 worker 产物存储与权限模型确定后 | 运行详情提供按来源/时间/级别筛选、截断提示和下载；秘密脱敏且不得任意读宿主路径 | Stage E/运维；权限、路径穿越、截断、保留期和恢复测试通过 |
| DEF-18 | 将 console 与 Bogda core 的 DeepSeek balance 解析实现收敛为一个共享适配器或由 core 暴露只读内部服务 | 3101 是独立可安装包，本轮保留端口隔离的 anti-corruption adapter；**已增加共享 versioned fixture，九类成功/失败 payload 两入口一致，重复 CNY fail-closed** | real-readonly 进入生产部署前 | 前端契约不变，只替换后端注入；不得改变余额语义或泄漏凭据 | Stage E 生产化；在共享 fixture 保持全绿的前提下删除重复 provider payload 解析，不引入相对包依赖 |
| DEF-19 | 对真实 profile 建立身份与角色边界，区分 owner、只读观察者和运维管理员 | 当前 capability 由部署 profile 控制，不是用户级授权；mock 控制完整不等于生产 RBAC 完成 | 3101 对多用户或非本机开放前 | 前端显示当前身份/角色；每个动作同时由服务端授权，不能只靠禁用按钮 | 正式切换前；越权 API 测试、审计主体、会话失效与最小权限验收通过 |
| DEF-20 | 将 capability 细化到资源/动作适用性，并为 checkpoint 引入独立 `canDecideCheckpoint` | **已关闭。** `CapabilitySnapshot` 已提供四组资源 scope 与独立 `canDecideCheckpoint`；后端仍 fresh-read Prefect 关系并作最终授权 | 已于 Gate 7 S2 触发并完成 | 专用资源按钮可用；production `pi-service/default` 禁用并显示“不在测试白名单”；前端状态不是授权来源 | [S2 验收](2026-09-01-bogda-console-s2-allowlisted-shadow.md)；负路径 403、前端适用性和直接 Prefect post-read 一致。真实开放 checkpoint 的行为验收归 DEF-03，不重开 capability 契约 |
| DEF-21 | 补齐复杂参数 schema 编辑、游标分页与过滤、OpenAPI 生成的端点/请求体类型客户端 | 当前通用参数 UI 只覆盖 primitive，列表首屏固定上限，generic client 对路径和 body 缺少静态约束 | 注册首个复杂参数 deployment 或任一列表超过当前 page limit 前 | 前端提供 schema 对应控件、下一页/过滤状态和可恢复错误，不静默截断 | Stage E；object/array/enum/nullable 契约测试、跨页不漏项、错误路径编译期失败 |
| DEF-22 | 收敛 Bogda core 与 Console 重复的公共模型/枚举为版本化契约并建立兼容性套件 | 独立安装边界合理，但手写双份字段会随演进漂移 | real profile 生产接线前，或任一公共字段/枚举再次变更时 | 前端 wire contract 保持稳定，迁移期显式显示兼容版本 | Stage E；core/console 同一 fixture 双向通过，旧版本有明确退役窗口 |
| DEF-23 | 加固低频但可达的持久化与兼容边界：policy revision 进程间 CAS、prompt archive 原子发布、Orchestra CSV 空值语义、mock Prefect idempotency、shell 缺失 `argv` 的明确错误 | 当前单进程/受控输入下不阻塞 Gate 6；合并成通用防御框架会过度设计 | 对应入口进入并发、生产迁移或外部输入前分别启动 | 仅对真实可达边界提供明确冲突/验证反馈，不增加无意义开关 | 逐项以故障注入和兼容 fixture 验收；不得用“理论不可能”替代测试，也不得吞错 |

## 明确不登记为必要目标

- DeepSeek vision、更多 provider 或任意新模型：当前没有产品需求，等真实需求再建 ADR/条目。
- 为理论上不可能的输入或平台故障添加通用恢复框架：不做；发现可达失败路径时再以测试驱动修复。
- 长期双控制台、双调度或双任务事实源：与 Bogda 下一代定位冲突，不作为过渡终态。

## 维护责任

SOL 在每个阶段结束时更新本表；任何条目只有在链接到实现 commit、测试和验收报告后才能标记完成。额度或会话中断后，下一位执行者应先读本表、当前阶段 plan 和 mission STATE，再继续工作。
