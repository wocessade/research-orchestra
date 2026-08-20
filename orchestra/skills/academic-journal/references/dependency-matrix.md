# 依赖追溯表 (Dependency Matrix)

> 每个 `skills-embedded/` 文件被哪些管道文件引用。检修时查此表快速评估修改影响范围。
>
> **生成时间:** 2026-06-06 | **总计:** 38 个嵌入文件，~250 处引用

---

## 核心 (Critical)

### `skills-embedded/paper-audit.md`

| 引用文件 | 用途 |
|---------|------|
| `static/core/exit-protocol.md` | S9 循环检测示例 |
| `static/core/gate-chain.md` | Q7、Q9 门控条件 |
| `static/core/prerequisites.md` | 必备/重要/可选表 |
| `strategists/S7-strategist.md` | 修正阈值、Pass1/2、3-referee 可选升级 |
| `strategists/S9-strategist.md` | 门控第一关 |
| `strategists/S12-strategist.md` | S9-Lite 模式复审 |
| `references/emergency-path.md` | S9-Lite、MVP 流程 |
| `references/literature-verify.md` | 审查前文献审计 |

### `skills-embedded/paper-lookup.md`

| 引用文件 | 用途 |
|---------|------|
| `static/core/web-search-policy.md` | 搜索优先级 #1 |
| `static/core/prerequisites.md` | 必备表 |
| `strategists/S2-strategist.md` | 英文/Crossref 中文补充检索 |
| `strategists/S2-LR-strategist.md` | D2D 针对性查新 |
| `strategists/S2-LR-strategist.md` | 多数据库搜索（×2）|
| `strategists/S2-strategist.md` | 备选搜索工具 |
| `references/chinese-journal-adapter.md` | 国际路径搜索工具（×3）|
| `references/journal-style-adapter.md` | Step 1 语料库获取 |

### `skills-embedded/nature-reader.md`

| 引用文件 | 用途 |
|---------|------|
| `static/core/do-dont.md` | 引用前精读 |
| `static/core/prerequisites.md` | 重要表 |
| `strategists/S2-LR-strategist.md` | 手动提取论文信息 |
| `strategists/S2-strategist.md` | 中英对照精读 |
| `strategists/S4-strategist.md` | 学习中式风格范文 |
| `strategists/S6-strategist.md` | 被标记引文重检 |
| `references/chinese-journal-adapter.md` | S2D 精读、S4 风格学习（×2）|
| `references/journal-style-adapter.md` | Step 1 全文阅读 |

### `skills-embedded/citation-management.md`

| 引用文件 | 用途 |
|---------|------|
| `static/core/prerequisites.md` | 必备表 |
| `strategists/S2-strategist.md` | 交叉检查生成条目 |
| `strategists/S2-LR-strategist.md` | DOI 验证 |
| `strategists/S2-strategist.md` | BibTeX DOI 验证（×2）|
| `strategists/S6-strategist.md` | DOI 验证、CNKI 交叉检查（×3）|
| `references/chinese-journal-adapter.md` | S6 国际路径工具 |

### `skills-embedded/nature-polishing.md`

| 引用文件 | 用途 |
|---------|------|
| `SKILL.md` | 模式验证说明 |
| `static/core/prerequisites.md` | 重要表 |
| `strategists/S7-strategist.md` | 高影响力期刊润色、zh-to-en 轴 |
| `references/chinese-journal-adapter.md` | S7 国际路径工具 |
| `references/journal-style-adapter.md` | P3 领域惯例 |

### `skills-embedded/nature-writing.md`

| 引用文件 | 用途 |
|---------|------|
| `SKILL.md` | 模式验证说明 |
| `static/core/prerequisites.md` | 重要表 |
| `strategists/S3-strategist.md` | 写作备选 |
| `strategists/S4-strategist.md` | 高影响力期刊写作 |
| `references/chinese-journal-adapter.md` | S4 国际路径、英文投稿说明（×3）|

### `skills-embedded/scientific-writing.md`

| 引用文件 | 用途 |
|---------|------|
| `static/core/prerequisites.md` | 重要表 |
| `strategists/S3-strategist.md` | 规划器 |
| `strategists/S4-strategist.md` | IMRAD 写作、word/markdown/auto-detect 格式（×4）|
| `strategists/S7-strategist.md` | 通用学术英文修订模式 |
| `references/chinese-journal-adapter.md` | S4 国内路径（zh mode）（×2）|
| `references/journal-style-adapter.md` | P3 领域惯例 |

---

## 重要 (Important)

### `skills-embedded/nature-figure.md`

