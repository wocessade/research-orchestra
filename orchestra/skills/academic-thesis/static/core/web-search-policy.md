# Web Search Policy

**Priority chain for academic lookups:**

1. **`skills-embedded/paper-lookup.md`** (API, fastest, covers 10+ databases: arXiv, Semantic Scholar, Crossref, OpenAlex, PubMed, etc.) — preferred for all bibliographic searches, DOI verification, and citation lookups
2. **Tavily API** (structured web search for AI agents) — for news articles, tech blogs, industry reports, policy documents, real-time web content, and image search. **Not a substitute for academic databases** — use for real-world context, not for citation discovery. See `references/tavily-search.md` for API usage.
3. **Playwright MCP (headful browser)** — for CNKI/Wanfang/万方/维普 (中文数据库), Google Scholar snowballing, publisher page cross-validation, DeepSeek Chat/ChatGPT deep research, and any page requiring user login. See `references/playwright-browser-automation.md` for workflows.
4. **Web browser (agent-browser)** — for Google Scholar, journal homepages, publisher sites not in paper-lookup's coverage, and any page requiring JavaScript rendering or login (fallback when Playwright MCP unavailable)
5. **`WebSearch`/`WebFetch`** — last resort, plain-text only, for quick fact checks

**When to use Tavily vs. browser:**
- **Tavily** — preferred when the query is structured (keyword-based), the target is public web content (news, blogs, documentation, policy pages), and speed matters. Returns clean JSON with source URLs.
- **Playwright MCP** — preferred when the target requires login (CNKI, DeepSeek Chat, ChatGPT, Google Scholar with cookies), JavaScript rendering, interactive pagination, or when you need to see the page visually.
- **agent-browser** — fallback when Playwright MCP is unavailable; same use cases.

**When to use WebSearch/WebFetch instead:** Only for quick fact checks or when the target is a plain-text page with no login wall, no JavaScript rendering, and no pagination. If in doubt, use paper-lookup, Tavily, or the browser.

### Web → Academic Cross-Reference

Tavily results may contain leads for academic search. When a Tavily result mentions:
- A specific paper title → feed it to `skills-embedded/paper-lookup.md` for DOI lookup
- An author name + research topic → search OpenAlex for that author
- A dataset, benchmark, or standard → search for associated academic publications

This is a structured bridge, not optional. After collecting Tavily results:
1. Extract all academic-looking leads (titles, author names, paper references)
2. Batch-discover via `skills-embedded/paper-lookup.md`
3. Add discovered papers to the academic search results
4. Mark as `[TAVILY-DISCOVERED]` source tag alongside the regular `[LITERATURE-SEARCH]` tag

This closes the loop: Tavily finds what academic databases miss, then feeds back into academic search.
