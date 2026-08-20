# CS Conference Path (研0 default)

For `discipline=stem` and English/Chinese CS conferences (CCF / NeurIPS / ACL / CVPR-style).
Complements `academic-journal/references/discipline-stem.md` and `academic-latex`.

## Defaults

| Item | Default |
|------|---------|
| writingFormat | `latex` preferred |
| Page budget | Record in `confirmed_contribution.md` (ask user if unknown) |
| Claim style | **Claim-first** — lead with contribution, not textbook background |
| Intro timing | **Draft0 at S3** → write Methods/Eval → **Final Intro last** → Abstract |

## S3 — Mini Draft0

Write `.paper/draft0_intro.md` (not the final Intro):

1. One identity sentence
2. Gap bullets (3–5)
3. Contributions C1–C3 (must match confirmed_contribution after user OK)
4. Eval plan sketch (datasets, baselines, metrics)
5. Page budget note

Do **not** polish Draft0 into camera-ready Intro yet.

## S4 — Core-First + Final Intro

Order for CS conference (override IMRAD names as needed):

1. Method / System / Approach
2. Experiments / Results (**each subsection ends with Takeaway**)
3. Update `contribution_experiment_map.md` (`verified` where possible)
4. Related Work (often after technical core)
5. **Final Introduction** (rewrite from Draft0 using real results — no invented numbers)
6. Abstract → Title

Forbidden: strong claims for `planned`/`placeholder` evidence rows.

## Compression (page crisis)

When over page limit:

1. Cut textbook background
2. Claim-first paragraph openers
3. Move numbers into tables/figures
4. Replace result laundry-lists with Takeaway sentences
5. Shorten Related Work to contrastive paragraphs
6. Drop redundant ablations (keep those tied to Ci)
7. Report before/after word counts to user

## Q-gates linkage

- Q3: contribution gate + Draft0 present (stem/conference)
- Q4: Final Intro after evidence sections; Results Takeaways; map file present
