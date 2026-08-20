# Stage S11: Post-Submission [Strategist]

**Gate:** Q11 (SOFT BLOCK) — post-submission tracking complete, R&R routed to S12.

**Goal:** Handle editorial decisions — rejection, R&R, or acceptance.

**Needs Composers:** none

## Decisions

### Decision Type Routing (11B, lines 20-92)

**Desk Reject (11B-Reject, lines 22-26):**
- Cause: scope mismatch, format non-compliance, quality below bar.
- Action: Return to S8.5 for venue re-selection. Do NOT modify content — desk reject means paper was never evaluated on content.

**Reject with Invitation to Resubmit (11B-Reject, lines 28-31):**
- Editor sees potential but needs substantial revision.
- Action: Follow R&R workflow to address comments, then resubmit to same journal as new manuscript. Response Matrix should acknowledge prior review.

**Review Reject (11B-Reject, lines 33-39):**
Parse root cause and route accordingly:

| Root Cause | Action | Rollback Point |
|-----------|--------|---------------|
| Fundamental design/data flaw | Redesign | S1 (Idea-First) or D2 (Data-First) |
| Fixable issues (weak framing, missing analysis) | Fix and resubmit elsewhere | Follow R&R workflow, then S8.5 |
| Unreasonable/biased reviewer | Ignore comments | S8.5 for new venue |

**Revise & Resubmit (11B-RR, lines 43-58):**
Two-part workflow: triage in S11, full execution in S12.

Step 1: Parse & Classify. Load editor decision letter + all reviewer reports. For each comment:
   - Extract individual requests (one paragraph may contain 2-3 requests)
   - Number: R1-1, R1-2, ..., R2-1, R2-2, ...
   - Classify by type: Revise text / Add analysis / Add experiment / Argue-defend / Clarify / Reject politely

Step 2: Present summary: "{N} reviewer comments parsed."
STOP-AND-ASK: "Route to Stage 12 for full R&R execution?" User confirms -> proceed to S12.

### Multi-Round R&R Loop (11B-RR-Loop, lines 60-72)
- Second/subsequent revision: re-enter at 11B-RR Step 1 — parse new comments.
- Track round number (Round 1, Round 2, etc.) in Response Matrix.
- Cross-reference: new comments relating to previous round changes should cite prior response.
- IF revised manuscript rejected after R&R:
  - Response Matrix is salvageable — reuse for next journal.
  - Route: go directly to S8.5 for new venue. Do NOT re-enter 11B-RR.
- IF 3 cumulative revision rounds with no acceptance -> STOP-AND-ASK: poor journal fit (-> S8.5) or need fundamental revision (-> S1/D2).

### Acceptance Routing (11B-Accept, lines 82-91)

**Conditional Acceptance:**
- Mini-R&R: parse required changes, fix inline (no stage re-execution), resubmit within deadline.
- Q11 gate still applies — verify all conditional items addressed.

**Full Acceptance:**
- Review proof for typesetting errors, figure placement, broken references.
- Check author names, affiliations, funding numbers one final time.
- Submit final version + copyright transfer + data archiving.
- Optional: post to preprint server with "accepted at [Journal]" note.

### Resubmission Package (11B-Resubmit, lines 74-80)
After completing R&R workflow:
1. Re-execute S10 (Submission Prep) — new cover letter (referencing revision), updated DAS, re-confirmed author approvals.
2. IF venue changed -> re-run S8 (Format & Compile) for new venue template BEFORE S10.
3. After resubmission -> return to 11A (Waiting Period).

### Composer Sequence
None. S11 is a decision-routing stage with no composer invocation.

## Gate

### Q11 Gate Checklist (Soft Block)
- [ ] Submission date, expected review time, and expected decision date recorded
- [ ] If R&R: all reviewer comments numbered and addressed in Response Matrix
- [ ] If R&R: all Critical/Major items resolved; change locations documented
- [ ] If rejected: root cause documented, new venue selected via S8.5
- [ ] If accepted: proof checked, final version submitted

### Gate Failure Route
Q11 is SOFT BLOCK — failure does not block pipeline but indicates incomplete tracking or routing.

- IF R&R comments not fully parsed -> route to S12A.
- IF no decision handler triggered -> STOP-AND-ASK for current manuscript status.
