# Common Mistakes & Anti-Patterns

Mistakes observed in pipeline execution that waste context, produce incorrect output, or violate pipeline rules.

## Writing & Revision

### S7 Q7 失败后直接回 S3 重写而不先检查 S6 引用
**Problem:** Gate Q7 fails on content quality, so the pipeline jumps back to S3 to restructure/write, but the root cause is incorrect citations from S6. Rewriting won't fix citation errors.
**Correct:** When Q7 fails, first check: are the failures related to cite-able claims? If yes → re-audit S6 citations before touching S3/S4 text.

### S9 审稿循环中反复修改但不重新调用 paper-audit
**Problem:** Each S9 revision round modifies text, but paper-audit is not re-run to verify fixes. The same issues may persist or new ones may be introduced.
**Correct:** Every S9 revision round must include a paper-audit re-run. The exit protocol's intra-stage loop detection will catch this — modifying the same paragraph ≥3 times without re-running paper-audit triggers an exit evaluation.

### 中文论文用英文写作思维再翻译
**Problem:** Writing in English first then translating to Chinese produces stilted, unnatural prose with English sentence structures mapped to Chinese words.
**Correct:** When `language=zh`, write in Chinese from the start. The writing protocol (claim→evidence→analysis) is language-agnostic but the prose must originate in Chinese. Use `chinese-de-ai-quick-ref.md` for Chinese-specific AI-tone detection, not translation-based checks.

## Venue & Formatting

### S8.6 未做栏目匹配就开始格式化
**Problem:** The pipeline formats the manuscript before checking whether the target journal has a matching column/section for the paper type. Result: formatted manuscript doesn't fit any journal section.
**Correct:** S8.6A (journal qualification) includes a column/section match check. Run it before S8 formatting. For Chinese domestic journals, this is a hard requirement — many 学报 journals have fixed columns (e.g., "计算机科学与技术", "经济与管理") and won't accept papers outside those columns.

### S8.5 选刊后跳过 S8.6 直接格式化
**Problem:** For `venue=chinese-domestic`, selecting a journal at S8.5 and then going directly to S8 formatting, skipping the S8.6 execution layer (journal qualification, reverse engineering, positioning audit).
**Correct:** Manifest.yaml routing: S8.5 → S8.6 (when venue=chinese-domestic) → S8. Never skip S8.6 for Chinese domestic journals. The execution layer catches format requirements, section matching, and positioning issues that generic S8 formatting won't find.

## Parallel & Agent Execution

### 并行 agent 失败后不触发 fallback 就继续
**Problem:** A parallel agent fails (e.g., one search domain in C2, one review lens in C4), but the pipeline proceeds with partial results without logging the gap or offering manual fallback.
**Correct:** Follow `parallel-groups.md` partial failure handling. 1 failure → retry once → if still fails, classify dependency and either skip (no downstream) or degrade to manual checklist (has downstream). 2+ failures → STOP-AND-ASK.

### 将所有 agent 原始输出直接塞入主上下文
**Problem:** Running 4 review agents in parallel, then reading all 4 raw outputs into the main context for "merging." Each agent output is ~10K tokens → 40K+ tokens consumed.
**Correct:** Each agent writes structured output to a file. A merge script extracts key findings into a consolidated table. Only the merged table enters the main context. See `context-budget.md` result merging rule.

## Advisor & Review

### 导师反馈未分类就直接修改
**Problem:** Receiving advisor feedback as a block of comments, then jumping into line-by-line editing without first categorizing. Easy to miss items, especially cross-cutting concerns.
**Correct (T1/T3/T4 advisor loop):**
1. Parse feedback into categorized items (topic/structure/method/writing/format)
2. Assign priority (Critical/Major/Minor)
3. Draft modification plan for each item
4. Present the plan to the user BEFORE making changes
5. Track each item: original feedback → action taken → location changed → resolved?

### 导师反馈轮次超出 3 轮仍继续
**Problem:** The advisor review loop keeps iterating without checking the 3-round hard limit.
**Correct:** T1/T3/T4 have a 3-round max per advisor node. After 3 rounds, STOP-AND-ASK: "After 3 rounds of advisor feedback, {N} items remain. Options: (A) accept remaining as deliberate choices, (B) schedule an in-person meeting with advisor, (C) escalate to department."

## Pipeline Mechanics

### 预加载未来阶段
**Problem:** While in S4 writing, the pipeline references "in S7 we'll polish this" or "S9 will catch this." This violates "one stage at a time" and wastes context on premature optimization.
**Correct:** Focus on the current stage. If a quality concern is valid for the current stage, address it now. If it's genuinely a future-stage concern, trust the pipeline — it will be caught at the appropriate gate.

