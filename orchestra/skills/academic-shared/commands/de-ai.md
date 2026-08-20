# Command: /de-ai — 去AI化重写

**来源:** Claude-Scholar 的 `writing-anti-ai` skill

## 用途

检测并消除论文中的 AI 写作痕迹（AI-typical 词汇、句式、语调），使文本更接近人类学者表达。可独立运行，无需完整 evaluate 流程。

## 检测维度

1. **AI 典型词汇** (D1) — "delve", "pivotal", "realm", "foster", "intricate", "tapestry" 等高频 AI 用语
2. **过渡词过密** (D2) — "moreover", "furthermore", "additionally", "notably" 高频重复
3. **句长均匀度** (D3) — 所有句子长度接近标准差 < 10 字符 → AI 特征
4. **"Not only... but also"** (D4) — 二元结构标记
5. **路标词过密** (D5) — 开头 5% 单词为过渡词
6. **介词填充** (D10) — 冗余介词短语
7. **具体性不足** (D15) — 数字/效应量/置信区间密度过低

## 运行流程

```
1. 读取论文文本（从 {output_dir} 中的最新草稿）
2. 扫描全部 7 个维度
3. 对每个 flagged 段落:
   a. 标记问题区域
   b. 生成替换建议（去除 AI 用语，使用更自然的表达）
   c. 显示 BEFORE / AFTER 对比
4. 输出整体 AI 语调评分（0-100）
5. 用户逐段确认替换
```

## 替换策略

| 检测到 | 替换为 |
|--------|--------|
| "This paper delves into..." | "This paper examines..." |
| "It is crucial to note that..." | "(直接陈述)" |
| "A multifaceted approach..." | "An approach combining..." |
| "The results underscore..." | "The results show..." |
| "Not only X, but also Y" | "X and Y" |
| "Moreover, ... Furthermore, ..." | 合并或删除过渡词 |

## 输出

向用户呈现（逐段）：

```
段落 #3 [AI 期望值: 72/100] ⚠️

原文: "This paper delves into the crucial realm of federated learning, underscoring its pivotal role in modern distributed systems. Moreover, the intricate interplay between communication efficiency and model accuracy fosters a multifaceted optimization landscape."

建议: "This paper examines federated learning and its role in distributed systems. The trade-off between communication efficiency and model accuracy creates a complex optimization problem."

是否替换? [y/n] (默认 y):
```

## 参考

- 英文: `chinese-de-ai-guide.md`, `english-de-ai-guide.md` (各阶段的 de-ai 指南)
- 评估: `evaluate/agents/ai_tone_detector.md` (AI 语调检测 agent)
