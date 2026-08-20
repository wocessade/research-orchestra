# Session Persistence (断点续传)

The pipeline has multiple stages and cannot realistically complete in a single conversation session. This protocol enables resumption across sessions.

## State File

After each stage completes, write `{output_dir}/.pipeline_state.json`:

```json
{
  "paper_slug": "{YYYYMMDD_HHMMSS}_{english_slug}",
  "current_stage": "{NEXT_STAGE_KEY}",
  "session_started": "{ISO_DATETIME}",
  "last_updated": "{ISO_DATETIME}",
  "axes": {
    "entry_point": "{entry_point}",
    "paperType": "{paper_type}",
    "language": "{lang}",
    "discipline": "{discipline}",
    "urgency": "{urgency}",
    "status": "{status}"
  },
  "completed_stages": [],
  "stage_outputs": {},
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
    "confidence_ledger": [],
    "stage_completion_log": []
  },
  "unresolved_items": [],
  "user_decisions": {}
}
```

### Required fields

| Field | Description |
|-------|-------------|
| `paper_slug` | Per-paper unique directory name in format `{YYYYMMDD_HHMMSS}_{english_slug}`. Used to locate the project's output directory and for resume detection. |
| `current_stage` | Stage key (e.g., "S4", "T2", "C3") — the stage that was about to start when session ended |
| `last_updated` | ISO 8601 timestamp |
| `axes` | Complete snapshot of all axis values at time of write. Must include all axes defined in manifest.yaml |
| `completed_stages` | Ordered list of stage keys that have passed their gates |
| `stage_outputs` | Map of stage key → relative path to the stage's primary output file |
| `unresolved_items` | Blocking items that need user input before proceeding (e.g., unanswered STOP-AND-ASK questions) |
| `passport.stage_completion_log` | Stage-by-stage completion records for handoff checks. Each entry: stage key, timestamp, key output summary, key decisions. Appended at each gate pass. |

### Optional fields

| Field | Description |
|-------|-------------|
| `user_decisions` | Key decisions the user made, for context in the next session |

## Write Protocol

1. **When to write:** Immediately after a gate passes (before loading the next stage).
2. **What to write:** The state as it stands after gate passage — `current_stage` should be the NEXT stage to execute.
3. **Atomic write:** Write to a temp file first, then rename — prevents corruption on interrupt.
4. **Never overwrite:** Append to the `completed_stages` and `stage_outputs` lists. Never remove entries.

## Resume Protocol

At SKILL.md Step 1 (after loading manifest + always_load):

1. Scan `{output_dir_base}/` for subdirectories matching `{YYYYMMDD_HHMMSS}_*` pattern
2. Check each for `.pipeline_state.json` — if found with matching topic or user confirms, prepare resume
3. If a matching state file exists:
   - Read `paper_slug`, `current_stage` from state
   - Compare `completed_stages` list with manifest dependency_graph to verify the state is consistent
   - Present resume prompt:
     ```
     Detected incomplete pipeline:
       Paper: {paper_slug}
       Entry point: {entry_point}
       Progress: {completed_count}/{total_stages} stages complete
       Last stage completed: {last_completed_stage}
       Next stage: {current_stage}
       Last activity: {last_updated}
     
     Continue from where we left off?
     ```
3. If user confirms:
   - Restore all `axes` values from state (they override the current session's detected values)
   - Load the `current_stage` file directly (skip all completed stages)
   - Continue pipeline execution normally
4. If user declines:
   - Rename `.pipeline_state.json` to `.pipeline_state_archived_{timestamp}.json`
   - Start fresh pipeline

## Edge Cases

| Situation | Handling |
|-----------|----------|
| State file exists but `paper_slug` is missing (legacy format) | Warn: "Detected legacy-format project (before per-paper isolation). A new timestamped directory will be created for this project. Old files remain untouched." |
| State file references stages not in current manifest | Warn: "Pipeline state was created with a different version of the pipeline. Some stages may not exist. Continue?" |
| `unresolved_items` is non-empty | Present unresolved items first: "These questions were left unanswered from the previous session. Let's resolve them before continuing." |
| A completed stage's output file is missing from disk | Warn: "Output file {path} from stage {N} is missing. That stage's work may need to be redone." Offer to roll back to that stage. |
| State file was written > 30 days ago | Warn: "Pipeline state is {N} days old. The research landscape may have changed. Consider re-running the literature review." |

## Legacy Format Detection

The old pipeline format wrote `.pipeline_state.json` directly in `{output_dir_base}/` (no per-paper subdirectory). The new format always writes inside `{output_dir_base}/{YYYYMMDD_HHMMSS}_{slug}/`.

Detection rule: if `.pipeline_state.json` exists at the TOP level of `output_dir_base` (not inside a timestamped subdirectory), treat it as legacy. Do NOT auto-migrate — warn the user and start a fresh project directory.
