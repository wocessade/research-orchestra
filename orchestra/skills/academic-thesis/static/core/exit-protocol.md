# Structured Exit Protocol

If the project hits repeated failures, don't spin. Trigger exit evaluation when:

### Intra-Stage Loop Detection

Same operation repeated ≥3 times within the same stage with no new information → automatic exit evaluation:

- **Same operation** = same tool call pattern + same input + no substantive output change
- Example: review cycle where the model modifies the same paragraph 3 times without re-running the evaluate module to check if the fix resolved the issue
- Example: repeatedly loading the same reference file and producing the same analysis without applying the findings

**Before triggering exit:** warn the user once ("I notice I'm repeating the same operation without progress. Let me step back and re-evaluate.") If the loop continues after the warning, trigger exit evaluation. This complements the existing cross-stage 3-failure rule — intra-stage loops waste context faster than cross-stage repeats.

- Same gate fails 2+ times with no new information gained
- **Parallel agent failure:** Any parallel dispatch triggers exit evaluation when per-agent recovery is exhausted. Per-agent recovery protocol: review agents follow `fallback.md` section on reviewer degradation strategy; literature search agents follow `parallel-groups.md` partial-failure handling. 2+ agents fail simultaneously in the same dispatch → immediate trigger.

**Exit evaluation output (auto-generated):**

1. **What went wrong:** which gate(s) failed, why, and what was attempted
2. **What data/IP you still have:** salvageable content (lit review, figures, partial analysis, data inventory)
3. **Three alternative paths ranked by feasibility:**
   a. **Scope down:** full output → shorter version / reduced scope
   b. **Simplify:** reduce requirements (citation count, argument depth)
   c. **Format down:** full paper → technical report / preprint only
4. **If all three are non-viable:** honest recommendation to shelve, with explicit reasoning

This section is advisory. The user makes the final decision. Exit evaluation output is preserved in the project record for possible future resurrection.

### Mandatory Stop Rule

If the same gate fails 3 times with no new information added between attempts, trigger a mandatory stop. Generate an exit evaluation in the output. The user may override, but must explicitly confirm they have read the exit evaluation.

This is a hard rule, not advisory. Repeatedly re-attempting the same gate with the same inputs wastes context and indicates a structural problem the pipeline cannot solve.
