# 5-Step Reference Verification Pipeline

受 Research-Skills 启发，将引用验证从"DOI 是否存在"扩展为完整的 5 步管线。

## 步骤

```
Search ─→ Verify ─→ Retrieve ─→ Validate ─→ Add
  │          │          │            │          │
  │          │          │            │          └── 生成格式化引用
  │          │          │            └── 与 evidence ledger 交叉验证
  │          │          └── 获取摘要/原文摘录
  │          └── 跨 API 一致性确认
  └── 多库搜索
```

### Step 1: Search（多库搜索）

查询 Semantic Scholar、CrossRef、OpenAlex 三个 API 寻找候选匹配。

**已实现:** `literature/verify_citations.py` 的 DOI 查找 + 标题搜索

### Step 2: Verify（跨 API 验证）

至少一个 API 确认 → `true`；有 DOI 但全不匹配 → `false`（伪造嫌疑）；仅有标题匹配 → `unresolvable`。

**已实现:** `compute_verdict()` 的三源投票判决

### Step 3: Retrieve（获取摘要/摘录）

验证通过后，从匹配源获取原文摘要和元数据。

**实现方式:** `verify_citations.py` 新增 `--fetch-abstracts` 模式
- 对 `verdict=true` 的条目，获取 abstract / key sentences
- 输出格式: `{citation_key, abstract, sections_count, retrieval_date}`
- 输出文件: `{output_dir}/retrieved_abstracts.json`

### Step 4: Validate（与 Evidence Ledger 交叉验证）

将验证结果与 evidence ledger 中的 claim 引用进行比对。

**依赖:** Phase 3 (Evidence Ledger) 的 `evidence_ledger.jsonl`
- 读取 ledger 中的 `source_ref` 与 `source_excerpt`
- 对照 `retrieved_abstracts` 验证 `source_excerpt` 是否真正存在于原文中
- 输出: `validation_report.json`

### Step 5: Add（生成格式化引用）

为已验证的引用生成 BibTeX / APA / GB/T 7714 格式输出。

**实现方式:** `verify_citations.py` 新增 `--format-output` 模式
- 输入: `verification_report.json` 中 `verdict=true` 的条目
- 输出: `{output_dir}/verified_references.bib`（BibTeX）+ `verified_references.txt`（APA/GB/T 7714 格式）

## CLI 集成

```bash
# 完整 5-step 管线（单次执行）
python literature/verify_citations.py \
  --input bibliography.json \
  --output-dir ./output \
  --fetch-abstracts \
  --format-output

# 仅验证（Step 1-2）
python literature/verify_citations.py \
  --input bibliography.json \
  --output-dir ./output

# 验证 + 摘要获取（Step 1-3）
python literature/verify_citations.py \
  --input bibliography.json \
  --output-dir ./output \
  --fetch-abstracts

# 与 evidence ledger 交叉验证（Step 4, 需要 ledger + 验证报告）
python literature/verify_citations.py \
  --validate-ledger ./output/evidence_ledger.jsonl \
  --verification-report ./output/verification_report.json \
  --output-dir ./output
```

## 集成到 Stage

- **S2 / T2 / C2 文献检索阶段:** 运行 Step 1-3
- **S7 / T5 / C4 评审阶段:** 运行 Step 4（如果 ledger 存在）
- **最终提交准备:** 运行 Step 5 生成格式化引用列表
