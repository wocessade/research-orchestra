# Emergency Shortcut — Minimal Viable Paper

Use only when deadline is imminent. Skip polish depth but never skip verification.

## Walk-Through: Data-First (The Most Common Scenario)

```
Day 1: D0Z (data manifest — pre-fill from filenames, user confirms) → D0 (data inventory + quality assessment) → QD0 gate
Day 2: D1 (EDA: D1A descriptive + D1B pattern discovery) → QD1 gate
Day 3: D2 (D2A pattern→claim, then D2B competitive diff, then D2C select question, then D2D targeted lit check) → QD2 gate
Day 4: S0.5 (project sanity check + Q0.5 gate) → S1.5 (design type + identification strategy if causal) → Q1.5 gate
Day 5: S2A (search strategy) → S2B (deep-read top 10 in parallel, DP5) → S2C (snowball 1 round)
Day 6: S2D (gap analysis) → Q2 gate → S2.5 (novelty audit: competing papers then dimension scoring) → Q2.5 gate
       └─ S8.5 (start venue research in background — depends only on S2.5 data; runs in parallel with Days 7-9)
Day 7: S3 (claim outline: Methods→Results→Discussion→Introduction) → Q3 gate
Day 8: S4 (write Methods + Results → Discussion → Introduction → Abstract) → Q4 gate
Day 9: S5 + S6 + S6.5A/C in parallel (DP9/DP10/DP11). After S5 finishes: run S6.5B (code regen check). → Q5 + Q6 + Q6.5 gates
Day 10: S7 (polish loop: paper-audit → fix → re-polish → re-audit) → Q7 gate
Day 11: S8.5 finalized (venue selection, route decision) → Q8.5 gate → [if Chinese: S8.6-Lite (8.6A + 8.6E only, 1 session — see §S8.6-Lite)]
Day 12: S8 (format + compile with venue template) → Q8 gate → S9-Lite (fatal-only paper-audit, 1 round, no personas — see §S9-Lite) → Q9 gate
Day 13: S10 (cover letter + DAS + supplementary in parallel DP15) → Q10 gate (S9.5 skipped in emergency)
Day 14: Buffer. If everything is clean: submit.
```

**Key difference from Idea-First:** Days 1-3 replace Stage 1. You arrive at S2 with a data-driven question instead of a literature-driven one. Figures in S5 are easier because D1 already produced diagnostic versions — you're polishing, not creating from scratch. S8.5 starts on Day 6 — as soon as S2.5 completes — to save time.

## Walk-Through: Idea-First (For Comparison)

```
Day 1: S1 (brainstorm + FINER: 5 criteria in parallel DP25) → Q1 gate → S0.5 (sanity check + Q0.5 gate)
Day 2: S1.5 (research design: power analysis + validity in parallel DP4 if causal) → Q1.5 gate
Day 3: S2A (search strategy) → S2B (deep-read top 10 in parallel DP5) → S2C (snowball 1 round)
Day 4: S2D (gap analysis) → Q2 gate → S2.5 (novelty audit: competing papers then dimension scoring DP27) → Q2.5 gate
       └─ S8.5 (start venue research in background — depends only on S2.5 data; runs in parallel with Days 5-8)
Day 5: S3 (claim outline: Methods→Results→Discussion→Introduction) → Q3 gate
Day 6: S4 (write Methods + Results)
Day 7: S4 (write Discussion + Introduction + Abstract + Title) → Q4 gate
Day 8: S5 + S6 + S6.5A/C in parallel (DP9/DP10/DP11). After S5 finishes: run S6.5B (code regen check). → Q5 + Q6 + Q6.5 gates
Day 9: S7 (polish loop) → Q7 gate
Day 10: S8.5 finalized (venue selection, route decision) → Q8.5 gate → [if Chinese: S8.6-Lite (8.6A + 8.6E only, 1 session — see §S8.6-Lite)]
Day 11: S8 (format + compile) → Q8 gate → S9-Lite (fatal-only paper-audit, 1 round, no personas — see §S9-Lite) → Q9 gate
Day 12: S10 (cover letter + DAS + supp parallel DP15) → Q10 gate (S9.5 skipped in emergency)
Day 13: Buffer.
```

