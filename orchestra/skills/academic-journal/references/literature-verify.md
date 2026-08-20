# 文献常态化验证机制

## 背景

> **~19 KB reference file.** Prefer on-demand partial reads.
> **Sections:** `## 背景` · `## 验证五维` · `## 三条验证路径` · `### Tier 1：OpenAlex / Crossref 验证（有 DOI 的文献）` · `### Tier 2：CNKI 交叉验证（无 DOI 或有 DOI 但 OpenAlex 查不到）` · `### Tier 3：结构化人工验证（无 DOI 且无 CNKI 记录）` · `## 验证路径选择流程图` · `## 验证状态标记规范` · `## 按文献类型的验证路径速查` · `## 验证流程` · `### 第一阶段：入库验证（S2 文献调研时）` · `### 第二阶段：出库复核（S3-S4 写作时 + S6 引文验证时）` · `### 第三阶段：审查前全面审计（S7）`
> `## 批量验证脚本` · `### 输入格式` · `### 输出 verdict 三态判决逻辑` · `## 污染信号 Schema（Contamination Signals）` · `### Schema` · `### 预印本域名列表（PREPRINT_VENUES）` · `### 污染层级计算（k/k_max）` · `### 与现有验证状态标记的关系` · `## 常见问题处理` · `## 门控集成` · `### S2 Gate (Q2)` · `### S6 Gate (Q6)` · `### S7 Gate (Q7)` · `## 中文文献验证的实操建议`

AI 辅助写作中最危险的故障模式是**编造参考文献** — DOI 看着像真的但不解析、作者名与实际不符、出处张冠李戴。评审人一眼就能看出这类问题，一旦发现会严重损害论文的可信度。

本文档覆盖从文献入库到终稿定稿的**全生命周期验证**，整合到已有的 S2 文献调研、S6 引文验证、S7 润色审查三个阶段中。

## 验证五维

| 维度 | 检查内容 | 严重级别 | 说明 |
|------|---------|---------|------|
| D1 存在性 | 文献在至少一个可信来源中真实存在 | Critical | 不通过 = 编造，必须替换或删除 |
| D2 标题匹配 | 标题一致性 ≥ 80% | Critical | 确保引用的论文确实是那篇 |
| D3 作者匹配 | 第一作者姓名相符 | High | 常见错误：作者名顺序错了或拼写差异 |
| D4 出处(venue) | 期刊/会议名称与源数据一致 | High | 会议标成期刊、中文期刊名英译版差异 |
| D5 年份 | 发表年份偏差 ≤ 1 | Medium | 常见于预印本→正式出版的年份差异 |

## 三条验证路径

不同来源的文献有不同的验证方式。**不要只依赖 DOI。**

```
文献类型判定
│
├─ 有 DOI ────────────────────────────────── → Tier 1: OpenAlex / Crossref 验证
│   ├─ 英文期刊/会议论文 → OpenAlex (覆盖率最高)
│   ├─ 中文期刊论文 → 大部分已有 CNKI DOI，OpenAlex 可查
│   ├─ 中文会议论文 → 部分有 DOI，OpenAlex 覆盖率较低
│   └─ 中文学位论文 → 部分有 DOI
│
├─ 无 DOI，但有 CNKI 检索结果 ─────────────── → Tier 2: CNKI 交叉验证
│   ├─ 中文学位论文 → CNKI 硕士/博士论文库
│   ├─ 中文期刊论文（老文章）→ CNKI 知网
│   └─ 中文会议论文 → CNKI 会议论文库
│
└─ 无 DOI，也无 CNKI 记录 ────────────────── → Tier 3: 结构化人工验证
    ├─ 政策文件 / 技术标准 → 官网可查
    ├─ CVE 条目 → MITRE 数据库
    ├─ 技术报告 / 白皮书 → 发布机构官网
    └─ 书籍 / 专著 → 出版社网站 / 图书馆目录
```

### Tier 1：OpenAlex / Crossref 验证（有 DOI 的文献）

**适用对象：** 有 DOI 的英文和中文文献。

OpenAlex 索引了超过 2.5 亿篇学术作品，**包括大量中文文献**。CNKI 近年分配的 DOI（格式如 `10.xxxx/j.cnki.xxxxx`）大部分已被 OpenAlex 收录。所以：

- 英文论文 → 首选 OpenAlex，覆盖 CCF 会议/SCI 期刊 99%+
- 中文论文（2015 年后）→ 大部分 CNKI DOI 可在 OpenAlex 查到
- 中文论文（2015 年前）→ 部分无 DOI，或 DOI 未入 OpenAlex

