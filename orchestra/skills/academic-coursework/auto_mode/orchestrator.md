# 全自动模式编排器 (Auto Mode Orchestrator)

**Purpose:** 定义全自动模式下的端到端编排流程。用户只需提供选题，无需中间确认即可获得完整论文。

**适用场景:**
- 时间紧迫，需要快速出稿
- 用户只提供选题，不参与中间决策
- 重复性课程论文写作

---

## 自动编排流程

```
┌─────────────────────────────────────────────────┐
│  Step 0: 接收用户选题                            │
│  "帮我写一篇关于X的课程论文"                       │
│  -> 提取 topic_sentence                          │
│  -> 设置 mode=auto                               │
│  -> 加载 manifest.yaml                           │
│  -> 检测 prerequisites (python-docx 等)           │
└─────────────────────┬───────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────┐
│  Step 1: C1 Auto — 自动选题与论点生成              │
│  -> 运行 C1-PRE 文献可得性检查                    │
│  -> 运行 C1A 自动头脑风暴 (scientific-brainstorming)│
│  -> 自动选择最佳选题 (不打断)                      │
│  -> 自动生成 3+ 论点及逻辑顺序                     │
│  -> 自动写入 thesis_paragraph                     │
│  -> 记录到 passport                              │
│  -> Auto-check QC1                               │
└─────────────────────┬───────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────┐
│  Step 2: C2 Auto — 自动文献搜索                   │
│  -> 运行 C2A 搜索协议生成                         │
│  -> 并行运行 C2B (英文搜索+paper-lookup)          │
│  -> 运行 C2C (政策/行业搜索)                      │
│  -> 运行 C2D (中文搜索 - Playwright/browser)      │
│  -> 运行 C2E (Web context - Tavily/browser)      │
│  -> 合并 C2F 可信度筛选 + 质量矩阵                │
│  -> C2G 去重合并                                 │
│  -> C2H 缺口填补                                 │
│  -> Auto-check QC2                               │
│  -> 生成 auto_bibliography.md                    │
└─────────────────────┬───────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────┐
│  Step 3: C3 Auto — 自动撰写 .docx                │
│  -> 生成 python-docx 写作脚本                     │
│  -> 引用来自 C2 的参考文献                         │
│  -> 执行脚本生成 draft.docx                       │
│  -> 自动填充：标题、摘要、关键词、正文、结论、参考文献  │
│  -> Auto-check QC3 (文件大小、段落数、章节完整性)   │
│  -> 抄送 user: "初稿已生成，路径为 {path}"         │
└─────────────────────┬───────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────┐
│  Step 4: C4 Auto — 自动审查                      │
│  -> 从 draft.docx 提取纯文本                      │
│  -> 运行 6 维自动审查 (auto_checks.py):           │
│    . content_reviewer — 内容完整性               │
│    . structure_reviewer — 结构合理性             │
│    . ai_tone_detector — AI 味检测               │
│    . format_compliance — 格式合规               │
│    . logic_consistency — 逻辑一致性              │
│    . factual_accuracy — 事实准确性               │
│  -> 生成 auto_review_report.md                   │
│  -> 去重+冲突合并                                │
│  -> Auto-check QC4                               │
└─────────────────────┬───────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────┐
│  Step 5: C5 Auto — 自动修订与收敛                 │
│  -> 读取 C4 审查报告                              │
│  -> 自动应用修复 (修改 python-docx 脚本 + 重新生成) │
│  -> 重新运行 C4 审查                              │
│  -> 检查收敛条件 (QC5)                            │
│  -> 最多 3 轮                                     │
│  -> 收敛后 -> 交付                                │
│  -> 未收敛 -> 交付+说明                           │
└─────────────────────┬───────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────┐
│  Step 6: 最终交付                                │
│  -> 输出 final_draft.docx                        │
│  -> 生成交付报告 (字数、页数、审查轮次、问题统计)    │
│  -> 检查隐藏分支触发器 (C5.5 - 用户是否提到注水)   │
│  -> 如触发: STOP-AND-ASK 是否运行注水             │
│  -> 交付完成                                    │
└─────────────────────────────────────────────────┘
```

## 自动决策规则

### 选题决策 (C1 Auto)

当用户没有指定具体选题时:

1. 从用户描述中提取核心主题
2. 运行 `skills-embedded/scientific-brainstorming.md` 生成 3 个候选选题
3. 自动评分: 引用可得性 (C1-PRE 结果) + 论证结构清晰度 + 课程适配度
4. 选择最高分选题，不中断用户
5. 自动生成 thesis_paragraph

**如果 C1-PRE 发现 < 10 篇可用文献:** 自动缩小范围或调整方向，记录在 auto_decision_log.md 中

### 参考文献决策 (C2 Auto)

1. 优先使用自动化搜索工具 (paper-lookup, Tavily, Playwright)
2. 达不到 15 篇目标时，自动降低标准至 8 篇 (emergency mode)
3. 达不到每论点 3 篇支撑时，自动调整论点结构
4. 全部记录在 auto_bibliography.md 中

### 修订决策 (C5 Auto)

1. Critical 问题: 全部自动修复
2. Major 问题: 自动修复，记录修复方式
3. Minor 问题: 时间允许时修复
4. 3 轮未收敛: 自动降级，交付带说明的版本

## 自动日志

全自动模式下，每个步骤的输出记录在 `{output_dir}/auto_decision_log.md` 中:

```markdown
# Auto Decision Log

## Step 1: C1 Auto
- Topic: [自动选择的选题]
- Alternatives considered: [候选列表]
- Selection rationale: [选择理由]
- Arguments: [自动生成的论点]

## Step 2: C2 Auto
- Total refs found: N (EN: N, CN: N)
- Auto-standard applied: [standard/emergency]
- ...
```

## 故障处理

| 问题 | 自动行为 | 升级条件 |
|------|---------|---------|
| C1-PRE 文献不足 | 自动缩小范围 | 两次失败 -> STOP-AND-ASK |
| C2B 英文搜索 0 结果 | 自动切换 fallback (paper-lookup + browser) | 双 fallback 失败 -> STOP-AND-ASK |
| C3 写作脚本执行失败 | 重试 1 次 (修复语法错误) | 第二次失败 -> STOP-AND-ASK |
| C4 agent 失败 | 自动重试 1 次 | 2+ agents 失败 -> STOP-AND-ASK |
| C5 收敛退化 | 自动重置到上一轮 + 重新评估 root cause | 两次退化 -> STOP-AND-ASK |
| python-docx 未安装 | 自动提示安装命令 | 用户拒绝 -> STOP |