| 引用文件 | 用途 |
|---------|------|
| `static/core/prerequisites.md` | 重要表 |
| `strategists/D1-strategist.md` | 分布图 |
| `strategists/S5-strategist.md` | Python/R 数据图、数据重制（×3）|
| `references/chart-type-selection.md` | 图表类型选用说明 |

### `skills-embedded/scientific-visualization.md`

| 引用文件 | 用途 |
|---------|------|
| `static/core/prerequisites.md` | 重要表 |
| `strategists/D0-strategist.md` | 数据类型快速检查 |
| `strategists/D1-strategist.md` | 单变量统计、分布图、相关矩阵、分组比较、缺失模式（×5）|
| `strategists/S2-LR-strategist.md` | 森林图 |
| `strategists/S5-strategist.md` | 数据图备选 |
| `references/chart-type-selection.md` | 图表类型选用说明 |

### `skills-embedded/peer-review.md`

| 引用文件 | 用途 |
|---------|------|
| `static/core/prerequisites.md` | 必备表 |
| `strategists/S9-strategist.md` | 细节审查、审稿人指定 |
| `strategists/S9.5-strategist.md` | 攻击性审稿人模拟 |

### `skills-embedded/scientific-critical-thinking.md`

| 引用文件 | 用途 |
|---------|------|
| `static/core/prerequisites.md` | 可选表 |
| `strategists/S2-LR-strategist.md` | GRADE 证据质量评估 |
| `strategists/S2-strategist.md` | 3D 质量评分 |
| `strategists/S7-strategist.md` | 段落逻辑流 |
| `strategists/S9-strategist.md` | 逐条证据评估 |

### `skills-embedded/scientific-schematics.md`

| 引用文件 | 用途 |
|---------|------|
| `static/core/prerequisites.md` | 重要表 |
| `strategists/S2-LR-strategist.md` | PRISMA 流程图（×2）|
| `strategists/S5-strategist.md` | 示意图、图形摘要（×2）|
| `references/chart-type-selection.md` | 理论/概念论文参考 |

### `skills-embedded/latex-document-skill.md`

| 引用文件 | 用途 |
|---------|------|
| `static/core/prerequisites.md` | 必备表 |
| `strategists/S8-strategist.md` | 编译、引擎选择、PDF/A（×5）|
| `references/chinese-journal-adapter.md` | S8 国际路径工具 |

### `skills-embedded/cover-letter.md`

| 引用文件 | 用途 |
|---------|------|
| `static/core/prerequisites.md` | 可选表 |
| `strategists/S10-strategist.md` | 投稿信生成 |
| `references/chinese-journal-adapter.md` | S10 国际路径工具 |

---

## 频率统计

| 嵌入文件 | 引用次数 | 涉及文件数 |
|---------|---------|-----------|
| `paper-lookup.md` | 9 | 8 |
| `nature-reader.md` | 10 | 7 |
| `citation-management.md` | 10 | 6 |
| `paper-audit.md` | 9 | 8 |
| `scientific-writing.md` | 10 | 6 |
| `scientific-visualization.md` | 10 | 5 |
| `nature-figure.md` | 6 | 4 |
| `peer-review.md` | 4 | 3 |
| `nature-polishing.md` | 6 | 5 |
| `nature-writing.md` | 7 | 5 |
| `scientific-critical-thinking.md` | 5 | 4 |
| `scientific-schematics.md` | 6 | 4 |
| `latex-document-skill.md` | 7 | 3 |
| `cover-letter.md` | 4 | 3 |
| `scientific-brainstorming.md` | 4 | 4 |
| `venue-templates.md` | 4 | 3 |
| `bib-search-citation.md` | 4 | 3 |
| `pyzotero.md` | 4 | 3 |
| `nature-citation.md` | 3 | 3 |
| `latex-paper-en.md` | 2 | 2 |
| `hypothesis-generation.md` | 2 | 2 |
| `nature-response.md` | 2 | 2 |
| `nature-data.md` | 1 | 1 |
| `nature-academic-search.md` | 2 | 2 |
| `generate-image.md` | 2 | 2 |
| `literature-review.md` | 2 | 2 |
| `latex-posters.md` | 1 | 1 |
| `bgpt-paper-search.md` | 1 | 1 |
| `typst-paper.md` | 2 | 2 |
| `academic-research.md` | 2 | 2 |

---

## 检修指引

1. **改一个嵌入文件 →** 查上表看哪些 stage/static 文件引用了它，逐一检查是否需要同步更新
2. **改一个 stage 文件 →** 无需更新依赖矩阵（矩阵只跟踪嵌入文件的被引用关系）
3. **新增嵌入文件 →** 在此表末尾追加一行，并更新 `skills-embedded/README.md` 的版本清单
4. **删除嵌入文件 →** 先查此表确保无残留引用，然后删除文件并从 `manifest.yaml` 移出