**操作：**

```bash
# 标准 DOI 查询
curl -s "https://api.openalex.org/works/doi:10.xxxx/xxxxx?select=doi,title,authorships,primary_location,cited_by_count,publication_year"

# 中文 DOI 也一样（CNKI 分配的 DOI）
curl -s "https://api.openalex.org/works/doi:10.xxxx/j.cnki.xxxxx?select=doi,title,authorships,primary_location,cited_by_count,publication_year"

# 无 DOI 时，用精确标题搜索（中英文皆可，URL 编码中文）
curl -s "https://api.openalex.org/works?search=网络安全态势感知&filter=publication_year:2022&select=doi,title,primary_location,cited_by_count"
```

**判定标准：**
- **D1 通过**：API 返回 200，有 `title` 字段
- **D2 通过**：API 返回标题与引用标题相似度 ≥ 80%（中文按字符重叠度，英文按单词重叠度）
- **D3 通过**：第一作者姓名匹配（中文名需注意全名/缩写差异）

**常见中文 DOI 前缀示例：**
| 来源 | DOI 格式示例 |
|------|-------------|
| CNKI 期刊 | `10.xxxx/j.cnki.xxxxx` |
| 万方 | `10.xxxx/j.issn.xxxx` |
| 中文会议（Springer LNEE 等） | `10.1007/xxxx` |
| 中文学位论文 | `10.xxxx/d.cnki.xxxxx` |

### Tier 2：CNKI 交叉验证（无 DOI 或有 DOI 但 OpenAlex 查不到）

**适用对象：** 中文学位论文、中文老期刊论文、中文会议论文。

**前置条件：** 用户已提供 CNKI 导出的搜索结果（.nbib / RIS 文件，或粘贴的题录列表）。

**操作流程：**

1. **用户提供 CNKI 导出文件**（S2/S6 步骤中要求用户导出）
2. **四字段比对：** 对每条待验证引用，逐一比对以下字段：

```
引用中的字段        CNKI 导出中的字段
────────────────────────────────────
作者                   作者
标题                   标题
期刊名                 期刊名/学位授予单位
年份                   出版年份
```

3. **结果分类：**
   - 四字段全部匹配 → `✅ [CNKI 验证]`
   - 1-2 个字段不匹配 → `⚠️ [CNKI 部分匹配: 差异字段]` → 人工判断
   - 全部不匹配 → `❌ [CNKI 未找到]` → 确认是否编造

4. **无 DOI 的中文期刊论文：** 如果用户无法提供 CNKI 导出，要求用户至少确认"这篇论文确实存在"。

**与现有 S6 中文文献处理的对接：**

S6 已有中文文献处理协议（CNKI 导出 .nbib/RIS 交叉检查 → 字段比对 → 标记 → 用户确认）。本机制直接复用该协议，并增加了统一的验证状态标记规范：

| 标记 | 含义 |
|------|------|
| `✅ [DOI 验证]` | OpenAlex/Crossref 确认存在，元数据一致 |
| `✅ [CNKI 验证]` | CNKI 导出记录四字段比对通过 |
| `⚠️ [待用户确认]` | 无法自动验证，需用户人工确认 |
| `❌ [未验证]` | 无法验证且用户未确认 |

### Tier 3：结构化人工验证（无 DOI 且无 CNKI 记录）

**适用对象：** 政策文件、技术标准、CVE 条目、技术报告、白皮书、书籍专著。

**每类文献的验证方法：**

| 类型 | 验证方式 | 可信来源 |
|------|---------|---------|
| 政策文件 | 访问官方发布网站确认 | gov.cn， 各部委官网 |
| 国家标准（GB/T） | 全国标准信息公共服务平台 | std.samr.gov.cn |
| CVE 条目 | MITRE CVE 数据库 | cve.mitre.org |
| 技术报告/白皮书 | 发布机构官网 | 信通院、CCID、Gartner 等 |
| 书籍/专著 | 出版社网站或图书馆目录 | 出版社官网、读秀 |
| 学位论文（无 DOI） | CNKI 硕士/博士论文库（用户提供截图即可） | cnki.net |

**人工验证清单：**
```
□ 文献标题是否在可信来源中检索到
□ 作者姓名是否一致
□ 出版年份是否一致
□ 出版社/发布机构是否一致
□（如是）当前日期，URL/来源仍可访问
```

