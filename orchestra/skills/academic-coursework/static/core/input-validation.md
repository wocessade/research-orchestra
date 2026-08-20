# Input Validation Protocol

User-provided data must be validated before the pipeline acts on it. Never silently accept malformed input.

| Input Type | Validation | Action on Failure |
|------------|-----------|-------------------|
| **Reference lists** (GB/T 7714, BibTeX, .nbib) | Minimum count check (≥3 items). Validate basic structure: author/year/title fields present | Return specific error with correct format example. Do not proceed with partial references. |
| **Sample papers** (PDF, .tex, list of titles) | Minimum count check (≥2 sample papers for journal reverse-engineering; ≥3 for Chinese adapter S8.6) | If too few: "I need at least [N] sample papers to [task]. You provided [M]." |
| **CNKI/万方/维普 search results** | Check that provider is named, search date recorded, result count > 0. Verify that each result has title + author + journal fields | If provider unspecified: ask. If results empty: confirm search terms before retrying. |
| **Funding information** (grant numbers, funder names) | Verify format matches funder conventions (e.g., NSF award numbers, NSFC 项目批准号 format) | Flag format mismatch; do not silently correct. Ask user to confirm. |
| **Conflicting information** | If sample paper structure ≠ journal author guidelines → flag conflict | Present conflict to user with evidence for both sides. Do not choose silently. |
| **Proprietary data files** (.VGD, .RAW, .WIFF, etc.) | Check that D0Z manifest has instrument name and characterization method. If not → STOP AND ASK per D0Z rules | Do not attempt to parse. Ask user to export as CSV/text. |

**General rule:** If validation fails, return a specific error message showing (a) what was received, (b) what format is expected, (c) an example of correct input. Never silently correct or guess.
