# Stage C4: 课程作业审查 [Strategist]

**Gate:** QC4 (BLOCK)
**Goal:** Multi-dimensional quality review of the draft covering structure, factual accuracy, AI tone, formatting, and citation quality
**Needs Composers:** [factual-accuracy-check, de-ai-detect, paper-audit-orchestration]

## Decisions

### Axis Routing

#### DP18: 6 Parallel Review Dimensions — Evaluate Module (C4B)

Load `evaluate/stage_agents.md` and dispatch agents with tier=`course`. Config: `evaluate/config/course.yaml` (shared from `../academic-shared/evaluate/config/course.yaml`).

| Dimension | Agent | Type |
|-----------|-------|------|
| 1. Content & Depth | `content_reviewer` | scored (×3) |
| 2. Structure & Logic | `structure_reviewer` | scored (×3) |
| 3. AI Tone Detection | `ai_tone_detector` | scored (×3, for AI tone curve) |
| 4. Format & Style | `format_compliance` | scored (×3) |
| 5. Logic Consistency | `logic_consistency` | scored (×3) |
| 6. Factual Accuracy | `factual_accuracy` | scoreless (×1) |

Before running scoring.py, extract plain text from the .docx:
```bash
python -c "from docx import Document; import sys; text = '\n'.join(p.text for p in Document(sys.argv[1]).paragraphs); open(sys.argv[2], 'w', encoding='utf-8').write(text)" \
  {output_dir}/draft.docx {output_dir}/paper.txt
```

Run scoring.py:
```bash
python {pipeline_root}/../academic-shared/evaluate/scripts/scoring.py \
  --tier course \
  --config-dir {pipeline_root}/../academic-shared/evaluate/config \
  --agent-reports-dir {output_dir}/agent_reports \
  --output-dir {output_dir} \
  --paper-text {output_dir}/paper.txt \
  --passport-state {output_dir}/.pipeline_state.json
```

Outputs: `{output_dir}/report.md` + `{output_dir}/report.json`

#### Language Auto-Load
- When `language=zh`:
  - Auto-load `references/chinese-de-ai-quick-ref.md` into context for AI tone detection dimension
  - This provides Chinese-specific AI writing pattern heuristics

#### Dedup Rules
- When merging review results across dimensions:
  - If semantically duplicate items found (same issue, same location):
    - Keep the item with the earliest (most severe) severity level
    - Mark deduplicated items with tag `[DEDUP-MERGED]`
  - Do NOT delete any items — preserve full audit trail

#### Conflict Resolution
- **Dimension score conflict:** If two dimensions assign different severity levels to the same issue:
  - Average the severity scores (e.g., Critical+Major → rounded to Major)
- **Factual conflict:** If one dimension says "correct" and another says "incorrect" on same fact:
  - Keep both entries with tag `[CONFLICT]`
  - Human (user) must resolve before gate passage
- **Sorting:** All findings sorted by severity (Critical > Major > Minor > Info)

#### Agent Error Handling
- 1 agent failure → tag replacement agent with `[AGENT-REPLACEMENT]`, re-dispatch
- Replacement also fails → tag as `[AGENT-FAILED]`, continue with remaining dimensions
- 2+ agent failures → STOP-AND-ASK: present partial results, ask user whether to continue or retry

### Composer Sequence
1. **composer:** factual-accuracy-check {draft_path: <path>, mode: coursework}
2. **composer:** de-ai-detect {draft_path: <path>, language: zh, quick_ref: <auto-loaded>}
3. **composer:** paper-audit-orchestration {dimensions: [structure, format, citation, originality], draft_path: <path>}

## Gate

### QC4 Gate Checklist
- [ ] All 6 agents completed — agent reports in `{output_dir}/agent_reports/`
- [ ] `{output_dir}/report.md` generated with grade, blockers, and issue list
- [ ] `{output_dir}/report.json` generated with structured data
- [ ] Dedup and conflict resolution (C4E) applied — merged_report.md with [DEDUP-MERGED] tags and [CONFLICT] markers
- [ ] Critical errors == 0
- [ ] Major errors <= 5 (or user-accepted threshold)
- [ ] AI tone report generated
- [ ] Factual accuracy report with verified/corrected items
- [ ] `--paper-text` extracted and passed to scoring.py
- [ ] Chinese curly quote direction verified (LEFT “ for opening, RIGHT ” for closing; pair-matched per paragraph; imbalance > 2 → flag as format error)

### Gate Failure Route
- Failed QC4 → re-schedule failed review agents (re-run specific dimensions):
  - Re-dispatch only the deficient review agents
  - Merge new results with existing (preserve non-failed dimension results)
  - Fix identified issues → re-evaluate QC4
