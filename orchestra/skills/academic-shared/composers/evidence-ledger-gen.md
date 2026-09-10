# Composer: Evidence Ledger Generation

**Used by:** S4/T4 writing; S7/T5 review; revisions and post-expansion review.
**Inputs:** current manuscript, available references/run artifacts/derivations, output_dir.

Load [ledger-protocol.md](../evidence-ledger/ledger-protocol.md) and follow its schema and lifecycle.

1. Extract every claim requiring evidence from the current section, whether or not it has a citation. Include numerical, comparative, causal, novelty and scope claims; skip only background common knowledge that does not carry the argument.
2. Reuse its stable claim_id and assign a new claim_revision when wording, evidence or interpretation changes. Record current manuscript_revision and 0-based paragraph_index.
3. Link literary claims to source_ref + verbatim source_excerpt + locator; experiment/derivation claims to actual artifact_path + locator. If missing, record evidence_kind=missing, source_ref="", source_excerpt=null and audit_status=orphan. Never invent evidence.
4. Append the revision to `{output_dir}/evidence_ledger.jsonl`; new or changed evidence starts pending until support is checked. Do not duplicate the same revision on repeated execution.
5. Audit using the current manuscript and latest applicable claim revisions. Use only pending / verified / orphan / mismatch. confidence records writer judgment, not verification.
6. Pass ledger, current manuscript and available sources to the existing factual/content reviewer; write evidence_audit.md and add actionable findings to the review issue list.

Do not score citation density or use source access alone to mark a claim verified. Preserve real uncertainty and follow the module's anti-defensive writing rule when revising unsupported claims.
