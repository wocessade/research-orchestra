# Tavily Search for Academic Paper Pipeline

Tavily is a structured web search API designed for AI agents. It returns clean JSON with source URLs, content snippets, and metadata.

## When to Use Tavily (Not Academic Databases)

| Tavily Is Best For | Academic Database Is Better |
|-------------------|---------------------------|
| Latest news / real-time events | Peer-reviewed journal papers |
| Tech blogs / engineering reports | DOI-verified citations |
| Industry reports / market data | Citation network analysis |
| Policy documents / regulations | Snowballing from seed DOIs |
| Official documentation / standards | Bibliographic metadata |
| Image search for references | Quality-scored literature matrix |

**Critical rule:** Tavily results are **web content**, NOT verified academic sources. Never cite a Tavily result as a peer-reviewed reference. Use Tavily for body-text context, real-world examples, and background material — then cite the official source URL, not the Tavily response.

## API Usage

```python
import httpx

response = httpx.post(
    "https://api.tavily.com/search",
    headers={"Content-Type": "application/json"},
    json={
        "api_key": tavily_api_key,
        "query": "search query here",
        "search_depth": "basic",       # "basic" (faster) or "advanced" (deeper)
        "max_results": 5,              # 1-20
        "include_answer": False,       # short AI-generated answer
        "include_raw_content": False,  # full page content (costlier)
        "include_images": False,       # include image results
    },
)
results = response.json()
```

## Parameter Guide

| Parameter | Default | When to Change |
|-----------|---------|---------------|
| `search_depth` | `basic` | Use `advanced` for deep-research queries (policy, standards, niche topics) |
| `max_results` | 5 | Use 8-10 for literature context search; 3-5 for quick fact checks |
| `include_answer` | False | Use True when you want a concise summary alongside results |
| `include_raw_content` | False | Use True when you need full page text for analysis (costs more tokens) |
| `include_images` | False | Use True during S5 for image reference search |

## Web Source 2D Quality Scoring

Every Tavily result gets a **2D quality score** (0-10 scale), parallel to the academic 3D scoring system but adapted for web content.

### Scoring Dimensions

| Dimension | Weight | Scoring Rules |
|-----------|--------|--------------|
| `domain_authority` | 0.55 | `.gov/.edu/.mil` = 9.0, standards body (ISO, IEEE-SA, IETF) = 8.5, major tech publication (Wired, Ars Technica, Nature News, MIT Tech Review) = 7.0, company official blog / documentation = 6.0, known news outlet (Reuters, BBC, NYT) = 5.5, Medium / personal blog = 3.0, unknown domain = 2.0, social media = 1.0 |
| `content_depth` | 0.45 | Technical report / staff paper / lengthy analysis (2000+ words, data-backed) = 9.0, detailed article with references (1000-2000 words) = 7.0, overview / summary (300-1000 words) = 5.0, press release / shallow coverage = 3.0, placeholder / aggregator = 2.0 |

**Composite = 0.55 × domain_authority + 0.45 × content_depth**

Rounded to one decimal place. Interpretation:
- **7.0-10.0 (High):** Authoritative, substantive content. Use as supporting evidence.
- **4.0-6.9 (Medium):** Decent source. Use as background only.
- **0.0-3.9 (Low):** Weak or unverifiable. Flag for caution.

### Timeliness Bonus (Separate Label)

Does NOT affect composite score. Appended as a label:

| Label | Criteria |
|-------|----------|
| `[RECENT]` | ≤ 3 months old |
| `[CURRENT]` | 3-12 months old |
| `[AGING]` | 1-2 years old |
| `[OUTDATED]` | \> 2 years or no detectable date — mark with warning |

### Comparison to Academic 3D Scoring

```
Academic 3D:   composite = 0.40×source_authority + 0.25×timeliness + 0.35×relevance
Web 2D:        composite = 0.55×domain_authority + 0.45×content_depth
```

The scales are aligned (0-10) but measure different things:
- Academic score = citation-based authority + recency + topical match
- Web score = domain trust + content substance

A web source scoring 8.5 is **not** equivalent to a journal paper scoring 8.5 — they are reviewed, but the web score helps prioritize reading order, filter noise, and flag high-quality grey literature.

## Output Entry Format

Each Tavily result entry should include the 2D score:

```
- {Title} — [OFFICIAL] [CURRENT] — 2D Score: 7.2 (auth: 8.5 | depth: 5.5)
  URL: {url}
  Key information: 1-2 sentence summary
  Relevance: how this connects to the research gap / argument
```

## Query Templates by Stage

### S2 (Literature Review — Web Context)
```
query: "latest advances in {topic} 2026"
query: "{research_topic} industry applications case study"
query: "{research_topic} open source implementation"
query: "{research_topic} policy regulation update"
```

### C2 (Course Assignment — Web Context)
```
query: "{topic} technology overview latest development"
query: "{topic} industry report 2025 2026"
query: "{topic_zh} 最新进展 行业应用"
query: "{topic_zh} 相关政策 技术标准"
```

### T2 (Thesis — Policy & Industry)
```
query: "{topic} national policy regulation standard"
query: "{topic_zh} 国家标准 行业规范"
query: "{topic} industry white paper technical report"
query: "{topic_zh} 政策文件 发展规划"
```

### S5 (Figures — Image Reference Search)
```
query: "{topic} diagram architecture flowchart"
query: "{topic} data visualization example"
query: "{topic} result chart graph"
```

With `include_images: true`, the response includes `image_urls` array for visual reference.

## Result Processing

Tavily returns this structure:

```json
{
  "results": [
    {
      "title": "Page Title",
      "url": "https://...",
      "content": "Page content excerpt...",
      "score": 0.95,
      "raw_content": null
    }
  ],
  "answer": "Optional AI-generated answer if include_answer=true",
  "image_urls": ["https://..."]
}
```

For each result used in the paper:
1. **Classify source type:** [OFFICIAL] / [INDUSTRY] / [NEWS] / [BLOG]
2. **Apply 2D score:** domain_authority + content_depth, with timeliness label
3. **Verify the URL is accessible** — open it via WebFetch if unsure
4. **Extract the publication date** — check `content` for date mentions
5. **Every Tavily-discovered fact in the paper body must cite a verifiable source URL**

## Web → Academic Cross-Reference

For the complete Web → Academic cross-reference procedure, see `static/core/web-search-policy.md` §Web → Academic Cross-Reference. That policy file is the canonical source; this section previously duplicated it.

## Important Limitations

- **No academic citation discovery** — Tavily does NOT index paywalled academic papers or their metadata. Use paper-lookup for that.
- **Content freshness** — Tavily prioritizes recent content. For historical context, use browser-based search or paper-lookup.
- **Rate limits** — The free tier has limited queries. Use `basic` depth and `max_results: 5` unless more is needed.
- **No Chinese database access** — CNKI/Wanfang content is not accessible via Tavily. Use Playwright MCP for Chinese academic sources.
