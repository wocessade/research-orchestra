# Composer: Evidence Ledger Generation

**Purpose:** Generate per-claim evidence ledger entries for every cited claim, creating a machine-auditable record of all claims and their sources.
**Used by:** S4 (section writing), S7 (factual accuracy audit), T4 (thesis chapter writing)
**Parameters:** `output_dir` (ledger file path), manuscript section/chapter being written

## Instructions

### 1. When to Generate

After writing each section or chapter, generate evidence ledger entries for every claim that has a citation `[...]`. Each cited claim produces exactly one entry.

### 2. Per-Claim Entry Format

Append each entry to `{output_dir}/evidence_ledger.jsonl`:

```json
{
  "claim_id": "CLM-001",
  "section": "2.3",
  "paragraph_index": 4,
  "claim_text": "Prior work has shown that FL reduces communication costs by up to 40%.",
  "source_ref": "[McMahan et al., 2017]",
  "source_excerpt": "FedAvg reduces communication rounds by 10-100x...",
  "confidence": "high",
  "claim_type": "factual",
  "audit_status": "pending"
}
```

### 3. Field Specification

| Field | Description | Rules |
|-------|-------------|-------|
| `claim_id` | Unique identifier | Sequential: `CLM-001`, `CLM-002`, ... |
| `section` | Section or chapter number | e.g., `"2.3"`, `"第2章"` |
| `paragraph_index` | Paragraph index within section | 0-based or 1-based, consistent throughout |
| `claim_text` | The exact claim as written | Verbatim from manuscript |
| `source_ref` | Citation identifier | Matches the `[...]` or `(Author, Year)` in text |
| `source_excerpt` | Supporting excerpt from source | Actual text from the cited document |
| `confidence` | Confidence level | `high` if direct source excerpt access; `low` if memory-based |
| `claim_type` | Type of claim | One of: factual / attribution / method / result / interpretation |
| `audit_status` | Audit tracking | Initial value: `"pending"` |

### 4. Claim Type Enumeration

| Type | Description | Examples |
|------|-------------|----------|
| `factual` | Stated fact or finding | "X reduces cost by 40%" |
| `attribution` | Attributing a position to a source | "Smith argues that..." |
| `method` | Describing a method used | "They used FedAvg with..." |
| `result` | Reporting a specific result | "Accuracy reached 92.3%" |
| `interpretation` | Interpretation or implication | "This suggests that..." |

### 5. Confidence Rules

- `high` -- you have direct access to the source excerpt (the text is in front of you or in your context). Include the actual `source_excerpt` in the entry.
- `low` -- the claim is based on your training memory, not direct access to the source. The `source_excerpt` should note this (e.g., "from training memory -- verify against actual source").

### 6. Skip Rule

Skip uncited factual statements that represent common knowledge in the field. Only generate entries for claims that have an explicit citation reference.

### 7. File Path Convention

- File: `{output_dir}/evidence_ledger.jsonl`
- Create the file if it does not exist.
- Append each entry as a newline-delimited JSON line (one JSON object per line).
- Do not overwrite -- always append.

### 8. Usage by Downstream Stages

Ledger entries are consumed at S7 by the `evidence_ledger_auditor` to verify source accuracy against actual source documents. The `audit_status` field is updated during the audit from `"pending"` to `"verified"`, `"discrepancy_found"`, or `"needs_review"`.

## Verification

- [ ] Each cited claim has exactly one ledger entry (same citation in multiple paragraphs = separate entries)
- [ ] All JSONL lines are valid JSON (no trailing commas, no malformed objects)
- [ ] `confidence` is correctly assigned: `high` only when source excerpt is directly accessible
- [ ] `claim_type` is one of the five enumerated values
- [ ] Uncited common knowledge statements are excluded
- [ ] Ledger file path correctly uses `{output_dir}/evidence_ledger.jsonl`
- [ ] Each entry appends (no overwrites)
- [ ] `audit_status` is initially `"pending"` for all entries

## Common Pitfalls

- **Duplicate entries:** Generating multiple entries for the same claim in the same paragraph. One claim = one entry.
- **Missing entry for cited claim:** Forgetting to generate an entry for a paragraph that has citations. Scan every paragraph with `[...]` or `(Author, Year)` patterns.
- **Overwriting the file:** Using `w` mode instead of `a` (append). Always append.
- **Memory-based confidence mislabel:** Setting `confidence: high` when the source excerpt is from memory rather than direct access. Be honest -- mark as `low` so the auditor knows to verify.
- **Wrong claim_type:** Using `factual` for everything. Differentiate: a direct quote from a paper about their method is `method`, not `factual`.
- **Including uncited statements:** Generating entries for claims like "Deep learning has transformed NLP" that are common knowledge without a citation. Skip these.
