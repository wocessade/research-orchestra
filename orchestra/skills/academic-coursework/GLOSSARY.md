# Academic Paper Pipeline — Glossary (Coursework Edition)

> **共享基础：** 通用 pipeline 概念见 `../academic-shared/GLOSSARY.md`。本文档仅保留 coursework 专属术语。

Core concepts used throughout the pipeline. Stage-specific terms are defined in their respective stage files.

## Core Concepts

### Entry Point
The pipeline has three entry points for course assignments: **course-assignment** (课程大作业, full pipeline C1→C5), **existing-manuscript** (已有稿件的课程论文, enters at QC4), and **data-first-coursework** (有数据的课程作业, enters at C1 with data-informed topic). Each enters at a different stage and follows a different gate chain.

### Axis (axes)
Session-level variables detected at pipeline start that control routing and behavior. Examples: `entry_point`, `paperType`, `language`, `discipline`, `urgency`, `writingFormat`. Axes are snapshot to `.pipeline_state.json` for session persistence.

#### Discipline values
| Value | Meaning | Effect |
|-------|---------|--------|
| `general` (default) | 文科/人文社科等 | Uses default AI-tone curve inflection points |
| `stem` | 理工科 (CS/工程等) | Raises inflection for "进行" (15→25/万) and "该X" (12→18/万) |

### Stage
A unit of work in the pipeline. Each stage has: a file in `strategists/`, a gate, a `next` or `route` field in manifest.yaml, and defined inputs/outputs. Stages are loaded one at a time — never pre-load future stages.

### Gate
A quality checkpoint at the end of each stage. Four types:

| Type | Behavior |
|------|----------|
| **BLOCK** | Must pass. Failure → return to relevant stage and fix. Cannot proceed past a failed BLOCK. |
| **SOFT BLOCK** | Strongly recommended. Can override with documented reason. |
| **COND. BLOCK** | Conditional — only blocks if the condition applies. N/A → bypassed. |
| **ADVISORY** | Never blocks. Flags risks for awareness only. |

### Gate Chain
The ordered sequence of gates for a given entry point. Course-assignment: QC1→QC2→QC3→QC4→QC5. Existing-manuscript: QC4→QC5. Conditional QC5.5 (padding/de-AI/plagiarism-check) is triggered by keyword after C5 convergence.

### Dispatch Point (DP)
A numbered point in the pipeline where parallel agents are launched. Defined in `dispatch-points.md`. Each DP specifies which agents run, what they share, and how results merge.

### Parallel Group
A set of stages with no mutual dependencies that execute simultaneously. Defined in `parallel-groups.md`. After all group members complete, evaluate all gates before proceeding to `parallel_group_next`.

### Convergence Loop
A fix→re-review→dedup→converge cycle used in C5. Iterate until: no new Critical items, ≤2 new Major items, and no degeneration (previously-fixed issues don't reappear). Hard cap of 3 rounds.

### STOP-AND-ASK
A mandatory pause point where the pipeline must get user confirmation before proceeding. Used at: major decisions (topic selection, structure), uncertainty, advisor review handoffs, and degradation thresholds. Defined in `stop-and-ask.md`.

### Manifest (manifest.yaml)
The declarative loading configuration. Defines all axes, stages, references, dependency graphs, skill criticality, and session variables. The router reads this to know what to load and when.

### Dependency Graph (DAG)
A directed acyclic graph of stage dependencies. Defined in both `manifest.yaml` (dependency_graph section) and `incremental-update.md` (visual DAG + rerun protocol). Used for incremental updates — when backtracking, downstream stages are marked [STALE].

### Incremental Update
When a gate failure requires backtracking to an earlier stage, the protocol in `incremental-update.md` governs: which outputs are reusable, which must be regenerated, and which downstream stages are stale. Prevents unnecessary rework.

### Session Persistence
A `.pipeline_state.json` file in `output_dir` that snapshots all axes, completed stages, stage outputs, and unresolved items after each gate pass. Enables resuming across conversation sessions. Defined in `session-persistence.md`.

### Unresolved Items
Issues recorded in session state that were not fully resolved — e.g., parallel agent failures degraded to manual checks. Persist across sessions and must be acknowledged before the final gate.

## Pipeline Tags

### [STALE]
Marks downstream stage outputs as potentially invalid after backtracking to an earlier stage. Format: `[STALE: {trigger_stage} → {affected_stage}]`. Placed at the top of affected output files. Gate evaluation must account for STALE outputs — re-run the stage before moving forward. Lifecycle: created on backtrack → cleared on stage re-execution.

### [OUTDATED]
Marks web sources or literature entries whose content is older than the field's timeliness threshold (typically >2 years for fast-moving fields). Used in timeliness scoring tables only (tavily-search.md, C2.md). Distinguished from [STALE] (which is pipeline-internal) — [OUTDATED] is a data quality tag for search results.

### [AGENT-UNILATERAL]
Marks findings flagged by only 1 of N redundant agents in a Mode B/C dispatch. When 2 independent agents cover the same persona, a finding reported by only 1 agent is tagged `[AGENT-UNILATERAL]` and requires orchestrator judgment before inclusion. See `static/core/result-collection.md` §Redundancy Integration for handling protocol.

### [SCORE-MAPPED: X.X]
Marks Chinese-paper quality tier mapped to a numeric score. X.X is a placeholder for the actual value (A=8.5, B=6.0, C=3.5). Used in C2 credibility tables.

### Composite Score (disambiguation)
The term "composite score" is used with different formulas in different contexts. Always qualify with a prefix:
- **Literature quality composite score**: 3D formula `0.4×authority + 0.25×timeliness + 0.35×relevance` (range 0-10). Used in C2 for paper quality filtering.
- **Web source composite score**: 2D formula `0.55×authority + 0.45×depth` (range 0-10). Used in tavily-search.md, C2F.2 for web result scoring.
- **De-AI composite score**: Multi-dimensional AI-detection score from De-AI guides (20 dimensions Chinese, range 0-5 with section risk weights). Used in C4, C5.5.

### GAP Matrix
Gap Analysis Profile matrix — a structured mapping of methodological approaches against research questions to identify density gaps in the literature. Produced during literature review (C2) and used in feasibility assessment. Concept used in dispatch-points.md DP17.

### Padding / 注水
A conditional sub-pipeline after C5 convergence (triggered by keywords "padding", "de-AI", or "plagiarism-check"). Uses `C5.5.md` to expand the paper's word count via controlled paraphrasing and structural expansion, followed by a full C4 re-review to ensure quality is maintained.