### Gate SOFT BLOCK 被当作 BLOCK 处理
**Problem:** A SOFT BLOCK gate fails, but the pipeline treats it as a hard stop and refuses to proceed, wasting time on an advisory check.
**Correct:** SOFT BLOCK can be overridden with a documented reason. The override reason is recorded in session state. Only BLOCK gates are hard stops.

### 重写用户内容而非标记建议
**Problem:** The pipeline overwrites user-written sections without preserving the original or asking permission. Violates the "append-only" rule.
**Correct:** Never overwrite user-written content. Add suggestions as comments/tracked changes, flag issues with severity, let the user decide. The only exception is format/compile fixes at S8 that are mechanically required.

## 参考文献

### 参考文献未按引用顺序编号 / 包含未引用文献
**Problem:** 正文引用标记为 `[1]`–`[16]` 的乱序，且参考文献列表包含正文从未引用的条目。这是 C2 生成的 bibliography 按主题分组排列，C3 直接照搬该顺序不改号所致。用户看到"参考文献怎么是乱序的"，且无引用条目占据版面。
**Correct (C3/T4/S4 writing stages):**
1. 正文写入**完成后**，扫描全文提取所有 `[N]` 引用标记，**按首次出现顺序**重新编号为 1, 2, 3...
2. 参考文献列表中**只保留**至少被正文引用过一次的条目。凡在正文扫描中未出现的 citation_key 或 `[N]` 号，一律从列表删除
3. 如果正文引用和参考文献列表不在同一阶段生成（如 C3 脚本一次性生成），则写作脚本体内必须实现上述扫描→排序→过滤逻辑，不能依赖人工后处理
4. 写作阶段的 gate check 必须增加一条：**"所有参考文献均有正文引用对应 / 参考文献按首次引用顺序排列"**

## literature_search.py 相关

### 初始搜索路径不对导致找不到工具
**Problem:** 在 S2/C2 阶段调用 `literature_search.py` 时，先在项目目录（`D:\pythonProject`）搜索 `**/literature_search.py`，没找到后才去 skills 目录搜索，浪费了时间并误导用户以为工具不存在。
**Correct:** 首次搜索路径应同时覆盖 `{pipeline_root}`（skills 目录）和项目目录。pipeline 启动时 manifest.yaml 已定义了 `pipeline_root` 变量，直接用它定位。

### Semantic Scholar API 不可用导致长时间等待
**Problem:** literature_search.py 默认同时搜索 openalex、semanticscholar、crossref 三个源。Semantic Scholar API（`api.semanticscholar.org`）在国内网络环境下返回 `ConnectionRefusedError`，每次超时需等待 4-7 分钟才放弃，导致整个搜索命令被拖慢数倍。
**Correct:** 在首次调用 literature_search.py 前，先测试 Semantic Scholar 连通性：
```python
import httpx
try:
    httpx.get("https://api.semanticscholar.org/graph/v1/paper/search?query=test", timeout=5)
except Exception:
    print("[WARN] Semantic Scholar unreachable — excluding from sources")
```
如果不可达，`--sources` 中排除 `semanticscholar`，只保留 `openalex,crossref`。对于硕士论文搜索等需要 Semantic Scholar 的场景，使用 playwright-browser 直接打开网页版作为 fallback。

### --output-format 参数与输出文件后缀不匹配
**Problem:** 使用 `--output-format summary` 时，工具输出的是纯文本 markdown 内容，但输出文件命名为 `.json` 后缀（如 `c2b_electronic_nose_food.json`）。后续代码用 `json.load()` 读取时报 `JSONDecodeError`。
**Correct:** 输出文件后缀必须与 `--output-format` 一致：
- `--output-format json` → `.json` 文件
- `--output-format summary` → `.md` 文件
- `--output-format bibtex` → `.bib` 文件

或者在脚本中根据 `output_format` 参数自动设置文件后缀。

## 环境与编码

### Cygwin/Windows Bash 中文与 emoji 编码问题
**Problem:** Cygwin bash 终端默认使用 GBK 编码，Python 的 `print()` 在输出 emoji（如 ✅）或中文字符时触发 `UnicodeEncodeError: 'gbk' codec can't encode character`。同样，文件路径中的中文也会被 bash 终端显示为乱码。
**Correct:** Python 脚本中避免直接 print emoji；文件路径使用纯英文命名或通过 `PYTHONIOENCODING=utf-8` 环境变量覆盖。写入 .docx 等二进制文件不受影响，仅终端输出有问题。参见 `memory/MEMORY.md` 中 Cygwin bash 中文编码问题的已有记录。
