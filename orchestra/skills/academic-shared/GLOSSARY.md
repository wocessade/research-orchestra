# Academic Writing Pipeline — Shared Glossary

Core concepts used across all pipeline modules (journal, thesis, coursework). Module-specific terms are defined in their respective GLOSSARY.md files.

## Entry Point
The pipeline has configurable entry points depending on how work starts: **idea-first/data-first/existing-manuscript** (journal), **thesis/existing-manuscript** (thesis), **course-assignment/existing-manuscript** (coursework). Each enters at a different stage and follows a different gate chain.

## Axis (axes)
Session-level variables detected at pipeline start that control routing and behavior. Common examples: `entry_point`, `language`, `discipline`, `urgency`, `writingFormat`. Axes are snapshot to `.pipeline_state.json` for session persistence.

## Stage
A unit of work in the pipeline. Each stage has: a file in `strategists/`, a gate, a `next` or `route` field in manifest.yaml, and defined inputs/outputs. Stages are loaded one at a time — never pre-load future stages.

## Gate
A quality checkpoint at the end of each stage. Four types: **BLOCK** (must pass), **SOFT BLOCK** (override with reason), **COND. BLOCK** (conditional on axis), **ADVISORY** (awareness only).

## Gate Chain
The ordered sequence of gates for a given entry point. Each module defines its own chain (e.g., journal: Q1→Q1.5→Q2→...→Q12).

## Dispatch Point (DP)
A numbered point in the pipeline where parallel agents are launched. Defined in `dispatch-points.md`. Each DP specifies which agents run, what they share, and how results merge.

## Parallel Group
A set of stages with no mutual dependencies that execute simultaneously. After all group members complete, evaluate all gates before proceeding to `parallel_group_next`.

## Convergence Loop
A fix→re-review→dedup→converge cycle. Iterate until: no new Critical items, ≤2 new Major items, and no degeneration (previously-fixed issues don't reappear). Hard cap of 3 rounds.

## STOP-AND-ASK
A mandatory pause point where the pipeline must get user confirmation before proceeding. Used at: major decisions, uncertainty, and degradation thresholds.

## Manifest (manifest.yaml)
The declarative loading configuration. Defines all axes, stages, references, dependency graphs, skill criticality, and session variables.

## Dependency Graph (DAG)
A directed acyclic graph of stage dependencies. Defined in both `manifest.yaml` (dependency_graph section) and `incremental-update.md` (visual DAG + rerun protocol).

## Incremental Update
When a gate failure requires backtracking to an earlier stage, the protocol in `incremental-update.md` governs which outputs are reusable and which must be regenerated.

## Session Persistence
A `.pipeline_state.json` file in `output_dir` that snapshots all axes, completed stages, stage outputs, and unresolved items after each gate pass. Enables resuming across conversation sessions.

## Material Passport
A structured document carried through the pipeline that records all key decisions, evidence, and artifacts produced at each stage. Defined in `material-passport.md`.
