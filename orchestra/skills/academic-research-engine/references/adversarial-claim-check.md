# Adversarial Claim Check (reference)

Optional pass **after** Deep Read Bridge / before promoting a claim into RQ or citation bank.

## Pattern (Scout → Specialist → Adversary → Synthesize)

1. **Scout** — list candidate claims with locators (`S/C/F/T` or DOI+paragraph).
2. **Specialist** — steelman the claim in domain terms.
3. **Adversary** — attack: wrong population, confounded metric, overclaim vs figure, citation drift.
4. **Synthesize** — keep / hedge / drop; write outcome into `.research/reads/{slug}.md`.

## Output shape

```yaml
claim: "..."
locator: "F2 / §4.1"
verdict: keep | hedge | drop | abstain
adversary_notes: "..."
rq_implication: supports | threatens | orthogonal
```

## Rules

- May be a subagent; must not invent quotes without locator.
- `abstain` if evidence insufficient — do not force a RQ edit.
- Does **not** write `metrics.json` or mark issues `verified`.
