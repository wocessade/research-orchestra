# Composer: citation-anchor-format

**Purpose:** Bind in-text claims to bibliography keys with machine-parseable anchors.
**Used by:** academic-journal S4/S6, academic-thesis T4
**Parameters:** `{writing_format}` (optional; prefer passport.writingFormat)

## Format branch (mandatory)

### If `writingFormat == latex` (or manuscript is `.tex`)

Use **native LaTeX citations only**. Do **not** insert HTML comments (`<!--ref:...-->`) — LaTeX does not treat them as comments; they leak into the PDF.

Required pattern:

```latex
Smith (2024) demonstrated X~\cite{smith2024}.
% optional note: claim anchored to smith2024 §3 / p.14
```

Gate checks for latex:
- Every `\cite{key}` / `\citep` / `\autocite` resolves in `.bib`
- Run `python ../academic-latex/scripts/verify_paper.py {tex_root}` (add `--allow-cjk` for Chinese)
- Optional `% ref:key` notes are fine; never HTML

Then skip the HTML rules below.

### If `writingFormat` is word / markdown / auto-detect prose

Use HTML comment anchors as follows.

---

# Composer: Citation Anchor Format

**Purpose:** Enforce a traceable two-layer citation structure (ref + anchor) and perform claim-to-citation alignment audit.
**Used by:** S4 (all writing protocols), S6 (claim alignment verification)
**Parameters:** `output_dir` (for audit report), manuscript sections being written

## Instructions

### 1. Two-Layer Citation Structure

Every citation in the body text must carry a ref tag and an anchor locator, forming a traceable two-layer structure:

```
Smith (2024) demonstrated... <!--ref:smith2024--><!--anchor:page:14-->
```

- **ref tag** `<!--ref:citation_key-->`: Points to the `citation_key` of the reference, corresponding to a `bibliography.json` entry.
- **anchor locator** `<!--anchor:kind:value-->`: Specifies the exact location of the cited content in the source document.

### 2. Anchor Kinds

| Kind | Meaning | Value Format | Example |
|------|---------|-------------|---------|
| `quote` | Verbatim quote | Quoted text (<= 25 English words or 40 Chinese characters) | `<!--anchor:quote:Attention is all you need-->` |
| `page` | Page number | Page number | `<!--anchor:page:14-->` |
| `section` | Section | Section name | `<!--anchor:section:related work-->` |
| `paragraph` | Paragraph number | Paragraph number | `<!--anchor:paragraph:3-->` |
| `none` | Explicitly no locator | Fixed value `claimed` | `<!--anchor:none:claimed-->` (does not bypass check; triggers warning) |

### 3. Rules

1. **One-to-one matching:** Every `<!--ref:...-->` must have a corresponding `<!--anchor:...-->` immediately following it (sequential order).
2. **Quote length limit:** `anchor:quote` value must not exceed 25 English words (or 40 Chinese characters).
3. **No orphans:** No orphan anchor tags (a `<!--anchor:...-->` without a corresponding `<!--ref:...-->`).
4. **Explicit declaration:** `anchor:none:claimed` is an explicit declaration of "I do not have a specific location as evidence." AI agents using this must attach a reason comment.

**Layout impact:** These HTML comments are invisible in Word/Markdown→docx pipelines. They are NOT safe in LaTeX sources — use the latex branch above., but they are parseable structured signals for AI agents.

### 4. Section-Specific Citation Examples

- **Citations in Methods:** `We used the method of Smith (2024) <!--ref:smith2024--><!--anchor:section:method-->...`
- **Direct comparison in Results:** `This is consistent with the 42% reported by Jones (2023) <!--ref:jones2023--><!--anchor:page:5-->`
- **Background citations in Introduction:** `The field has been extensively studied (Lee 2022 <!--ref:lee2022--><!--anchor:section:intro-->)`

### 5. Claim-to-Citation Alignment

After citations are written, perform a claim alignment check on the top-5 most heavily cited references:

1. For each of the top-5 papers (by citation count), extract: "What does our manuscript CLAIM this paper says?"
2. For the same 5 papers, verify against the paper's own abstract/intro/conclusion: "What does the paper ACTUALLY say?"
3. Classify each alignment using the table below and document results.

### 6. Alignment Classification Table

| Classification | Meaning | Action |
|---------------|---------|--------|
| `SUPPORTS` | Claim matches paper's actual finding | Proceed |
| `PARTIALLY SUPPORTS` | Claim is directionally correct but overstated/understated | Adjust claim wording |
| `DOES NOT SUPPORT` | Claim contradicts or is absent from the cited paper | **Critical** -- rewrite or find correct citation |

### 7. Documentation Format

Document results in `{output_dir}/citation_audit_summary.md`:

```
## Claim-to-Citation Alignment
| Reference | Our Claim | Paper's Actual Finding | Verdict |
|-----------|-----------|----------------------|---------|
| Smith 2024 | ... | ... | SUPPORTS |
| ... | ... | ... | PARTIALLY SUPPORTS |
```

## Verification

- [ ] Every `<!--ref:...-->` has a corresponding `<!--anchor:...-->` (one-to-one, sequential order)
- [ ] No `anchor:quote` value exceeds 25 English words (or 40 Chinese characters)
- [ ] No orphan anchor tags
- [ ] Every `anchor:none:claimed` has an attached reason comment
- [ ] Claim-to-citation alignment checked for top-5 most heavily cited references
- [ ] All `DOES NOT SUPPORT` entries have been rewritten or citations replaced

## Common Pitfalls

- **Missing anchor:** Adding a ref tag without its corresponding anchor locator. Always add both.
- **Overlong quotes:** Using more than 25 English words (40 Chinese characters) in an `anchor:quote` value. Truncate and use `anchor:page` instead.
- **Orphan anchors:** Adding an anchor tag without verifying the preceding ref tag exists.
- **Claim inflation:** Overstating what a cited paper actually found (leads to `PARTIALLY SUPPORTS` or `DOES NOT SUPPORT` verdicts). Always verify claims against original source.
- **Layout concern confusion:** Worrying that HTML comments will appear in the rendered output -- they will not. Word/Markdown pipelines ignore them; LaTeX does not — never use HTML anchors in `.tex`.