## 验证路径选择流程图

```
┌─────────────────────────┐
│   有一条参考文献要验证    │
└──────────┬──────────────┘
           ▼
┌─────────────────────────┐
│  有没有 DOI？            │
└──────┬──────────┬───────┘
       │是        │否
       ▼          ▼
┌─────────────┐  ┌─────────────────────┐
│ OpenAlex    │  │  CNKI/Wanfang 能查到吗？│
│ 查询        │  └──────┬──────────┬───────┘
└──────┬──────┘         │是        │否
       ▼                ▼          ▼
┌─────────┐  ┌──────────────┐  ┌──────────────────┐
│ 查到？   │  │ CNKI 四字段  │  │ 属于哪种类型？   │
└──┬──┬───┘  │ 比对          │  │ 政策/标准/CVE/   │
   │是│否    └──────┬───────┘  │ 报告/书籍/其他？ │
   ▼  ▼            ▼          └──────┬───────────┘
┌────┐ ┌─────┐ ┌────────┐           ▼
│✅  │ │用   │ │✅/⚠️   │  ┌──────────────────┐
│   │ │Tier2│ │        │  │ 官网/数据库确认   │
│   │ │或   │ │        │  │ 存在 → ✅        │
│   │ │Tier3│ │        │  │ 否则 → ⚠️       │
└────┘ └─────┘ └────────┘  └──────────────────┘
```

## 验证状态标记规范

每篇文献在文献矩阵或审计报告中必须有且只有一个验证状态标记：

```
✅ [DOI 验证]         — Tier 1 通过
✅ [CNKI 验证]        — Tier 2 通过
✅ [人工验证]         — Tier 3 通过
⚠️ [待用户确认]       — 无法自动验证
❌ [未验证: 原因]     — 显式未验证（如"用户未提供 CNKI 导出"）
```

## 按文献类型的验证路径速查

| 文献类型 | 典型验证路径 | 备注 |
|---------|-------------|------|
| 英文期刊（SCI/EI） | Tier 1 DOI | 几乎都有 DOI，OpenAlex 全覆盖 |
| 英文会议（CCF 系列） | Tier 1 DOI | NDSS/CCS/USENIX/S&P 等都有 DOI |
| 中文核心期刊 | Tier 1 或 Tier 2 | 2015 年后大多有 CNKI DOI，OpenAlex 覆盖率约 60-70% |
| 中文非核心期刊 | Tier 2 CNKI | DOI 覆盖率低 |
| 中文学位论文 2020+ | Tier 1 或 Tier 2 | 部分有 CNKI DOI |
| 中文学位论文 2020 前 | Tier 2 CNKI | 大多无 DOI |
| 中文会议论文 | Tier 1 或 Tier 2 | 视会议是否提供 DOI |
| CVE 条目 | Tier 3 cve.mitre.org | 无 DOI |
| 国家标准 | Tier 3 std.samr.gov.cn | 无 DOI |
| 政策文件 | Tier 3 政府官网 | 无 DOI |
| 技术白皮书 | Tier 3 机构官网 | 无 DOI |
| 书籍/专著 | Tier 3 出版社/图书馆 | 少数有 DOI |

## 验证流程

### 第一阶段：入库验证（S2 文献调研时）

**英文/国际文献：** 从 `literature_search.py` 搜索/雪球获取的每篇论文，同步保存验证快照：

```json
{
  "doi": "10.xxxx/xxxxx",
  "title_api": "API 返回标题",
  "authors_api": ["Author1", "Author2"],
  "venue_api": "Journal Name",
  "year_api": 2024,
  "cited_by_count": 42,
  "verified_at": "2026-06-04",
  "status": "verified",
  "verify_method": "openalex"
}
```

**中文文献：** 用户提供 CNKI 搜索结果后，做四字段比对验证。

每篇文献在文献矩阵末尾追加验证摘要行：

```markdown
| 验证状态 | ✅ [DOI 验证] DOI: 10.xxxx/xxxxx, 引用: 42 |
| 验证状态 | ✅ [CNKI 验证] 四字段一致 |
| 验证状态 | ⚠️ [待用户确认] 无 DOI，无 CNKI 记录 |
```

**硬规则：** 标记为 `❌ [未验证]` 的文献不得超过文献池总量的 10%。

### 第二阶段：出库复核（S3-S4 写作时 + S6 引文验证时）

