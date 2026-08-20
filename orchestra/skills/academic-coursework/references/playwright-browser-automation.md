# 浏览器自动化 (Playwright MCP) 工作流参考

> Playwright MCP 提供**有头（headful）浏览器**模式，可弹出可见浏览器窗口。
> 支持用户手动登录（一次性的，会话保持）后，后续操作全自动。
>
> **适用场景：** CNKI、万方 中文文献检索、DOI 交叉验证、Google Scholar snowballing
> **前置条件：** `settings.json` 中 `mcpServers.playwright` 已配置，`PLAYWRIGHT_HEADLESS=false`

---

## 1. CNKI 文献检索流程

标准的 CNKI 搜索流程，适用于 C2D、T2C、S2-LR 等所有需要中文学术文献检索的阶段。

### Step 1: 打开浏览器 → 导航至 CNKI

```
使用 Playwright MCP 工具导航至 https://www.cnki.net
```

### Step 2: 检查并等待登录

```
检查页面是否有登录提示（右上角"登录/注册"按钮或登录弹窗）。
如果已登录（右上角显示"我的CNKI"或昵称/机构名）→ 跳过，继续 Step 3。
如果未登录 → 弹出浏览器窗口，提示用户：
  "请在浏览器中手动登录 CNKI（推荐扫码登录或机构登录）。
   登录后请告诉我'已登录'，我将继续搜索。"
使用 STOP-AND-ASK 等待用户确认已登录。
```

### Step 3: 执行搜索

从 `search_protocol.md`（C2A/T2A）读取关键词组，依次搜索：

```
对于每个关键词组：
1. 在 CNKI 搜索框输入关键词
2. 选择搜索范围（主题/篇名/关键词/摘要）—— 默认"主题"
3. 点击搜索按钮
4. 等待搜索结果页面加载
5. 翻页提取结果

提取每条结果：
- 标题（点击进入详情页获取完整信息）
- 作者
- 期刊/学位授予单位
- 年份 / 期卷
- 摘要片段
- DOI（如果有）
- 被引次数
- 下载次数
```

### Step 4: 特殊搜索模式

根据阶段需求，在 Step 3 基础上切换搜索范围：

| 搜索目标 | CNKI 操作 | 适用阶段 |
|---------|----------|---------|
| 期刊论文 | 搜索范围选"篇名"，文献类型选"学术期刊" | C2D、T2C |
| 硕博论文 | 搜索范围选"篇名"，文献类型选"学位论文" | T2C（必须） |
| CSSCI/CSCD 论文 | 搜索后勾选"核心期刊"筛选 | T2C |
| 引用验证 | 用标题精确搜索，确认作者/期刊/年份匹配 | S6 |

### Step 5: 导出检索结果（可选）

```
如果需要 .nbib 或 RIS 格式导出：
1. 在搜索结果页勾选所需条目
2. 点击"导出/参考文献"
3. 选择 EndNote（输出 .ris）或 RefWorks（输出 .nbib）
4. 下载文件到本地
5. 保存路径：{output_dir}/cnki_export_{keyword}.nbib
```

> **注意：** Playwright MCP 支持文件下载，但下载路径由浏览器默认设置决定。导出后可读取下载的文件内容。

### Step 6: 保存结构化结果

将提取的结果写入 `{output_dir}/cnki_results.md`：

```markdown
# CNKI 搜索结果：{keyword_set}

## 期刊论文
### [标题]
- 作者: ...
- 期刊: ... | 年份: ... | 卷期: ...
- DOI: ...
- 被引: ...
- 来源: [PLAYWRIGHT-CNKI]
- 摘要: ...
- 相关论据: [A1/A2/A3]

## 学位论文
### [标题]
- 作者: ...
- 授予单位: ... | 年份: ...
- 类型: 硕士/博士
- DOI/URL: ...
- 来源: [PLAYWRIGHT-CNKI]
- 摘要: ...
- 相关论据: [A1/A2/A3]
```

所有通过 Playwright MCP 采集的条目标记为 `[PLAYWRIGHT-CNKI]`，区别于用户手动提供的 `[USER-SOURCED]`。

---

## 2. 万方数据检索流程

CNKI 查不到时备选。步骤与 CNKI 基本相同：

1. 导航至 `https://www.wanfangdata.com.cn`
2. 登录检查（同上，需要用户手动登录）
3. 输入关键词搜索，提取结果
4. 输出到 `{output_dir}/wanfang_results.md`

---

## 3. DOI 浏览器验证流程

适用于 S6 引文验证中 API 无法解析的 DOI。

```
输入：一个或多个 DOI 列表（来自参考文献）

对于每个 DOI：
1. 使用 Playwright MCP 导航至 https://doi.org/{doi}
2. 等待自动重定向到 publisher 页面（Springer、Elsevier、CNKI 等）
3. 提取页面标题（应与论文标题匹配）
4. 提取作者、期刊、年份
5. 对比与 BibTeX 中的元数据
6. 如果一致 → 标记 [VERIFIED: BROWSER]
7. 如果不一致或 404 → 标记 [NEEDS USER CONFIRMATION]

输出：{output_dir}/doi_browser_verification.md
```

> **中文文献 DOI 解析局限性：** CNKI 的中文论文很多没有 DOI，或 DOI 不在 CrossRef 索引中。
> 此时直接用 CNKI 搜索流程（第 1 节 Step 4 的"引用验证"模式）——用标题搜索确认元数据。

---

## 4. Google Scholar Snowballing 流程

