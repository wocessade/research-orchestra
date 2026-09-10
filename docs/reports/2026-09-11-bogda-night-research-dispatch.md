# 2026-09-11 夜班报告 — 模型控制打通、控制面缺陷修复与首个真实科研实投

作者：协调者（夜间全权授权）
状态：全部完成并现网验证

## 1. 目标

夜间授权：把 bogda 落地跑通、前端所有功能可用、后端完整可维护、由协调者自行审批，用 bogda 的科研功能完成一次真实科研任务并交付可投稿论文（LaTeX + PDF），选题须与策略笔记方向相关、基于最新文献、不重复既有工作；中途若 bogda 出问题自行修复后继续。

## 2. 交付物

| 交付物 | 位置 |
|---|---|
| 论文（LaTeX/PDF/数据/分析/图） | `docs/papers/2026-09-context-reuse-audit/` |
| 定价目录（09-11 修正 + 09-14 Pro 退役） | `bogda/src/bogda/budget/pricing.py`（部署于 runner WSL + RK） |
| 模型策略 core 侧 | `bogda/src/bogda/policy/{models,store}.py` |
| 模型控制 console 适配器 | `bogda-console/src/bogda_console/adapters/local_model_control.py` |
| 控制面缺陷修复 | `prefect_api.py`、`services/queries.py`、`config.py`、`app.py` |
| 测试 | `bogda/tests/policy/`、`bogda-console/tests/backend/test_local_model_control.py` 等 |

## 3. 做了什么

### 3.1 定价目录按官网重订

单目录改为目录注册表：新增 `deepseek-cn-2026-09-11`（V4.1-Flash 错峰 0.02/1/4、峰时 0.04/2/8；Pro 未变）与 `deepseek-cn-2026-09-14`（09-14T12:00+08 生效，Pro 退役后按 Flash 费率计价）。解析器 `current_catalog(as_of)` 取"生效时间 ≤ as_of 的最新目录"，超 `review_by` 失败关闭；`next_off_peak_start()` 供峰谷排程；`WorkloadEstimator` 可注入目录、缺省走解析器。两台机器部署后现网验证：今日解析 09-11 目录；模拟 09-15 → 09-14 目录且 Pro 行 = Flash 行。

### 3.2 模型策略与运行准备路径打通

core 新增 `bogda.policy`：`ModelPolicyValues`/`ModelPolicy`/`ResolvedModelPolicy` + `ModelPolicyStore`（JSON 文件、revision 守卫、项目级覆盖、原子 tmp+replace、货币字段禁 float、`extra="forbid"`）。console 新增 `LocalModelControlAdapter`：策略读写、`preview_run`（层级解析/错峰排程/按 core 估算器算钱/真实余额闸门）、`confirm_preparation`（幂等落盘）、`run_budget`（先恢复后账本兜底）。开关 `BOGDA_MODEL_POLICY_PATH` 与 `model_control_enabled` 同型 fail-closed。

现网：capabilities 全绿；策略 rev 0→1 写入成功、陈旧 revision 409；`preview_run` 返回真实估算 0.40 CNY；来源显示 `catalog ready · deepseek-cn-2026-09-11`（此前界面常显的琥珀色"模型控制 · 不可用/无观测时间"消失）。

### 3.3 控制面三处真实缺陷（均属"界面有、功能不可用"）

1. **RunResult 全部 invalid**：真实 Prefect artifact 的 `data` 是 JSON 字符串，适配器按 dict 校验失败 → 所有 RunResult `availability=invalid`、评审功能整体不可用。改为先 `json.loads` 再校验（失败仍 fail-closed）。复验：run `0d36b774` 评审 POST accepted、新增产物版本，未评审 run 列表 0 → 5。
2. **来源新鲜度误报**：真实 profile 返回 `UNAVAILABLE/None`，界面据此常显琥珀色"不可用/无观测时间"。改为按已读取观测点回填 `observedAt/lastSuccessfulAt/freshness=FRESH`。
3. **有效自主模式为空**：真实 profile 的 `effectiveAutonomyMode` 为 None，改为按策略快照计算（异常吞为 None，不误报）。

### 3.4 全流程实跑（含人工审批环节由协调者按授权自行决定）

- SUPERVISED 链：submit → EXPERIMENT_APPROVAL 暂停 → console API 决定 → shell 执行（裸 API 探针）→ SCIENTIFIC_REVIEW 暂停 → 决定 → **Completed**。
- AUTONOMOUS 链：TTL 探针直通无暂停，**Completed**。
- 期间修掉一处自动化脚本缺陷：只置单个"已批准"标志会让第二个检查点悬空导致 run Crashed；改为按 `(kind, commandVersion)` 集合逐条决定后 Completed。

### 3.5 首个真实科研任务：上下文复用计量取证

选题：**能否仅凭 token 计量（cache 命中）反推上下文复用** —— 面向 AI 内容来源审计。两通道受控设计：

- **通道 A（dsh agent 编排，经 bogda 真实付费链）**：17 次调用，**17/17 命中为 0**（均值输入 16,446 tokens，合计 0.4123 CNY）。根因由会话日志定位为**系统提示含每次唯一产物路径**（`.../artifacts/{run_id}/attempt-0001`），在 4181 字符中第 172 字符即分叉 —— 结构性不可复用，非采集缺陷（provider 原始响应 `cacheReadTokens` 同为 0）。
- **通道 B（裸 API 受控探测）**：同文档复用稳定命中 **512 tokens（73.6–74.4%）**，异文档 0、跨层级 0；判定规则 7/7；TTL 探测 35 分钟后仍命中；文本相似度基线 0.000–0.051，无区分度。

论文含两通道实测表、机制证据（前缀分叉处的原文引用）、政策依据与审计模型、伦理与可复现性声明。`verify_paper.py` 结果 **hard=0 soft=0**，9 页，无 overfull。

## 4. 遗留与风险

- 论文待作者确认：单位/邮箱（`main.tex` 内 TODO；本稿按策略笔记取"新疆大学"）。
- 投稿前建议补：小时级 TTL 探测、多平台（非 DeepSeek）复现。
- 运维遗留：AtStartup 冷开机确认、宿舍–实验室跨网络实测（宿舍网络掉线不自愈，需人工，已入 lessons）。
- 模型路由未改动；全程未打印凭据。

## 5. 结论

夜间目标闭环：模型控制与运行准备路径打通、定价目录按官网重订并部署、控制面三处真实缺陷修复、首个真实科研任务实投并产出可投稿论文（LaTeX + PDF）。控制面缺陷的复验均基于真实 run 与真实端点。