**S3/S4 写作中引用文献：**
- 提取全部引用的验证状态
- 发现 `❌ [未验证]` 或 `⚠️ [待用户确认]` → 暂停，先处理验证
- 记录修正日志到 `{output_dir}/citation_fix_log.md`

**S6 处理时：** 已是全量验证的最后关卡。此时所有引用都必须有确定的状态标记。

### 第三阶段：审查前全面审计（S7）

在 `skills-embedded/paper-audit.md` 或毕业论文审查之前，运行**文献审计**：

1. **Tier 1 文献：** 全量 OpenAlex DOI 验证
2. **Tier 2 文献：** 确认 CNKI 四字段比对记录
3. **Tier 3 文献：** 确认人工验证记录
4. **重复检测：** 同一论文被标注为两个不同引用编号
5. **CCF 标注检查：** 声称在 CCF-A/B 会议发表的论文是否属实（仅限 discipline=stem）

## 批量验证脚本

`literature/verify_citations.py` 是自动化的批量引用验证 CLI，替代手动 curl 操作。功能：

- **多 API 并行验证**：OpenAlex（DOI/标题）→ Semantic Scholar（DOI/标题）→ Crossref（DOI）
- **三态判决**：`true`（匹配）、`false`（DOI 级不匹配=造假证据）、`unresolvable`（仅标题搜索失败=覆盖缺口）
- **SQLite 缓存**：`~/.cache/pipeline/verification.db`，90 天 TTL
- **污染信号**：每篇文献附 contamination_signals 对象（见下文 schema）
- **豁免**：`source: manual` 的条目跳过自动验证

```bash
# 标准运行
python literature/verify_citations.py \
    --input {output_dir}/bibliography.json \
    --output-dir {output_dir}/verification/

# 仅从缓存重新生成报告（不发 API 请求）
python literature/verify_citations.py \
    --input {output_dir}/bibliography.json \
    --output-dir {output_dir}/verification/ \
    --report-only
```

输出文件：
- `verification_report.json` — 完整验证报告（含每篇的 verdict + contamination_signals）
- `verification_summary.txt` — 人类可读的摘要

### 输入格式

`bibliography.json` 应为包含 Paper 对象列表的 JSON 文件（S2 输出格式，list 或 `{"results": [...]}`）：

```json
{
  "citation_key": "smith2024",
  "title": "Attention Is All You Need",
  "authors": ["Vaswani, A."],
  "year": 2017,
  "doi": "10.xxxx/xxxxx",
  "venue": "NeurIPS",
  "source": "openalex"
}
```

### 输出 verdict 三态判决逻辑

```
有 DOI 且至少一个 API 确认存在         → "true"   ✅
有 DOI 但所有 API 都未匹配             → "false"  ❌（造假证据）
无 DOI，且标题搜索全失败               → "unresolvable" ⚠️（覆盖缺口）
source=manual                           → "unresolvable" ⏭️（豁免）
```

`false` 是最严重的信号——DOI 存在但没有任何一个索引数据库找到它，说明 DOI 可能是编造的。

## 污染信号 Schema（Contamination Signals）

每篇文献的验证输出包含一个 `contamination_signals` 对象。这些信号是**劝告级**（不阻断验证流程），用于给 AI agent 和人工评审者提供额外的可靠性上下文。

### Schema

| 字段 | 类型 | 含义 | 触发条件 |
|------|------|------|---------|
| `preprint_post_2024` | bool | 2024 年后的预印本 | `year >= 2024` 且 `venue` 在预印本域名列表中 |
| `openalex_unmatched` | bool\|null | OpenAlex 无匹配 | API 查询无匹配；`null`=未检查（manual 豁免/API 降级） |
| `semantic_scholar_unmatched` | bool\|null | Semantic Scholar 无匹配 | 同上 |
| `crossref_unmatched` | bool\|null | Crossref 无匹配 | 同上 |

### 预印本域名列表（PREPRINT_VENUES）

```
arXiv, bioRxiv, medRxiv, SSRN, Research Square,
Preprints.org, ChemRxiv, EarthArXiv, OSF Preprints, TechRxiv
```

### 污染层级计算（k/k_max）

从 per-API unmatched 信号（排除 `preprint_post_2024` 和 `null` 字段）计算：

| k/k_max | 层级 | 含义 |
|---------|------|------|
| 0/3 | `clean` | 所有 API 均匹配，无污染 |
| ≤0.25（≤1/3） | `low` | 少量 API 未匹配，可能为覆盖缺口 |
| ≤0.5（≤2/3） | `medium` | 多个 API 未匹配，建议人工核验 |
| >0.5（>2/3） | `high` | 大多数 API 未匹配，重点审查 |

