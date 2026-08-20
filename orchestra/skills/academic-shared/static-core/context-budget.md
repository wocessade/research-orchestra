# Context Window Budget

Parallel agents consume context. Budget them:

| Agent Type | Est. Token Budget | Strategy |
|------------|-------------------|----------|
| Deep-read one paper + structured summary | ~15K tokens per paper | Serialize for 5+ papers: read → extract structured summary → release context → next paper |
| Review persona (methodologist/domain/skeptic/generalist) | ~10K tokens per persona | Parallel OK for 4 personas (each only needs manuscript, not other reviewers' output) |
| Figure generation from tabular data | ~3K tokens per figure | Parallel OK |
| Venue evaluation per journal | ~5K tokens per journal | Parallel OK for 3-5 journals |
| T2 thesis literature search agent (one domain) | ~8K tokens per agent | Parallel OK for 3 agents (independent domains) — each writes structured output. ~24K total across 3 lanes. |
| T5 thesis review agent (one lens) | ~10K tokens per agent | 9-11 agents parallel (humanities bachelor 9, STEM bachelor 10, master 11). See DP20 for exact counts. ~90K-110K total across all lanes — higher than C4's ~60K due to additional lenses (theory_depth, methodology) and reference_quality for STEM. |
| T7 defense prep agent | ~8K (PPT) / ~5K (script) / ~6K (Q&A) | Parallel OK for 3 agents (independent artifacts). ~19K total. Cross-check runs after all complete. |

**Critical rules:**
- DP5 (5-10 paper deep-reads): Do NOT launch 10 agents simultaneously. Pipeline instead: each agent reads one paper → extracts structured summary → releases context → next agent starts. Only the merged extraction table enters the main context.
- Result merging: Never feed all raw agent outputs into one context. Each agent writes structured output → merge script extracts key findings → only the merged table/JSON enters the main context.
- Max 3 agents active at once for text-heavy parallel work (deep-read, review), EXCEPT:
  - S9 DP30 (Mode C, 8 review agents): OK to run all 8 — each pair reads manuscript independently, no inter-agent dependency
  - T5 DP20 (9-11 review agents): OK to run all — independent evaluation lenses
  Lighter tasks (citation verification, figure generation) can exceed this.
- If total estimated token budget exceeds available context (>150K tokens for all concurrent agents), serialize the heaviest agents first.

### 引用文件加载成本 (Reference File Loading Costs)

Reference loading conditions (auto-load vs on-demand, stage triggers, axis conditions) are defined authoritatively in `manifest.yaml` under `references:`. Refer to manifest.yaml for the current loading strategy for each reference file. The key costs (lines + token estimates) are summarized here:

| Reference file | Size | Loading strategy |
|---------------|------|------------------|
| quick-routing | ~22 lines / ~1.5K tokens | Always loaded (in `always_load` list) |
| english-de-ai-quick-ref | ~135 lines / ~9K tokens | Auto-loaded at S7 when language=en |
| english-de-ai-guide | ~1090 lines / ~72K tokens | On-demand only — user requests deep De-AI scan |
| chinese-de-ai-quick-ref | ~152 lines / ~10K tokens | Auto-loaded at S7, C4, or T5 when language=zh |
| chinese-de-ai-guide | ~662 lines / ~44K tokens | On-demand only (S7/T5/S8.6) — user requests deep De-AI scan |
| chinese-journal-adapter | ~572 lines / ~38K tokens | Auto-loaded when venue=chinese-domestic |
| chart-type-selection | ~121 lines / ~8K tokens | Auto-loaded at S5 — 19 chart types taxonomy |
| journal-style-adapter | ~96 lines / ~6.5K tokens | Auto-loaded at S8.5 for international venues (Route A/B) |
| discipline-writing-patterns | ~34 lines / ~2K tokens | Auto-loaded at S4 and S7 |
| feasibility-check | ~98 lines / ~6.5K tokens | Auto-loaded at S0.5, S2, S8.5 |
| emergency-path | ~147 lines / ~10K tokens | Auto-loaded when urgency=emergency |
| english-academic-writing-guide | ~130 lines / ~9K tokens | Auto-loaded at S4 and S7 when language=en |
| english-paper-template | ~110 lines / ~7K tokens | Auto-loaded at S4 when language=en |
| nnes-chinese-english-writing | ~170 lines / ~11K tokens | Auto-loaded at S4 and S7 when language=en |
| english-academic-lexicon | ~137 lines / ~9K tokens | Auto-loaded at S4 and S7 when language=en |
| ai-declaration-templates | ~80 lines / ~5K tokens | Auto-loaded at S4, T4, C3, S10, S6.5 |
| literature-verify | ~90 lines / ~6K tokens | Auto-loaded at S2, S6, S7, T5, T6 |
| evidence-grade | ~70 lines / ~5K tokens | Auto-loaded at S2-LR |
| common-mistakes | ~60 lines / ~4K tokens | On-demand only — anti-patterns reference |
| dependency-matrix | ~70 lines / ~5K tokens | On-demand only — maintenance aid |
| discipline-stem | ~216 lines / ~14K tokens | Auto-loaded at S3/S4/S5/S8/S8.5 when discipline=stem |
| chinese-conference-adapter | ~76 lines / ~5K tokens | Auto-loaded when venue=chinese-conference |
| tavily-search | ~40 lines / ~3K tokens | On-demand only — Tavily API parameter reference |
| T6-plagiarism-check | ~188 lines / ~12K tokens | On-demand at T6 when user provides 查重报告 |
| paraphrasing-patterns | ~177 lines / ~12K tokens | On-demand at C5.5, T6.7 — 807 training pairs for padding layer |
| predatory-journal-check | ~60 lines / ~4K tokens | On-demand at S8.5 — Beall's List + Think.Check.Submit. |
| playwright-browser-automation | ~80 lines / ~5K tokens | On-demand at C2, T2, S2-LR, S6 when using CNKI/browser workflows. Referenced inline from stage files; only load the relevant section (§1-4) not the entire file |

### Per-Stage Token Budget Warning

At the start of each stage, estimate the stage's token consumption and compare against remaining context capacity:

**Estimation formula:**
```
stage_cost = stage_file_lines × 0.06K     # stage instructions (~60 tokens per line avg)
           + sum(reference_files)           # any auto-loaded references for this stage
           + expected_agent_calls × 10K     # average agent output per call
           + overhead_buffer 5K             # gate evaluation + routing logic
```

**Redundancy cost adjustment:**
When using Mode B or Mode C (see `multi-agent-patterns.md`), apply the redundancy multiplier:

| Redundancy Pattern | Total Agent Calls | Cost vs Mode A |
|--------------------|------------------|----------------|
| Mode A (divide) | N | 1.0× baseline |
| Mode B ×2 | 2 | 2.0× same task |
| Mode B ×3 | 3 | 3.0× same task |
| Mode C (4 personas × 2) | 8 | 2.0× baseline (DP30) |

Include this in the stage_cost estimate when the stage references a redundancy DP.

**Warning thresholds:**

| Remaining Capacity | Action |
|-------------------|--------|
| stage_cost < 40% of remaining | Normal — proceed |
| stage_cost 40-60% of remaining | Warn: "This stage may consume ~{stage_cost}K tokens. Consider compressing past stage outputs or being concise in agent prompts." |
| stage_cost > 60% of remaining | Strongly warn: "This stage is estimated to consume ~{stage_cost}K out of ~{remaining}K remaining tokens. Strongly recommend: (1) compress/summarize previous stage outputs, (2) use new session with session persistence to continue, or (3) run this stage's agents with minimal-context prompts." |

**When to trigger:** Before loading the stage file (Step 3/4 boundary). If the warning fires, present options before loading the stage — don't load it and then warn, as loading itself consumes context.

**New session strategy:** If the user chooses to continue in a new session, the session persistence state file already contains all axes and completed stages. The new session resumes at the current stage with full context budget restored.
