# Claim-evidence protocol

Integrates with `academic-shared/evidence-ledger/ledger-protocol.md`.
Use `.paper/claim_evidence_ledger.md` and/or `evidence_ledger.jsonl`.

## Rule

No artifact -> no polished claim. Mark `[CLAIM NEEDS EVIDENCE]` or weaken the claim.

## Ledger row (markdown)

```text
claim -> evidence source -> allowed certainty -> boundary -> status
```

| status | Meaning |
|--------|---------|
| planned | Need this evidence; not yet collected |
| placeholder | Prose uses TODO/placeholder metrics |
| verified | Number/statement matches artifact |
| blocked | Cannot verify; user decision required |

## Certainty language

| Evidence | Allowed wording |
|----------|-----------------|
| Single seed / single run | "In this run..."; avoid unsupported "significantly" |
| Multi-seed with CI | Report mean+/-CI; significance only if tested |
| Qualitative example | "Illustrative"; not a population claim |
| Literature (verified) | Cite + claim must appear in source |

## Negative / mixed results

Report honestly. Incomplete seeds, missing ablations, and compute limits are scope boundaries — not content to erase.

## Numeric audit (Results)

For every quantitative sentence:

1. Grep the number in CSV / generated table / log.
2. If derived (delta, ratio), add `% derived: ...` near the TeX.
3. Never use a number remembered only from conversation.

## Contribution boundaries

In `.paper/context.md` list main claims, secondary claims, explicit non-claims, and likely reviewer attacks.

## Caption alignment

Each figure/table appears in the ledger with a `message` matching the caption takeaway (see academic-plotting).