用于论文 snowballing（S2、S2-LR），补充 API snowballing 的覆盖不足。

```
输入：论文标题列表（通常来自 literature_search.py 输出）

对于每篇论文：
1. 使用 Playwright MCP 导航至 https://scholar.google.com
2. 输入论文标题搜索
3. 在结果中点击目标论文
4. 点击 "Cited by N" 链接
5. 提取被引论文列表（标题、作者、年份、摘要片段）
6. 翻页查看更多被引
7. 对发现的被引论文，将 DOIs/titles 加入 bibliography

如果论文的 "Cited by" 数量在 Google Scholar 上远多于
literature_search.py 的 forward citation 数量，说明 API 覆盖不足，
以 Google Scholar 的数据为准（但需要后续 DOI 验证）。

输出：{output_dir}/scholar_snowballing.md
```

---

## 5. 通用原则

1. **登录一次性：** 用户只需在浏览器弹窗后手动登录一次。Playwright MCP 的浏览器会话保持，后续所有操作（搜索、翻页、导出）自动完成。
2. **来源标记：** 所有通过 Playwright MCP 提取的条目标记 `[PLAYWRIGHT-CNKI]` 或 `[VERIFIED: BROWSER]`，与人工提供的 `[USER-SOURCED]` 区分。
3. **失败降级：** 如果浏览器自动化失败（页面结构变化、验证码、网络问题），降级为原来的人工模式——提示用户手动搜索并贴结果。
4. **交叉验证：** 浏览器提取的结果仍需要通过 C2F（可信度筛选）—— 不会因为流程自动化就降低验证标准。
6. **文件下载：** Playwright MCP 支持文件下载（.nbib、.ris），但路径由浏览器配置决定。下载后通过 Read 工具读取文件内容。

---

## 6. CNKI Citation Tracing（中文雪球追溯）

Chinese papers on CNKI have no DOI-based snowballing via Semantic Scholar API. Instead, manually trace citation networks through CNKI's paper detail pages using Playwright MCP. This is the Chinese analogue of the English snowballing in `literature_search.py` (`--seed-dois` → forward/backward citation tracing via API).

**Trigger:** Run after CNKI search completes (C2D or T2C). Apply to the top-5 most relevant or most-cited Chinese papers.

### Step 1: Navigate to Paper Detail Page

From the CNKI search results list, click the title of one of the top-5 papers to open its detail page. Wait for the page to fully load.

### Step 2: Locate the 引文网络 (Citation Network) Section

On the paper detail page, locate the "引文网络" section. This typically contains four sub-sections:

| Sub-section | Chinese | Meaning | Snowballing Direction |
|------------|---------|---------|----------------------|
| References | 参考文献 | Papers cited BY this paper | Backward (what this paper builds on) |
| Citing papers | 引证文献 | Papers that cite THIS paper | Forward (who built on this work) |
| Co-cited papers | 共引文献 | Papers cited alongside this one | Context (shared intellectual base) |
| Co-citing papers | 同被引文献 | Papers citing the same sources | Context (shared intellectual influence) |

Focus on 参考文献 (backward) and 引证文献 (forward) — these are the highest-signal traces. 共引文献 and 同被引文献 are optional, only if time permits.

### Step 3: Scrape Citation Lists

For each sub-section (参考文献 and 引证文献 at minimum):

```
1. Click to expand the section if collapsed (look for "更多>>" or "展开" links)
2. Extract each entry: paper title, authors, journal/university, year
3. If the list spans multiple pages, navigate pagination and repeat
4. Record all newly discovered papers
```

Extract at minimum: Chinese title, English title (if shown), first author, year, journal/university name. Note whether each entry is a journal paper [J] or dissertation [D].

### Step 4: Filter Results

- Keep papers within the search year range (extend range by +/- 2 years for foundational works that may be older)
- Prioritize 核心期刊 (core journals) and 学位论文 (dissertations)
- Discard any paper already present in the primary CNKI search results (T2C/C2D output)
- Discard papers that are clearly off-topic

### Step 5: Add Discovered Papers to Output

Append newly discovered papers to the stage output file with source tag `[CITATION-TRACE-CN]`:

```
### [Chinese Title] ([English Translation])
- Authors: ...
- Year: ... | Journal/University: ...
- Source: [CITATION-TRACE-CN]
- Discovered via: [Seed paper title] (引文网络 — 参考文献/引证文献)
- Type: [J] / [D]
- Relevance: 1-2 sentences explaining relevance
```

### Step 6: Handle Limitations

- CNKI's 引文网络 may not load if the user's institution lacks full database access → skip with note `[TRACE-SKIPPED: no institution access]`
- Older papers (< 2000) may have empty or incomplete citation sections → skip with note `[TRACE-SKIPPED: no citation data available]`
- Time budget: spend no more than 3 minutes per seed paper on citation tracing (approximately 1 minute to open detail page + 2 minutes to scrape lists)
- If Playwright MCP fails entirely → note `[TRACE-SKIPPED: browser automation unavailable]` and proceed without (this is a manual enhancement, not a gate-blocking requirement)

### Output Tag Convention

All papers discovered through this method get `[CITATION-TRACE-CN]`. This distinguishes them from:
- `[PLAYWRIGHT-CNKI]` — primary CNKI search results
- `[USER-SOURCED]` — manually provided by user
- `[OPEN-ACCESS]` — found via open access channels
- `[CROSSREF]` — indexed in CrossRef

This provenance tagging enables future stages to know how each Chinese paper was discovered.
