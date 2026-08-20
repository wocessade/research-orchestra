# 文风学习 — 风格提取流程

## 输入
用户提供 1-3 篇目标范文（支持 PDF / DOCX / TXT）

## 流程
1. 读取范文全文
2. 分四个维度分析风格特征
3. 生成 Style Profile JSON
4. 存档到 `style_profiles/{profile_name}.json`

## 四维分析

### 1. 句式维度
- 平均句长（字/句）和句长分布（短句<15字、中句15-30字、长句>30字的比例）
- 句首多样性（"这/那/但/而/且/虽"等常见句首词的分布熵）
- 主动语态 vs 被动语态比例
- 连词使用模式（如"然而/但是/因此/所以/从而"的使用频率）
- 排比/反问/设问等修辞手法的出现频率

### 2. 词汇维度
- 高频学术词汇 TOP 30（去掉停用词后的实词频率表）
- 领域术语密度（学术领域特有词占总字数比例）
- 成语和四字格使用频率
- 口语化表达出现频率（如"其实、真的、特别"等）
- 中英文混用率（英文术语/缩写出现密度）

### 3. 结构维度
- 段落长度分布（段落的句数和字数分布）
- 节/小节长度（每节字数的均值和标准差）
- 段落首句功能分类（论点引入/过渡/例证/总结的比例）
- 论证推进模式（演绎→归纳还是归纳→演绎）
- 标题风格（"基于X的Y研究" / "X对Y的Z影响" / 动宾短语等）

### 4. 引用维度
- 引用密度（每千字引用次数）
- 引用融合方式分布（"X(2023)认为"叙述式 vs "前人研究表明(X, 2023)"括号式）
- 引用来源类型分布（期刊/专著/学位论文/网络资源等）
- 自引vs他引比例

## Style Profile JSON 格式

```json
{
  "profile_name": "目标期刊/导师风格",
  "source_papers": ["paper1.md", "paper2.md", "paper3.md"],
  "extracted_at": "2026-06-26",
  "sentence": {
    "avg_length": 22.5,
    "length_distribution": {"short": 0.25, "medium": 0.55, "long": 0.20},
    "active_passive_ratio": 0.7,
    "conjunctions": {"然而": 0.8, "因此": 1.2, "但是": 0.5},
    "sentence_start_entropy": 3.2
  },
  "vocabulary": {
    "top_30": ["研究", "分析", "影响", ...],
    "term_density": 0.15,
    "idiom_rate": 0.03,
    "colloquial_rate": 0.01,
    "en_mix_rate": 0.05
  },
  "structure": {
    "para_length_mean": 4.2,
    "para_length_std": 1.8,
    "section_length_mean": 1200,
    "section_length_std": 400,
    "para_first_sentence_types": {"claim": 0.4, "transition": 0.3, "example": 0.2, "summary": 0.1},
    "reasoning_pattern": "deductive",
    "title_style": "基于X的Y研究"
  },
  "citation": {
    "density_per_1k": 3.5,
    "narrative_ratio": 0.6,
    "parenthetical_ratio": 0.4,
    "source_types": {"journal": 0.7, "book": 0.2, "thesis": 0.1},
    "self_citation_ratio": 0.05
  }
}
```

## 应用模式

### 自动应用模式
将 Style Profile 注入写作 prompt：
- 句式约束："平均句长控制在22字左右"
- 词汇约束："优先使用XXX等学术词汇，避免口语化表达"
- 结构约束："每个段落4-5句推论式推进"
- 引用约束："以叙述式引用为主，引用密度约3次/千字"

### 仅建议模式
写作完成后，提取当前文稿的风格特征并与 Style Profile 对比，输出差异报告：
- "你的平均句长28字，目标22字——建议拆分多字句"
- "你的被动语态占比60%，目标30%——建议转为主动"
- "你的引用密度1.2次/千字，目标3.5次——建议补充文献支持"
