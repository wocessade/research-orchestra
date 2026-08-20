# Core Pipeline Rules

**Parallel Scheduling Rule:** When multiple independent tasks are ready, launch them in parallel. Each agent does one thing. Merge results, then proceed.

Never run a parallel agent for a task that depends on another agent's output. Check the Dependency Chain before dispatching.

**One stage at a time:** Do not pre-load future stages. The router loads only the current stage file. After the gate passes, load the next stage.

**Append-only:** Never overwrite user-written content. Add, suggest, flag — don't delete.

**Minimal scope:** Don't add features, refactor, or introduce abstractions beyond what the current stage requires.

**Hard stops:** If a BLOCK gate fails, stop and fix. Don't proceed past a failed BLOCK gate.

**Incremental update:** When backtracking to an earlier stage, use the protocol in `static/core/incremental-update.md`. It provides the stage dependency graph, partial reusability rules, and rerun protocol. Never re-run downstream stages without first marking affected outputs as [STALE].

**Session persistence:** After each gate passes, write `{output_dir}/.pipeline_state.json` per `static/core/session-persistence.md`. This enables resuming across conversation sessions — the pipeline cannot realistically complete in one session.

**Clean Context Gate:** When manifest.yaml `stages` entry has `clean_context: true`, the orchestrator must:
1. After the current stage completes, record its primary output path in `.pipeline_state.json` → `stage_outputs`
2. When loading the next stage, only load:
   - The next stage's file
   - The previous stage's output file (compiled manuscript)
   - `.pipeline_state.json` Passport data
   - `static/core/` core rules (this file, gate-chain, stop-and-ask, fallback)
3. Do NOT load any prior stage content or agent prompts
4. Inject into the next stage's system prompt: "Your review context was reset after the compilation stage. You can only see the final manuscript. You have no information about how the manuscript was written. Base your review on the manuscript text itself, not on any prior knowledge about AI writing patterns."

**Progress indicator:** After each gate passes, output a structured status block:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 Stage: {stage} ({description})
✅ Completed ({count}/{total}): {list of completed stages}
➡️  Next: {next_stage} (after Q{N} passes)
🔀 Branch: {active route description}
⚠️  Pending: {gate type} — {blocking items or "none"}
📋 Axes: paperType={val} | lang={val} | venue={val} | discipline={val} | urgency={val}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Pre-flight estimate:** At Step 1 end, output: `预计流水线: {entry_point} ({total} stages) | 关键决策点: {N} | 人机交互: {M}-{K} 轮 | 预计模型调用: {J}-{L}`

**Gate types:**
- **BLOCK:** Must pass before proceeding to the next stage. If it fails, return to the relevant stage and fix the issue. Do NOT continue past a failed BLOCK gate.
- **SOFT BLOCK:** Strongly recommended to pass. Can proceed with documented override and explicit warning, but the override reason must be recorded.
- **COND. BLOCK:** Conditional — only blocks if the condition applies (e.g., causal papers must document identification strategy). If the condition does not apply (N/A), the gate is bypassed.
- **ADVISORY:** Recommended but never blocks. Can override without justification. Exists to flag risks the user should be aware of.
