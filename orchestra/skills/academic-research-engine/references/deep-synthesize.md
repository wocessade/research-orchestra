# deep_synthesize — Radar mode (documentation only)

## What it is

Optional radar mode that calls an external/local Deep Research stack or a multi-agent
adversarial review to produce a **structured synthesis** for human reading.

## What it is not

- Not a verified metrics source
- Not Results prose
- Not a replacement for EXP ingest
- Not a default always-on path (`watchlist.deep_synthesize.enabled: false`)

## Protocol

1. Draft a **plan** (questions, corpora, stop conditions) → user approves.
2. Run DR / multi-agent synthesize asynchronously if needed; persist state under `.research/radar/`.
3. Write outputs **only** to `radar/inbox/` and/or `reads/` with provenance envelope (tool, time, sources).
4. Every factual bullet needs a locator or URL; otherwise mark `abstain`.
5. Promote into RQ/H only after deep-read bridge + optional adversarial claim check.

## Provenance envelope (minimum)

```yaml
source_skill: deep_synthesize
backend: "user-specified DR | local multi-agent"
plan_approved_by_user: true
outputs: [inbox/..., reads/...]
writes_verified_metrics: false
```
