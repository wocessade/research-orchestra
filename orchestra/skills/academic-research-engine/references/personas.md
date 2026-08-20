# Personas / program axis

One skill; depth selected by `.research/program.yaml` `persona`:

| Persona | Focus |
|---------|--------|
| `explorer` | RQ clarity, small EXP cards, forced NEG honesty, first meeting memo |
| `focused_paper` | Single paper track; tight radar + handoff to one `.paper/` |
| `multi_project` | Shared `.research/`; multiple `writing.paper_dirs` |
| `lab_lead` | Portfolio, student task cards, weekly → group-meeting pack |

## Lab lead extras

- Per-student EXP cards under experiments/ with owner note in card body
- Weekly-review output → group meeting agenda (pointers, not ghostwritten critique)
- Tournament budget optional for multi-H students

## Multi-project

- One `.research/` at lab/repo root
- Each manuscript keeps its own `{paper_dir}/.paper/`
- Handoff_sync per paper_dir

## Compute modes

| mode | Meaning |
|------|---------|
| `human_in_loop` | **default** — scripts generate cards/metrics slots; humans/CI run jobs |
| `ci_cpu` | optional documented CPU job for CI |
| `optional_gpu` | user-owned; engine never auto-launches GPU |