**Estimated time:** Data-First is faster because the data already constrains what you can claim. Idea-First requires more literature iteration because the question space is unbounded. S0.5 and S1.5 add ~half a day each at the start — but prevent weeks of wasted effort downstream. S8.5 starting early (parallel with writing stages) saves 2-4 days vs. running it sequentially after S7.

**For Chinese domestic journal targets:** In emergency mode, use S8.6-Lite (8.6A + 8.6E only, 1 session — see §S8.6-Lite) instead of the full 7-sub-stage S8.6. The full S8.6 (S8.6A-S8.6G) takes 1-2 days and is for normal-pace pipelines only.

## Minimal Viable Paper (if deadline is TOMORROW)

Emergency shortcut — skip polish depth but never skip verification.

**Data-First emergency:**
```
1. D0Z (manifest — still required: misidentified files waste more time than skipping polish) → D0 → D1 → D2 (must extract question from data)
2. S2 (quick lit search + verify key citations)
3. S2.5 (quick novelty check — at minimum, name 3 competing papers and your delta)
4. S3 → S4 (write all sections from D2 question)
5. S6 (verify every citation)
6. S7 pass 1 only (paper-audit → fix Critical/major items only → skip Pass 2)
7. S8.5 (quick venue check — pick one journal) → S8 (compile for that journal)
8. S9-Lite (fatal-only paper-audit, 1 round — see §S9-Lite)
9. S10 (bare-minimum cover letter)
```

**Idea-First emergency:**
```
1. S1 → S2 (must verify citations)
2. S2.5 (quick novelty check)
3. S3 → S4 (write all sections, minimal quality OK)
4. S6 (verify every citation)
5. S7 pass 1 only (paper-audit → fix Critical/major items only → skip Pass 2)
6. S8.5 (quick venue check) → S8 (compile)
7. S9-Lite (fatal-only paper-audit, 1 round — see §S9-Lite)
8. S10 (bare-minimum cover letter)
```

Both produce a technically correct but unpolished paper. Better than missing the deadline.

**Skipped in MVP (deadline is tomorrow):** S0.5 (sanity check — you're past this point), S1.5 (design — time pressure), S5 (figures — reuse whatever exists from earlier stages), S6.5 (reproducibility), Polish pass 2, S9.5 (reviewer attack).

**Never skipped even in MVP:** Citation verification (S6), paper-audit Critical/major item fix (S7 pass 1), S9-Lite (fatal-only audit).

### S9-Lite (Emergency Paper Audit)

Replaces full S9 when urgency=emergency.

Run `skills-embedded/paper-audit.md` with these constraints:
- Check FATAL items ONLY — skip Major, Moderate, and Minor issues
- Skip the 4 reviewer personas (no Persona A/B/C/D simulation)
- Skip convergence check (single-pass)
- If no fatal items → proceed to S10
- If fatal items found → fix them and proceed (NO re-audit)

Rationale: Full S9 with 4 personas and convergence is the pipeline's most expensive stage. Fatal-only audit catches show-stoppers without the cost.

### S8.6-Lite (Chinese Domestic Emergency)

When urgency=emergency AND venue=chinese-domestic:

Run only:
- 8.6A (Journal Qualification) — essential gate
- 8.6E (Structure Compliance Audit) — formatting blocker

Skip: 8.6B (Reverse Engineering), 8.6C (Positioning Audit), 8.6D (Innovation Packaging), 8.6F (Reviewer Perspective Check)

Time: 1 session. Output: Pass/Fail for qualification + compliance checklist.

## Emergency + Chinese-Conference (Combined Skip Lists)

When urgency=emergency AND venue=chinese-conference, both skip lists apply. The Chinese conference pipeline already skips S6.5 (reproducibility), S8.5 (venue strategy — venue is fixed), S8.6 (domestic journal layer — not applicable to conferences), and S9.5 (reviewer attack drill). Emergency mode additionally skips S0.5 (sanity check), S1.5 (research design — time pressure), S5 (figures — reuse from earlier stages), and uses S9-Lite for S9.

**Combined rule:** Apply the conference skip list as-is; it already covers most emergency skips. The only emergency-specific actions: use S9-Lite (fatal-only paper-audit, 1 round) for S9, reduce S2 reference target to 10, skip S0.5/S1.5. Conference pipeline's condensed S7 already handles polishing faster than the full pipeline.

