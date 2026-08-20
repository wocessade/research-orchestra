# 步进模式编排器

## 概述
期刊论文步进模式：按 Core-First 顺序推进，每写完一个 §X.Y 停下来等作者核对。作者可随时指定跳到其他节。

## 核心原则：Core-First 默认，作者可重定向

学术写作有成熟的非顺序策略——核心就一条：**先写主体，后写框架**。编排器默认按此推进，但不强制。

默认顺序（Core-First Protocol）：
1. Methods（最容易，建立写作动量）
2. Results（数据驱动，自然承接 Methods）
3. Discussion（基于 Results 展开解读）
4. Introduction（必须等主体写完——否则不知道要引入什么）
5. Abstract（最后——总结全文）
6. Title

Introduction 和 Abstract 在主体完成前**不应**写——这是写作技巧，不是可选的。

作者可按需重定向（如"先写 §3.2 吧"），AI 跟随。写完当前节后，默认推荐列表里的下一节，作者确认或指定其他节。

## 状态机
OUTLINE_CONFIRMED → WRITING_§X.Y → AUTHOR_REVIEW → {APPROVED | MINOR_FIX | REJECT} → NEXT_SECTION

### 三种作者操作：
- **通过 (APPROVED)** → 该节标记完成，推荐下一节（按 Core-First），询问作者继续还是换
- **小改 (MINOR_FIX)** → 保留当前内容，按具体意见增量修改，改完后再次展示给作者确认
- **打回 (REJECT)** → 作者选择"完全重写"或"指定修改点"

### 每节写完后的提示模板：
```
✅ §X.Y [{section_title}] — 已通过

📋 已完成: §2.1, §2.2, §3.1
➡️  下一节推荐: §3.2 [{section_title}]

继续写 §3.2？还是换其他节？
```
作者可以回复"继续"/"好"（写推荐节），或指定其他节编号。

### 作者中途重定向：
写作过程中作者说"先写 §4.2"→ 保存当前进度，切换到 §4.2。写完后默认回到被中断的节。

## 第三方质量监控
每节写完后自动运行 quality_monitor.md 中的一致性检查（术语/论点/数据）。质量监控覆盖**所有已完成节之间的交叉验证**。

## 节级状态持久化
`.checkpoint/{paper_slug}/stepping_state.json`:
```json
{
  "current_section": "2.1",
  "completed_sections": ["2.1", "2.2", "3.1"],
  "current_step": "author_review",
  "pending_review": true,
  "recommended_next": "3.2",
  "interrupted_section": null
}
```

- `completed_sections`: 已完成节列表
- `recommended_next`: 按 Core-First 推荐的下一节
- `interrupted_section`: 如果作者中途跳走，记录被中断的节以便回来

## 部分手稿模式集成

当 `entry_point == "partial-manuscript"` 且 `passport.gap_fill_plan` 存在时启用。

### Complete 节预标记
将 `gap_fill_plan.sections` 中 `status="Complete"` 的节预初始化为 stepping_state 中的已批准状态，不在待写列表中展示。

### 修改后的完成列表显示
```
📋 已完成: §2 (Methods) [作者撰写，保留], §4 (Discussion) [作者撰写，保留]
📋 待定: §3 (Results) [缺失—从零写], §1 (Introduction) [占位符—从零写]
➡️  下一节推荐: §3 (Results)
```

### 禁止编辑 Complete 节
若作者请求编辑预标记为 Complete 的节：
```
⚠️ §4 由您撰写并标记为 Complete。编辑将状态从[已保留]改为[已修改]。继续？
```

### Partial 节工作流
1. 展示已有内容，突出缺失部分
2. 确认缺失部分列表
3. 只写缺失部分
4. 新旧合并展示，作者审核
5. 通过后标记完成

### 中断恢复
若 Partial 节写作中被重定向 → 保存当前进度、切换目标、返回后从中断处继续。
