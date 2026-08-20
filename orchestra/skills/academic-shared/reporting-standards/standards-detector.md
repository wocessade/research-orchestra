# Standards Detector — 研究设计类型自动检测

## 目的

自动分析论文的标题、摘要和方法部分，判断适用的报告规范 checklist。

## 检测逻辑

### Step 1: 读取输入

从论文的开头部分（标题 + 摘要 + 方法前 3 句）提取文本。

### Step 2: 关键词匹配

```
如果包含: "randomized" / "RCT" / "randomised" / "随机对照"
  → CONSORT 2010

如果包含: "cohort" / "case-control" / "cross-sectional" / "observational" / "longitudinal"
  → STROBE

如果包含: "systematic review" / "meta-analysis" / "meta analysis" / "systematic literature review" / "系统综述" / "Meta 分析"
  → PRISMA 2020

如果包含: "case report" / "case series" / "病例报告"
  → CARE

如果 STUDY DESIGN 字段已指定:
  → 直接映射到对应 checklist
```

### Step 3: 多匹配处理

如果匹配到多个 checklist：
- 取置信度最高的（更多关键词命中 → 更高置信度）
- 如果置信度相近（差 ≤ 1），提示用户确认
- 如果无匹配，返回 "未检测到适用的报告规范"

### Step 4: 输出

```json
{
  "detected_standards": ["CONSORT 2010"],
  "confidence": "high",
  "matched_keywords": ["randomized", "RCT"],
  "study_design": "randomized controlled trial",
  "note": null
}
```

## 集成

standards_compliance agent 首先调用此 detector 确定 checklist，然后加载对应的 checklist 文件进行逐项检查。
