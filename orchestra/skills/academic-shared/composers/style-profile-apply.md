# Composer: Style Profile Application

**Purpose:** Apply author style profile soft constraints during writing and perform multi-dimensional consistency checks against the profile.
**Used by:** S4 (section writing), S7 (style consistency check)
**Parameters:** `target_profile` (from `.pipeline_state.json` -> `passport.style_profile`), manuscript sections being written

## Instructions

### 1. Null Check

If `style_profile` is `null` in the Passport (`.pipeline_state.json` -> `passport.style_profile`), skip all style profile steps entirely. Proceed without applying any style constraints.

### 2. Soft Constraints (Writing Phase)

When a style_profile exists, apply these four soft constraints during the writing phase:

**1. Sentence length distribution** -- Keep deviation from profile <= 20%. Exact matching is not required, but this prevents AI-style uniform sentence lengths.

**2. Citation integration style** -- If the profile is predominantly integral (>60%), use "Author (Year) found..." format for in-text citations.

**3. Modifier style** -- If the profile shows high hedge density, increase cautiously worded conclusions in the Discussion accordingly.

**4. Paragraph length** -- Keep deviation from profile <= 30%.

### 3. Priority Rule

When constraints conflict, resolve in this order:

```
Journal conventions (HARD) > Disciplinary norms (STRONG) > Author personal style (SOFT)
```

- **HARD** -- Must be followed (e.g., journal template requirements on citation format, section structure).
- **STRONG** -- Should be followed but can be overridden by journal conventions (e.g., typical methods of presenting data in the discipline).
- **SOFT** -- Follow when possible, but yield to both of the above (e.g., author's preferred sentence length, hedging frequency).

### 4. Six-Dimension Consistency Check (Audit Phase)

During the audit phase (S7), compare the manuscript against the profile across these 6 dimensions:

1. **Sentence length distribution** -- Compare mean and variance against profile.
2. **Citation integration style** -- Integral vs. non-integral ratio.
3. **Modifier/hedge density** -- Frequency of hedging language.
4. **Paragraph length** -- Mean paragraph length in words/characters.
5. **Vocabulary register** -- Formality level, jargon density.
6. **Voice/tense distribution** -- Active vs. passive voice, tense consistency.

### 5. Audit Output Format

Output a `style_consistency_report` with this structure:

```json
{
  "aligned_dimensions": 4,
  "total_dimensions": 6,
  "deviations": [
    {
      "dimension": "sentence_length_distribution",
      "current_value": 22.5,
      "profile_value": 18.0,
      "acceptable": false
    },
    {
      "dimension": "paragraph_length",
      "current_value": 120,
      "profile_value": 95,
      "acceptable": true
    }
  ]
}
```

- `aligned_dimensions`: Count of dimensions where deviation is within acceptable range.
- `deviations`: Array of per-dimension comparisons, each with `acceptable: bool`.
- Unacceptable deviations are recorded as Minor items for the author to address.

## Verification

- [ ] `style_profile` null check performed -- skip if null
- [ ] Sentence length distribution within 20% of profile
- [ ] Citation integration style matches profile (integral >60% triggers "Author (Year) found..." format)
- [ ] Hedge density applied appropriately
- [ ] Paragraph length within 30% of profile
- [ ] Priority rule applied: Journal > Discipline > Personal
- [ ] 6-dimension consistency check completed
- [ ] `style_consistency_report` generated with aligned_dimensions count and deviation details
- [ ] Unacceptable deviations recorded as Minor items

## Common Pitfalls

- **Skipping the null check:** Attempting to apply style profile constraints when no profile exists. Always check for null first.
- **Over-applying soft constraints:** Treating soft constraints as hard rules. Remember the 20%/30% thresholds allow deviation within bounds.
- **Priority violation:** Letting personal style preferences override journal conventions. Journal requirements always win.
- **Citation style mismatch:** Failing to detect whether the profile is integral or non-integral dominant before choosing citation format.
- **Hedge density overcorrection:** Indiscriminately increasing hedging everywhere in the Discussion instead of only in cautiously worded conclusions.
- **Ignoring the report output:** Generating the consistency report but not recording unacceptable deviations as actionable items.
