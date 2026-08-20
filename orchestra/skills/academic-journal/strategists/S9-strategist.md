# Stage S9: Paper Audit 2 [Strategist]

**Gate:** Q9 (BLOCK) — paper-audit returns PASS, all Critical items fixed, response matrix filled.

**Goal:** Find problems before reviewers do.

**Needs Composers:** paper-audit-orchestration

## Decisions

### Redundancy Strategy (DP30, lines 8-10)
4 personas x 2 redundancy = 8 agents total (Mode C mixed mode).

- Each persona receives same description + paper, writes independent review.
- Orchestrator merges intra-pair: take union. Items found by only 1/2 flagged as `[AGENT-UNILATERAL]`.

### Two-Tier Review (9A, lines 13-25)

```
paper-audit (GATE) -> peer-review (DETAIL) -> fix HIGH -> fix MEDIUM -> re-audit
```

| Tier | Purpose |
|------|---------|
| Gate | Pass/fail on structure, completeness, citation validity |
| Detail | Methodology depth, statistical validity, reporting standards |
| Evidence | Claim-by-claim evidence quality assessment |

- Run paper-audit gate first. IF FAIL → go back to relevant stage. Do NOT proceed to detail tier.
- Only run peer-review detail AFTER paper-audit returns PASS.

### Null-Result Awareness (9C, lines 39-44) — Conditional
- IF `passport.negative_results_pathway == "null_result_aware"` → all reviewer personas must: (1) NOT treat non-significant effects as flaws, (2) check for equivalence/non-inferiority tests, (3) check effect sizes reported (not just p-values), (4) check Discussion avoids "proves no difference" misinterpretation.

### Preregistration Deviation Check (9C.5, lines 54-66) — Conditional
- ONLY execute IF `passport.preregistration` exists (`.pipeline_state.json`).
- For each preregistered hypothesis: compare direction, outcome measure, confirmatory vs exploratory classification.
- Classify: CONFIRMED / DEVIATED (unlabeled exploratory) / EXPLORATORY (correctly labeled).
- Severity: MINOR (name differences), MODERATE (secondary hypothesis changed), MAJOR (primary hypothesis changed / selective reporting).
- MAJOR deviation -> Critical item: manuscript must explain deviation or mark as exploratory.

### Self-Challenge Rebuttal (9C.6, lines 68-103)
After all personas produce findings (through DP30), before response matrix:
1. Collect all Critical findings from each persona.
2. Re-present: show paper draft + persona's OWN Critical findings.
3. Self-challenge: each persona re-examines own Critical items. Verdict:
   - UPHELD → remains in final report.
   - DOWNGRADED to Major → demoted, flagged `[SELF-CHALLENGE-DOWNGRADED]`.
   - RETRACTED → removed, flagged `[SELF-CHALLENGE-RETRACTED]`.
4. At least 20% of Critical findings must be challenged (UPHELD is not default — each item must earn its place).
5. Orchestrator can override suspicious retractions back to UPHELD.

### Convergence Check (9F, lines 129-163)
After each review round, compare against previous rounds' merged set (semantic deduplication):

```
├── No new Critical items AND <= 2 new Major items
│   -> CONVERGED. Stop reviewing. Proceed to Q9 gate.
├── New Critical items found
│   -> Fix Critical items. Run ONE more round to verify. Then stop regardless.
├── > 2 new Major items
│   -> Fix items. Re-run review. Max 3 rounds total.
└── Same issues reappearing (classified but not fixed)
    -> DEGENERATE. Stop. Fix before re-reviewing. Don't spin.
```

**Hard cap: 3 rounds.** After round 3, stop. Remaining issues -> acknowledge in Limitations or prepare as pre-emptive defenses. If still not converged, problems are structural -> go back to S3 (or re-examine claim-level structure for existing-manuscript entry).

### Composer Sequence
1. composer: paper-audit-orchestration {8-agent Mode C, 4 personas x 2 redundancy}
   - IF `passport.negative_results_pathway == "null_result_aware"` → set flag: null-result aware mode
   - IF `passport.preregistration` exists → include deviation check
   - Self-challenge round built in
   - Convergence check after each round
   - Max 3 rounds

## Gate

### Q9 Gate Checklist
- [ ] paper-audit gate returns PASS
- [ ] All Critical severity items fixed
- [ ] All Major severity items fixed or explicitly acknowledged as limitations
- [ ] peer-review completed from at least 2 personas
- [ ] Self-challenge rebuttal completed — all Critical findings re-examined
- [ ] No inflated Critical items — self-challenge verified all surviving UPHELD items are genuine
- [ ] Preregistration deviation check complete (if applicable) — MAJOR deviations disclosed in manuscript
- [ ] Response matrix filled for all review comments
- [ ] At least one person who is NOT an author has read the paper

### Gate Failure Route
Q9 is BLOCK.

1. Inspect specific failed items:
   - Critical issues -> route to 9D (revision tracking), fix, re-verify.
   - paper-audit fails -> return to S7 (polish loop), fix, re-submit.
2. After 2 fix attempts still fail -> STOP-AND-ASK: downgrade to S9-Lite (fatal-only, skip 4 persona review) or accept risk and submit as-is.
