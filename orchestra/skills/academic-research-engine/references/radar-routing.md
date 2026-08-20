# Literature Radar — Routing (orchestrate, do not rebuild)

## Config

`.research/radar/watchlist.yaml` (from `templates/watchlist.yaml`):

- venues, authors, keywords, arXiv categories
- `deep_synthesize.enabled` (default false)
- `weekly_review_queue`

## Modes

| Mode | Backend (call-out — do not reimplement) | Output |
|------|------------------------------------------|--------|
| `ingest` | **nature-literature-pipeline** daily digest / six-dim score | inbox pointers |
| `directed_search` | **academic-shared/literature/literature_search.py** snowball | inbox + optional bib |
| `community` | **agent-reach** (code/discussions) | inbox notes |
| `weekly` | **nature-weekly-review** (human discussion; no代判) | watchlist / reads queue |
| `deep_synthesize` | external/local DR or multi-agent synthesize (**docs only**) | inbox/reads — **never** verified metrics |

## Inbox normalization

Each `radar/inbox/*.md` entry fields: `title`, `id`, `score`, `source_skill`, `vault_path`.

## Human gate

After weekly-review discussion, write "next deep-read list" back to `watchlist.weekly_review_queue` and/or create read-bridge stubs.

## Plan-before-execute

For `directed_search` and `deep_synthesize`: output a short plan → user confirms → then run. Aligns with weekly-review "禁代判".

## Nature-* call-outs

| Skill | Path | Engine responsibility |
|-------|------|------------------------|
| nature-literature-pipeline | `../nature-literature-pipeline/SKILL.md` | invoke; store pointers only |
| nature-reader | `../nature-reader/SKILL.md` | invoke; fill read-bridge implication |
| nature-weekly-review | `../nature-weekly-review/SKILL.md` | invoke; update watchlist |
| literature_search | `../academic-shared/literature/literature_search.py` | invoke; verify via existing verify_citations |

**Forbidden:** reimplement scoring email/Zotero archive, bilingual reader pipeline, or weekly critique conclusions for the user.
