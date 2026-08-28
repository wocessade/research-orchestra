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
| NOW-02 | Stage D：owner 可操作的前端裁决面与状态可视化 | Phase C 本地合并后继续，SOL 自主裁定并本地 auto-merge | 前端测试、窗口/开关矩阵、决策中心单一事实源验收 |
| NOW-03 | Stage E：运行接线与迁移前验收 | Stage D 后继续；仍不默认授权 live spend/production mutation | 影子/强制门禁证据、回滚与运维说明 |
| NOW-04 | Gate 6 收尾 | `20260828T064220Z` 因 USB SSD 断连和 120 次 API 失败已收口为失败；新 trial 等待 DEF-15 的 owner-approved 维护 | [Gate 6 失败报告](2026-08-29-bogda-rk3528-gate6-failure.md)、新 trial 与剩余 blocker 清单 |

## 必要延期项

| ID | 必要结果 | 当前不做的原因 | 启动触发 | owner/前端操作面 | 目标阶段与验收 |
|---|---|---|---|---|---|
| DEF-01 | 接入真实只读 usage/balance API，包括鉴权、币种、120 秒新鲜度与不可达 fail-closed | Phase C 只使用 fake，避免触碰生产凭据和 3101/现网 | owner 提供/确认真实 endpoint、token 来源与只读窗口 | 全局策略页显示余额、快照时间、来源和错误；不可用时给恢复动作 | Stage E；先只读展示，再影子决策，契约测试覆盖未授权/缺字段/过期 |
| DEF-02 | 真实 dsh/DeepSeek Flash 与 Pro 最小 smoke，确认 argv、patch、`usage.json` 和 provider exact cost | 会产生真实费用，当前未获 live spend 授权 | owner 明确批准费用上限与执行时段 | 启动前确认显示模型、最高费用、峰谷窗口；结果链接 receipt/事件 | Stage E；Flash/Pro 各一次受限调用，无秘密落盘，能精确对账 |
| DEF-03 | Prefect deployment、持久化结果存储与 worker 重调度的真实 suspend/resume 验证 | Phase C 只证明代码边界；真实 `suspend_flow_run` 要 deployment 与持久化配置 | Gate 6 允许操作目标 Prefect 环境且备份/回滚就绪 | 运行详情显示挂起原因、恢复条件、deployment/run 链接 | Stage E/Gate 6；worker 被释放，恢复后同一冻结 envelope 重检且只写一次 resume 事件 |
| DEF-04 | usage unknown 的人工对账闭环：查看 receipt/产物、录入或拉取实际费用、批准重试/终止、释放或对账预留 | 当前仅有 fail-safe barrier，没有 owner 命令/API/窗口 | 第一条真实 provider 调用前 | 决策中心必须提供“先对账、确认重试、终止”，禁止无提示一键重试 | Stage D+E；所有动作写结构化审批事件，同 call 不重复付费 |
| DEF-05 | 将进程内 SingleFlight ledger、call claim 和终态事件投递替换为跨进程原子预留/持久 outbox | Phase C 明确限定单进程；过早引入数据库会增加复杂度 | worker 并发大于 1、跨进程恢复或正式多节点执行前 | 全局策略页只展示并发/锁状态；不能提供绕过锁的普通开关 | Stage E/切换前；崩溃恢复、并发相同 call、终态事件失败均不会重复付费 |
| DEF-06 | 峰谷调度器按 deadline、预计调用窗口和高峰重算预算；支持“继续等/按高峰新预算立即跑/取消” | Phase C 只有价格目录与即时 cost 计算，没有调度执行 | Stage D 创建运行窗口和 Stage E scheduler 接线同步启动 | 创建/确认窗口显示计划启动、当前价格窗口、预计节省和 deadline 风险 | Stage D+E；北京时间边界、跨峰谷、deadline 临近集成测试通过 |
| DEF-07 | 完整 owner 前端：决策中心、创建运行、启动确认、运行详情、项目策略、全局策略 | 当前 Phase C 是后端 vertical slice | Phase C acceptance 本地合并后 | 明确展示三种 autonomy 合作方式、intent、Auto/Flash/Pro、预算、价格、恢复条件、日志/产物 | Stage D；必须通过设计 spec §13/§16.4 的前端矩阵，不复制后端策略 |
| DEF-08 | 前端显式开关与不可关闭安全基线 | 后端契约已冻结，UI 尚未接入 | 与 DEF-07 同步 | 可选：自动升 Pro、低风险降 Flash、优先空闲、余额恢复自动继续、通知、继承/覆盖；不可关闭：stale fail-closed、最低余额、decide/audit 禁静默降级、unknown-usage 门禁、日志/归档/脱敏 | Stage D；来源/修订号/恢复继承与冲突重确认测试通过 |
| DEF-09 | 价格目录生命周期：到期前更新、来源审计、失效 fail-closed、前端告警 | 当前目录 `review_by=2026-09-28`，不会自动更新 | 到 review_by 前或 DeepSeek 价格变更时 | 全局策略页显示版本、来源、生效/复核日期；失效时给更新入口 | Stage E 运维；新旧版本回归、未知版本拒绝、无猜价 |
| DEF-10 | 实际消耗反馈到 workload 估算、历史 p90、安全系数和后续调用预算 | 当前只完成单次精确对账，尚未形成历史反馈闭环 | 有足够真实调用样本后 | 运行详情显示预测/实际偏差；策略页显示调整依据，不自动扩大当前预算 | Stage E 后续；偏差告警与下一次预测变化可复现 |
| DEF-11 | Orchestra → Bogda 单向生产迁移与第三维兼容映射，最终冻结 Orchestra 为只读历史 | 迁移期禁止双调度/双事实源；当前只复用契约/patch 语义 | Stage D/E 独立验收完成并由 owner 批准切换 | 切换窗口显示任务范围、兼容映射、回滚点和不可逆影响 | Gate 6/切换阶段；任务转换测试、无 Bogda runtime import Orchestra、3100/3101 事实源不冲突 |
| DEF-12 | 生产运维接线：密钥注入、systemd/worker、日志保留、备份/恢复、告警和回滚 | 当前明确禁止改生产、密钥、systemd、Prefect DB | Gate 6 变更窗和备份确认 | 运维窗口显示目标主机/服务/版本/回滚；敏感值永不回显 | Gate 6；runbook 演练、健康检查、回滚验证、秘密扫描通过 |
| DEF-13 | 运行产物生命周期：prompt/stdout/stderr/receipt 的权限、保留期、清理与科研可复现引用 | Phase C 只定义落盘与脱敏，没有生产保留策略 | 正式产生真实科研产物前 | 运行详情提供可点击引用和权限状态；清理必须是显式受控动作 | Stage E；保留/清理不破坏事件引用，秘密扫描与恢复抽查通过 |
| DEF-14 | 高风险科学/外部动作统一审批：结果 accepted/rejected/inconclusive、发布、采购、新增支出 | 不属于模型调用内核，autonomous 也不能跳过 | Stage D 决策中心接线 | 每个窗口显示证据、费用/质量影响、不可逆后果和日志摘要 | Stage D/E；审批事件、冲突修订和拒绝路径端到端通过 |
| DEF-15 | RK3528 USB/SSD 稳定性整改并重跑 Gate 6 | 失败轮发生 USB SSD 断连、ext4 journal abort、Prefect server/worker 停止；只读证据不能修复物理/运行状态 | owner 批准维护窗、设备检查、离线文件系统/SSD 健康检查和服务恢复 | 运维窗口显示目标设备、检查步骤、备份、回滚与新 trial 编号；不能把重挂载当成通过 | Gate 6；根因证据、服务恢复、全新 24h trial、每日快照、受控 reboot、独立 restore 全部通过 |

## 明确不登记为必要目标

- DeepSeek vision、更多 provider 或任意新模型：当前没有产品需求，等真实需求再建 ADR/条目。
- 为理论上不可能的输入或平台故障添加通用恢复框架：不做；发现可达失败路径时再以测试驱动修复。
- 长期双控制台、双调度或双任务事实源：与 Bogda 下一代定位冲突，不作为过渡终态。

## 维护责任

SOL 在每个阶段结束时更新本表；任何条目只有在链接到实现 commit、测试和验收报告后才能标记完成。额度或会话中断后，下一位执行者应先读本表、当前阶段 plan 和 mission STATE，再继续工作。
