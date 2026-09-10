# Shared Convergence Loop Protocol

Each review/revision cycle uses the current manuscript and a cumulative issue register. Maximum three review rounds; reaching the cap stops automatic iteration, not evidence checks.

## Issue Register and Closure

Keep stable issue IDs, severity, affected claim/section, status (open / resolved / accepted), and closure evidence in the review report. This review register is separate from the experiment backfill issues.csv contract.
An issue is resolved only after its fix is checked in the current manuscript. A user may explicitly accept a non-critical scope limitation with rationale; this does not turn missing evidence into verified evidence. Critical validity/evidence defects remain open until fixed or the affected claim is removed/narrowed and reviewed.
An item disappearing from a later review is a closure candidate, not proof of resolution. `diff_issues.py` FULLY_ADDRESSED means no match in that review; inspect the original issue and fix evidence before closing it. Keep unmatched unresolved issues in the cumulative register.

## Two Separate Decisions

- **REVIEW_STABLE:** no new Critical and at most two new Major items. This measures review stability only.
- **READY:** zero open Critical and zero open Major across the cumulative register, no regression, and applicable stage checks completed on the current manuscript. Accepted non-critical limitations must have explicit user rationale; review scores cannot waive evidence defects.
- **CONVERGED:** REVIEW_STABLE and READY. Otherwise continue targeted repairs within the round limit.

## Round Procedure

1. Fix open Critical/Major findings and record original issue, affected version/location and fix evidence.
2. Preserve the previous report; re-review the revised manuscript and update the cumulative register.
3. Use semantic diff as matching assistance, not as the gate decision. Check old unresolved items even when no new problems are reported.
4. Reappearing resolved issues reopen; inspect the cause and repair the affected scope before claiming READY.
5. Record both REVIEW_STABLE and READY, counts of all open Critical/Major, accepted limitations and remaining actions in `{output_dir}/{prefix}_convergence_report.md`.

## Hard Limit and Delivery

At round three, stop automatic review loops. If not READY, deliver the current draft and concrete open issues as unfinished work; do not mark the gate passed or advance automatically to submission, blind-review finalization or defense. Continue affected fixes when authorized. Do not pad the manuscript with generic disclaimers to hide unresolved defects.

## Outputs

- `{output_dir}/{prefix}_fix_log_round{N}.md`: Original issue, stable ID, fix and verification.
- `{output_dir}/{prefix}_convergence_report.md`: cumulative register, stability and readiness.
- `{output_dir}/report_previous.json`: previous evaluation.
