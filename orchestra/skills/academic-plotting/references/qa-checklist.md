# Figure QA checklist

Use before S5 exit, Q5 gate, and camera-ready.

## Logic

- [ ] One core conclusion; every panel earns space
- [ ] Backend matches class (no generative numbers)
- [ ] Source script/data or prompt exists
- [ ] Claim ledger message matches caption takeaway

## Visual / journal

- [ ] Built at target single/double width
- [ ] Readable at final paper size (zoom PDF page)
- [ ] Fonts embedded / svg fonttype none as required
- [ ] Lines ≥ 0.5 pt; no hairlines
- [ ] Panel labels consistent
- [ ] Colorblind-safe + grayscale OK when needed
- [ ] Vector for line art; DPI OK for rasters
- [ ] Blind / unsure on readability or concept-diagram garbled text → export final-width PNG and ask **deepseek-vision** one falsifiable hypothesis (e.g. axis labels still legible; no mojibake). Do not ask for a full-figure description. Numbers still reconcile from CSV/scripts, not from vision.

## Stats / integrity

- [ ] Error bars / n / tests are real or absent
- [ ] Numbers match CSV/tables in manuscript
- [ ] No logos, watermarks, unsupported mechanisms

## LaTeX

- [ ] File path resolves
- [ ] `\label` unique; referenced in text
- [ ] Caption complete (What/How/Takeaway)

## Gate Q5 alignment

At least type-appropriate schematic + data figures; complete captions; colorblind-safe; axes readable; vector/DPI rules satisfied.
