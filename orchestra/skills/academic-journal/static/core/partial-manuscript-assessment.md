# Partial Manuscript Assessment

评估半成品论文各章节的完成状态，输出缺口表，指导补写策略。

## 评估流程

### Step 1: 结构识别
根据 `passport.paperType` 确定论文应有的节结构（IMRAD / Data Descriptor / Architecture-Implementation-Validation 等）。

### Step 2: 逐节分类
对每个应有节，分类为：

| 状态 | 判定标准 | 处理方式 |
|------|---------|---------|
| **Complete** | 有完整 prose，无占位符，论据有支撑 | 保留不动 |
| **Partial** | 有内容但不足：缺论据、逻辑跳跃、部分段落是提纲 | 增量补充，不重写 |
| **Placeholder** | 只有 `[TBD]`/`[To be written]`/空标题等占位标记 | 从零写 |
| **Missing** | 整个节不存在 | 从零写 |

### Step 3: 冲突标记
如果已完成节与计划补写的内容存在逻辑/数据冲突：
- 标记冲突位置
- 补写时以数据/证据为准
- 必要时回头修改已完成节（最小改动）

## 输出格式

```markdown
## Manuscript Assessment: {paper_title}

### Section Status
| § | Section | Status | Notes |
|----|---------|--------|-------|
| 1 | Introduction | Placeholder | [To be rewritten] |
| 2 | Background | Complete | — |
| 3 | Methods | Partial | §3.2 missing experimental setup details |
| 4 | Results | Placeholder | [To be completed] |
| 5 | Discussion | Complete | — |
| 6 | Conclusion | Missing | Section doesn't exist |

### Gap-Fill Plan (Core-First order)
1. §3.2 — 补充实验设置细节
2. §4 (Results) — 从零写
3. §1 (Introduction) — 从零写（主体完成后）
4. §6 (Conclusion) — 从零写（最后）
```

## 补写纪律

1. **已完成节不要动** —— 除非补写内容暴露出矛盾，此时做最小修改
2. **按 Core-First 顺序补** —— 先补主体（Methods→Results→Discussion），后补框架（Introduction→Conclusion）
3. **补写质量要对齐已完成节** —— 术语、风格、引用格式与已完成节一致
4. **补完后整体跑 Q7 审计** —— 保证新旧内容衔接无痕
