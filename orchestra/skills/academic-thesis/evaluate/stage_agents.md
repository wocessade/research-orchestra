# Evaluate Module: Agent Dispatch Template

**Used by:** T5 (Thesis Review)
**Module path:** `evaluate/` (shared canonical in `academic-shared/evaluate/`)

## Procedure

### Step 1: Determine Tier

- T5 with `discipline=general` and `degree=bachelor` → tier = `humanities_bachelor` (routes to humanities-specific config and agent prompts)
- T5 with `discipline=stem` and `degree=bachelor` → tier = `stem_bachelor` (routes to STEM-specific v2 config and agent prompts)
- T5 with `degree=master` → tier = `master` (routes to master-specific config with ethics_reviewer)

### Step 2: Load Config

Open `{pipeline_root}/evaluate/config/{tier}.yaml`. From the config, determine:
- Which agents to dispatch (from `dimensions[].agents`)
- Weights and grade thresholds (for scoring.py later)

### Step 3: Create agent_reports directory

```bash
mkdir -p {output_dir}/agent_reports
```

### Step 4: Parallel Agent Dispatch (Triplicate)

For each unique agent in `dimensions[].agents`:

1. Read prompt. For `humanities_bachelor` tier, read from `{pipeline_root}/evaluate/agents/humanities/{agent_id}.md`. For `stem_bachelor` tier, read from `{pipeline_root}/evaluate/agents/stem/{agent_id}.md`. For `master` tier, read from `{pipeline_root}/../academic-shared/evaluate/agents/{agent_id}.md`.
2. **Scoreless agents** (dimension has `scoreless: true`): Launch **1 copy** (single run), EXCEPT ai_tone_detector which uses 3 copies (scoring.py fuses deep patterns across 3 reports for AI-tone curve computation). Scoreless agents write to `{output_dir}/agent_reports/{agent_id}_review.md` (no number suffix). No DIMENSION_SCORE expected — output is issues only.
3. **Scored agents** (all others): **Launch 3 copies** of each agent as parallel subagents to counter LLM score variance. Each agent writes its review to `{output_dir}/agent_reports/{agent_id}_review_{N}.md` where N = 1, 2, 3.
4. Agent output must follow 3-part format. **ai_tone_detector** (triplicate scoreless — curves + deep patterns), **factual_accuracy**, and **ethics_reviewer** (single scoreless) do NOT output DIMENSION_SCORE (qualitative/gate only). All other agents end with `DIMENSION_SCORE: <0-100>`.
5. AI_MARKERS block required for ai_tone_detector agent

**Triplicate naming convention (scored agents only):**
- `content_reviewer_review_1.md`, `content_reviewer_review_2.md`, `content_reviewer_review_3.md`
- `ai_tone_detector_review_1.md`, ... (all 3)
- etc.

**Single-run naming convention (scoreless agents):**
- `factual_accuracy_review.md` (no number suffix)

**scoring.py** reads all 3 for scored agents, extracts DIMENSION_SCORE from each, computes median, and checks variance.
If max-min > 15 points: flagged as HIGH VARIANCE (agent unstable, report shows warning).
The median run's file is used for issue extraction and AI_MARKERS.

For scoreless agents (`scoreless: true` in config): scoring.py reads the report file(s), extracts issues only (no score). ai_tone_detector is triplicate even though scoreless — scoring.py fuses deep patterns across 3 reports for AI-tone curve computation. ethics_reviewer does not output AI_MARKERS block.

All agents are independent → dispatch simultaneously.
Total: 3 × N unique scored agents + 3 (ai_tone_detector triplicate scoreless) + 1 × other scoreless agents (e.g., for humanities bachelor: 7 unique scored agents × 3 = 21 + ai_tone 3 + factual_accuracy 1 = 25 total dispatches). Note: unique agent count may differ from dimension count when one agent serves multiple dimensions (e.g., content_reviewer_humanities serves both argument_quality and textual_analysis). See config YAML `# @agent-count:` for dimension counts.

### Step 4.5: Cross-Model Verification (conditional)

**条件：** 环境变量 `CROSS_MODEL_ENABLED=true` 且 `OPENAI_API_KEY` 已设置

从主模型评估结果中提取 Top-5 权重最高的论述（跨所有 agent 的 Critical+Major 发现），
调用 `python academic-shared/evaluate/scripts/cross_model_verify.py`。

```bash
# Extract Top-5 claims from Critical+Major findings into claims.json, then:
python {pipeline_root}/../academic-shared/evaluate/scripts/cross_model_verify.py \
  --input {output_dir}/paper.txt \
  --claims {output_dir}/claims.json \
  --provider openai \
  --model gpt-4o \
  --output {output_dir}/cross_model_report.json
```

输出写入 `{output_dir}/cross_model_report.json`。
如果跨模型 verdict 与主模型分歧 > 30% → 在最终报告中标记 `[CROSS-MODEL-DISAGREEMENT]`。
分歧项在 scoring 中不改变主模型评分，但在报告中附加 cross-model 意见供用户参考。

### Step 5: Score and Report

After all agents complete, run:

```bash
python {pipeline_root}/../academic-shared/evaluate/scripts/scoring.py \
  --tier {tier} \
  --config-dir {pipeline_root}/evaluate/config/ \
  --agent-reports-dir {output_dir}/agent_reports/ \
  --output-dir {output_dir}/ \
  --paper-text {output_dir}/paper.txt \
  [--discipline stem|humanities] \
  [--calibration {pipeline_root}/evaluate/calibration/{tier}_calibration.yaml] \
  [--previous-report-dir {output_dir}/] \
  [--passport-state {output_dir}/.pipeline_state.json] \
  [--evidence-grades {output_dir}/evidence_grades.json]
```

### Step 6: Present Findings

Read `{output_dir}/report.md` and present to user:
1. Grade (优/良/中/差) with calibration hint
2. Dimension scores
3. Gate blockers (if any)
4. Variance warnings (if any agent had unstable scores)
5. Issue list (Critical/Major/Minor)
