# Research Engine — Workflow (state machine)

## Role

**Research engine = state machine + orchestrator.** It registers verified evidence
for writing skills to consume. It does **not** replace novelty judgment or advisor
decisions. It does **not** reimplement `nature-reader`, `nature-literature-pipeline`,
or `nature-weekly-review`.

## High-level loop

```text
radar → deep read bridge → RQ/H store → EXP registry → (NEG) → handoff → academic-journal/thesis
```

## Stages vs writing

| Research phase | Engine | Writing |
|----------------|--------|---------|
| Explore | radar + read + RQ | no body prose |
| Converge | EXP designed; Ci candidates | S3/T1 contribution draft OK |
| Results land | ingest → verified | S4/T4 strong claims allowed |
| Fail | NEG + failure loops | revise Ci / limitations; no number fakery |
| Manuscript | handoff | journal/thesis/latex P0/P1 |
| Multi-project | shared `.research/`, per-paper `.paper/` | |

## Human-in-the-loop gates

1. Activate RQ (`program.yaml` `active_rq` + user OK) before EXP.
2. Freeze success/failure criteria before run.
3. Confirm handoff before seeding `user_confirmed` contribution for writing.

## ID spine

See `../academic-shared/research/schemas.md`:

`RQ → H → EXP/NEG → Ci → ISS → CLM` (+ nature-reader `S/C/F/T` locators).

## Intent routing (natural language)

| User says | Load | Action |
|-----------|------|--------|
| 雷达 / radar / 本周日推 | `radar-routing.md` | route to nature-* / literature_search |
| 开 RQ / 假设 | `rq-hypothesis.md` | scaffold from templates |
| 设计实验 / EXP | `experiment-card.md` | write card; `validate_experiment_card.py` |
| 摄入 / ingest run | scripts | `ingest_run.py` |
| 负结果 / NEG | `negative-results.md` | ledger entry |
| handoff / 准备写稿 | `handoff-to-writing.md` | `handoff_sync.py` |
| 组会 / weekly | call nature-weekly-review | write back watchlist |
| deep synthesize | `deep-synthesize.md` | **docs mode only** → inbox/reads |
| 对抗核验 claim | `adversarial-claim-check.md` | after deep read |

## Hard rules

- No fabricated metrics. Numbers only from ingested artifacts.
- Default **no GPU auto-runner**. Optional CI/CPU only (see personas / program.yaml).
- Abstain when evidence insufficient — never pad handoff with planned strong numbers.