### 与现有验证状态标记的关系

contamination_signals 是**附加信息**，不改变主验证状态标记（`✅ [DOI 验证]` / `❌ [未验证]`）。`preprint_post_2024: true` 的文献仍然可以通过验证——预印本不是造假（但 AI agent 在写作时应注明"预印本"）。`false` verdict 且 `openalex_unmatched: true` 的文献应升格为 Critical 问题。

```json
{
  "verdict": "true",
  "contamination_signals": {
    "preprint_post_2024": true,
    "openalex_unmatched": false,
    "semantic_scholar_unmatched": false,
    "crossref_unmatched": false
  },
  "contamination_level": "clean"
}
```

## 常见问题处理

| 问题 | 处理方式 |
|------|---------|
| DOI 在 OpenAlex 返回 404 | 检查格式。仍无效 → 降级到 Tier 2（CNKI 搜索标题确认） |
| 中文论文有 CNKI DOI 但 OpenAlex 查不到 | 正常，CNKI 部分 DOI 未入 OpenAlex。降级到 Tier 2 |
| 标题有细微出入（标点/大小写） | 以 API 为准修正引用。不影响通过。 |
| 中文作者名差异（张三 vs Zhang San） | 中文期刊用中文名，英文期刊用拼音。记录为"一致" |
| 第一作者匹配但第二作者对不上 | 只检查第一作者。中文论文尤其常见作者顺序问题。 |
| 引用次数为 0 | 2025-2026 新论文正常。检查是否发表在非正规期刊。 |
| 声称 CCF-A 但实际不是 | 修正标注。强烈建议替换为真实 CCF-A 来源。 |
| 书中章节引用 | 有 DOI 走 Tier 1，无 DOI 走 Tier 3（出版社官网确认） |
| 预印本（arXiv） | Crossref 收录 arXiv DOI，可直接验证。注意预印本→正式出版的版本差异。 |

## 门控集成

### S2 Gate (Q2)

```
☐ 所有有 DOI 的文献已通过 OpenAlex 存在性验证（D1）或 verify_citations.py 确认
☐ 中文文献已通过 CNKI 四字段比对或用户确认
☐ 前 10 篇重点文献的作者/出处/年份已核对（D3-D5）
☐ 文献矩阵中每篇论文均有统一的验证状态标记
☐ ❌ [未验证] 比例 ≤ 10%
☐ 每篇文献已计算 contamination_level（clean/low/medium/high）
☐ contamination_level=high 的文献已记录到审查日志
```

### S6 Gate (Q6)

```
☐ 全量 Tier 1 文献 DOI 解析通过（verify_citations.py 批量验证确认）
☐ 全量 Tier 2 文献 CNKI 比对完成或用户已确认
☐ 全量 Tier 3 文献人工验证记录完整
☐ 随机抽查 5 篇：引用声明与实际论文摘要一致
☐ 无 ❌ [未验证] 状态的引用
☐ contamination_level=high 的引用已逐条审查
☐ verdict=false（造假嫌疑）的引用已被替换或删除
☐ 所有预印本（preprint_post_2024=true）已标注为预印本来源
```

### S7 Gate (Q7)

```
☐ 文献验证状态汇总完成
☐ 无 Critical 问题（无编造/虚构参考文献）
☐ existing-manuscript 入口：全量验证；正常入口：至少抽查 20%
```

## 中文文献验证的实操建议

1. **大部分中文期刊论文实际上有 DOI。** CNKI 自 2015 年起大规模分配 DOI，格式为 `10.xxxx/j.cnki.xxxxx`。先试 Tier 1，查不到再降级到 Tier 2。

2. **OpenAlex 对中文文献的标题搜索可能不准确。** 因为 OpenAlex 的全文索引是以英文为主的。中文标题搜索时，建议使用精确短语加双引号。

3. **最可靠的中文验证方式仍然是 CNKI 导出。** 在 S2 阶段主动要求用户提供 CNKI 搜索结果导出文件，这是性价比最高的方式。

4. **学位论文的验证：** 中文学位论文多数可在 CNKI 硕士/博士论文库查到。有 DOI 的走 Tier 1，无 DOI 的走 Tier 2（用户提供 CNKI 截图即可）。

5. **老文献（2010 年前）可能完全没有数字标识：** 走 Tier 3，要求用户通过图书馆目录或 CNKI 确认存在即可。
