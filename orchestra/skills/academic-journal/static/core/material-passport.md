# Material Passport — Cross-Stage Structured Data Carrier

**Purpose:** Standardized data carrier that travels across pipeline stages, carrying structured metadata that individual stages read and write.
**Schema location:** `.pipeline_state.json` → field `passport`
**Loaded:** As part of `static/core/session-persistence.md` state (not as separate file load)

## Schema

```json
{
  "passport": {
    "style_profile": {
      "sentence_length_avg": null,
      "vocabulary_preferences": [],
      "citation_integration_style": "integral",
      "hedging_density": null,
      "register_shifts": null,
      "paragraph_length_avg": null,
      "collected_at": null,
      "sample_text_hash": null
    },
    "evidence_grades": {
      "entries": []
    },
    "preregistration": {
      "document_hash": null,
      "hypotheses": [],
      "analysis_plan": null
    },
    "negative_results_pathway": "standard",
    "confidence_ledger": []
  }
}
```

## Field Lifecycle

| Field | Written By | Read By | Purpose |
|-------|-----------|---------|---------|
| `style_profile` | Stage 1 (style calibration) | Writing/Polish stages | Author voice consistency |
| `evidence_grades` | Literature review (gap analysis) | Writing, claim alignment | GRADE quality tracking |
| `preregistration` | Stage 1 (user provides URL) | Final review (deviation check) | Confirmatory vs exploratory |
| `negative_results_pathway` | Feasibility check | Final review, submission | Null-result-aware routing |
| `confidence_ledger` | evaluate/scoring.py | Final report generation | Agent confidence tracking |
| `stage_completion_log` | Each stage (at gate pass) | Next stage (handoff check) | Stage-to-stage context continuity |

## Stage Completion Log

**Purpose:** 记录每个完成的 stage 的关键输出和决策。供下一 stage 加载时做 handoff check。

**写入时机:** 每个 stage 的 gate 通过后，在写 `.pipeline_state.json` 时追加一条到 `stage_completion_log` 数组。

**字段格式** (JSON 中的单个 entry):

```json
{
  "stage": "S2",
  "completed_at": "2026-06-20T14:30:00",
  "key_output": "30 papers → 5 themes, gap: X not studied in Y",
  "key_decisions": "Excluded Z domain (low relevance)"
}
```

**示例** (`.pipeline_state.json` 中的 `stage_completion_log`):

```json
{
  "passport": {
    ...
    "stage_completion_log": [
      { "stage": "S1", "completed_at": "2026-06-19", "key_output": "RQ defined", "key_decisions": "Chose empirical study over review" },
      { "stage": "S0.5", "completed_at": "2026-06-19", "key_output": "Feasibility: PASS", "key_decisions": "" }
    ]
  }
}
```

## Read/Write Protocol

### Writing
Each stage writes to its passport fields at the end of the stage (before gate evaluation). The orchestrator appends to `.pipeline_state.json`'s `passport` field, never overwriting fields written by other stages.

```json
// Example: after stage 1 writes style_profile
{
  "passport": {
    "style_profile": { ... },
    "evidence_grades": { "entries": [] },
    "preregistration": { ... },
    "negative_results_pathway": "standard",
    "confidence_ledger": []
  }
}
```

### Reading
A stage reads passport fields it needs from `.pipeline_state.json` before executing. If the required field is `null` or missing, the stage silently skips passport-dependent behavior — passport is a soft mechanism.

## Schema Validation Rules

- All fields nullable: if a stage cannot produce the data, set to `null` rather than empty
- `style_profile.sample_text_hash`: SHA-256 first 12 hex chars of the sample text
- `evidence_grades.entries[]`: each entry must have `source_id`, `initial_level`, `final_grade`
- `preregistration.document_hash`: SHA-256 first 12 hex chars of the preregistration document
- `confidence_ledger[]`: each entry must have `agent_id`, `confidence_score`, `timestamp`
