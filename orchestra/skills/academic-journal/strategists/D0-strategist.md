# Stage D0: Data Inventory [Strategist]

**Gate:** QD0 (SOFT BLOCK)
**Goal:** Document user-provided data for the Data-First pipeline.
**Needs Composers:** none

## Decisions

### Axis Routing
D0 is a sequential single-agent stage (DP1 ref.). No axis/passport branching — all data-first pipelines start here.

### Composer Sequence
1. (single-agent sequential — no composers)

### Sub-Step Execution Order
D0A (File Inventory) → D0B (Variable Documentation) → D0C (Missingness Assessment) → D0D (Data Structure Documentation) → D0Z (Data Manifest Review)

Strictly sequential. Each sub-step depends on the prior. No parallelism.

### STOP-AND-ASK Points
- **D0A (line 29):** If data format is unrecognizable (proprietary binary, instrument-specific output, images, video, audio) → present what can be determined and ask user about exported tabular/text version.
- **D0B (line 44):** For domain-specific variables with ambiguous interpretation → ask user to clarify meaning. Do not guess.
- **D0C (line 75):** If missingness > 20% on key variables or systematic pattern suggests data quality issues → ask whether to drop, impute, or treat as secondary analysis.
- **D0Z (line 114):** Present complete manifest to user. Ask confirmation: (1) variable interpretations correct, (2) flagged concerns acceptable, (3) proceed with this data. Manifest does not need to be perfect.

### Passport Update
After user confirmation, write passport fields:
- `data_manifest.n_files`, `data_manifest.n_variables`, `data_manifest.n_observations`
- `data_manifest.missingness_flags`, `data_manifest.unit_of_analysis`, `data_manifest.data_type`

## Gate

### QD0 Gate Checklist
- [ ] Data files inventoried (D0A): format, size, source, collection period, license
- [ ] Variables documented (D0B): type, interpretation, coding, unit, role
- [ ] Missingness assessed (D0C): per-variable, per-row, patterns, mechanism
- [ ] Data structure documented (D0D): unit of analysis, hierarchy, identifiers, time structure
- [ ] Data manifest reviewed and confirmed by user (D0Z)
- [ ] Passport fields written
- [ ] Stage completion log appended

### Gate Failure Route
QD0 is SOFT BLOCK — incomplete manifest does NOT block. Two failure paths:

1. **Manifest incomplete but user confirms proceed** → route to D1 with `[INCOMPLETE]` tag. Remaining fields marked as "to be supplemented."
2. **User says data is unusable** → STOP-AND-ASK: ask if alternative data exists, or route to Idea-First entry point.
