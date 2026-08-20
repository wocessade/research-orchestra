# Attention Defense — Pipeline-Specific Drift Prevention

**Purpose:** 轻量级注意力防御层，解决 pipeline 特有的 5 类注意力涣散（轴遗忘、stage 决策丢失、分支遗忘、收敛循环记忆衰减、跨 stage 上下文脱节）。定义 3 个机制，每个 ≤5 秒执行成本。

**加载方式:** `manifest.yaml` always_load（每个 stage 执行时都在上下文中）。

**设计原则:** 不增加 stage 文件的认知负载，不改变现有流程结构，只在边界点插入自检。

---

## Mechanism 1: Stage Handoff Check

**触发时机:** 加载 stage 文件之前（6-Step Loading Protocol Step 3，以及每次 Step 5 gate 通过后加载下一 stage 之前）。

**执行步骤:**

```
[HANDOFF] 读 material-passport.md 的 Stage Completion Log（最近 1 条）
  → AXIS CHECK: 从 passport 取当前 axes 快照，与 session 中的 axes 对比
     → 不一致 → 以 passport 为准（axes 在 session 间可能被覆盖检测）
  → STAGE CHECK: 读上一 stage 的完成记录（做了什么 + 关键输出）
     → 确保知道"自己从哪里来"
  → 如果无上一 stage 记录（第一 stage）→ 跳过检查
```

**注意:** 这是软检查——信息不对称不阻断执行，只用于修正记忆偏差。检查结果不写入文件。

---

## Mechanism 2: Stage Completion Log

**定位:** 在 `material-passport.md` 中添加 `## Stage Completion Log` 字段，每完成一个 stage 追加一行。是 Mechanism 1 读取的数据来源。

**写入时机:** 每个 stage 的 gate 通过后，写入 `.pipeline_state.json` 的 `stage_completion_log` 字段。

**格式:**

```markdown
## Stage Completion Log
| Stage | Date | Key Output | Key Decisions |
|-------|------|-----------|---------------|
| S2    | 06-20 | 30 papers → 5 themes, gap: "X not studied in Y" | Excluded Z domain (low relevance) |
| S3    | 06-21 | Method: CNN-LSTM hybrid, ablation-ready | Chose LSTM over Transformer (data size) |
```

**写入协议:**
- 每行 ≤ 120 字符（Key Output ~60 chars，Key Decisions ~60 chars）
- Key Output = 该 stage 产出的核心结果（文件路径 + 一句话摘要）
- Key Decisions = 该 stage 做出的关键路由或设计决策（用于提醒未来的自己）
- 不要写 stage 的执行过程细节——那是 stage output 文件的内容
- 如果 stage 没有可记录的决策，Key Decisions 留空

---

## Mechanism 3: Convergence Loop Memory Card

**触发时机:** C5/T6 收敛循环的每一轮开始时（在读取评估结果之前）。

**执行步骤:**

```
[MEMORY CHECK] 读 passport 中本 stage 的 Fix Log（最近 1 轮）
  → 与当前问题列表对比
  → 如果有之前标记为 "fixed" 的问题再次出现（完全相同或极其相似）
     → 标记为 degeneration，停止循环
     → 重新评估 root cause，不是继续硬修
     → 更新 fix log：明确标注 "degeneration detected — root cause re-evaluated"
  → 无 degeneration → 继续正常循环
```

**在 C5.md / T6.md 中的体现:**

```
[在收敛循环的每一轮开始时，在读取评估结果之前]
[MEMORY CHECK] 读 passport 的 Stage Completion Log 中本 stage 的 Fix Log
  → 对比当前问题列表 → 检测 degeneration
  → 有 degeneration → 暂停循环，重新评估 root cause
  → 无 → 继续正常收敛
```

---

## 触发规则汇总

| 机制 | 周期 | 执行成本 | 写入 |
|------|------|---------|------|
| M1: Handoff Check | 每次加载 stage 前 | ~3 秒（读 1 行 + 对比） | 不写入 |
| M2: Completion Log | 每 stage gate 通过后 | ~5 秒（写 1 行） | 写入 passport |
| M3: Memory Card | C5/T6 每轮开始 | ~3 秒（读 Fix Log + 对比） | 写入 fix log |

## 与 Sustained-Development 的关系

此文件只解决 pipeline 内部的 stage-to-stage 注意力涣散。如果你同时使用 `sustained-development` skill 作为长任务 wrapper，两者的防御层是互补的：

| 场景 | 由谁防御 |
|------|---------|
| 跨 stage 轴遗忘 | attention-defense.md M1 + M2 |
| 跨 stage 决策丢失 | attention-defense.md M2 |
| 收敛循环重复修 | attention-defense.md M3 |
| 子任务方向偏离 | sustained-development BRIEF.md drift self-check |
| 上下文压缩恢复 | sustained-development C1-C5 |
| 第三方审计 | sustained-development Sentry Audit |
