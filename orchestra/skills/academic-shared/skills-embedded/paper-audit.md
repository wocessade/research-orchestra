# Paper Audit (Embedded)

**Source:** `paper-audit` v5.1.0 | **Snapshot:** 2026-06-06
**Pipeline usage:** S7 (Paper Audit gate Q7), S9 (Multi-Persona Review gate Q9)

## Core Purpose
Reviewer-style structured audit: find technical, methodological, claim-level,
and cross-section issues; return structured issue bundle + revision roadmap.
Do NOT rewrite the paper source — this is a reviewer, not an editor.

## Audit Modes
- **quick-audit:** Fast submission-readiness screen
- **deep-review:** Structured issue bundle (Critical/Major/Minor)
- **gate:** PASS/FAIL decision calibrated for submission blockers
- **re-audit:** Compare current issues against previous audit

## Issue Classification
| Severity | Meaning | Gate Impact |
|----------|---------|-------------|
| Critical | Fatal flaw — invalidates claims | BLOCKS submission |
| Major | Significant weakness — undermines confidence | Must fix |
| Moderate | Notable concern — should address | Should fix |
| Minor | Cosmetic or clarity issue | Optional |

## Review Dimensions
1. **Methodology** — design validity, sample adequacy, controls
2. **Claims** — supported by evidence? overclaimed?
3. **Literature** — gap fairly positioned? key refs cited?
4. **Logic** — argument chain complete? no leaps?
5. **Reproducibility** — methods replicable? data/code available?
6. **Ethics** — IRB, competing interests, data integrity

## Critical Rules
- Anchor every finding to a quote/section/exact location
- Distinguish script-backed findings from LLM judgment
- Don't fabricate references, baselines, or reviewer evidence
- Don't rewrite prose — keep review separable from edits
