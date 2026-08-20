# Shared Convergence Loop Protocol

Used by review-and-revise stages to iterate until quality stabilizes or the hard limit is reached.

## Protocol

### 3-Round Max Loop

Each round: apply Critical + Major fixes from the consolidated review, then re-run the review stage against the revised output. Maximum 3 rounds (initial review + 2 revision cycles).

### Round Procedure

1. **Apply fixes:** Fix all Critical items. Fix all Major items (document any that cannot be fixed). Minor items as time permits, can be deferred.
2. **Save previous evaluation:** Back up the current review report before re-running.
3. **Re-run review:** Execute the same review agents against the revised output.
4. **Run semantic diff:** Compare current vs. previous issue lists using `evaluate/scripts/diff_issues.py`.
5. **Evaluate convergence:** Check criteria below.

### Convergence Criteria

- **CONVERGED:** New Critical = 0 AND New Major <= 2
- **CONTINUE:** New Critical > 0 OR New Major > 2

### Degeneration Detection

Check `NOT_ADDRESSED` items from the diff against the fix log's `Original:` fields. If a previously-fixed issue reappears unchanged in the current review, **STOP** immediately. The fix approach needs re-examination -- do not continue iterating. Present the degenerated issues to the user.

### Hard Limit

Maximum 3 rounds. If not converged after 3 rounds: report remaining issues to the user, note the hard limit, and deliver with a caveat about unresolved items.

### Fix Log Requirements

Every fix log entry must include an `Original:` field with the full issue description from the consolidated review. This enables degeneration cross-referencing between rounds.

### Per-Round Outputs

- Fix log: `{output_dir}/{prefix}_fix_log_round{N}.md`
- Convergence report: `{output_dir}/{prefix}_convergence_report.md`
- Saved previous evaluation: `{output_dir}/report_previous.json`
