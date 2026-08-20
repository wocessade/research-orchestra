# Nature-Style Polishing (Embedded)

**Source:** `nature-polishing` v6.0.0 | **Snapshot:** 2026-06-06
**Pipeline usage:** S7 — manuscript polish before paper-audit

## Core Process
1. **Paper-type playbook** — architecture, writing order
2. **Section-specific job & failure modes** — abstract, intro, results, discussion, conclusion
3. **Journal-specific framing & constraints** — Nature, Nat Comms, generic
4. **Language-specific rules** — en: concision, hedging, signposting; zh-to-en: translation pitfalls
5. **Core stance & ethics** — claim-evidence boundary, no fabricated content

## Failure Modes to Fix
- **Intro too narrow:** Jumps to detail without motivating the problem
- **Results without claims:** Data dump without interpretation
- **Discussion repeats results:** Must interpret, not restate
- **Overclaiming:** "Proves" instead of "suggests," "demonstrates"
- **Hedging mismatch:** Too cautious for strong evidence, too confident for weak

## Polish Priority
1. Argument logic (claim → evidence → boundary)
2. Paragraph structure (topic sentence → support → transition)
3. Sentence-level clarity (subject-verb proximity, nominalizations, passive voice)
4. Terminology consistency
5. AI-tone reduction (see de-ai quick-ref files)

## Key Rule
If a structural problem cannot be fixed without inventing content, flag it instead of papering over it.

## Examples

### Sentence-Level Polish: Hedge Stacking

**Before (hedge-stacked):**
> "These results may potentially suggest that the intervention might possibly have a somewhat beneficial effect on certain outcomes under specific conditions."

→ Five hedges in one sentence. The reader trusts nothing.

**After (one calibrated hedge):**
> "These results suggest the intervention improved the primary outcome (23% increase, p = 0.03), though the effect on secondary outcomes was not significant."

### Anti-Pattern: Nominalization Stack
**Symptoms:** Sentences like "The implementation of the evaluation of the performance of the algorithm was conducted..." — three nominalizations chained. **Fix:** Unwrap to verb form: "We evaluated the algorithm's performance by..."

### Polish Priority Checklist
- [ ] Argument logic: claim → evidence → boundary — every paragraph passes this test
- [ ] Hedge calibration: one qualifier per claim max, strength proportional to evidence
- [ ] Nominalization audit: ≤1 per sentence, zero in topic sentences
- [ ] Passive voice audit: Methods passive OK; Results/Discussion prefer active
- [ ] Sentence-length variety: SD ≥ 8 words (check with tool or spot-check 10 consecutive sentences)
- [ ] Terminology: same concept → same term throughout; no synonym roulette
- [ ] AI-tone scan: run de-ai quick-ref patterns; flag any Tier 1 hits
