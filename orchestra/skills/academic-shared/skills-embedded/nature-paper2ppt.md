# Nature Paper-to-PPT (Embedded)

**Source:** `nature-paper2ppt` | **Snapshot:** 2026-06-06
**Pipeline usage:** T7 (Defense PPT — Agent 1: T7B)

## Core Principle
Use the paper's scientific argument as the presentation spine. The audience should answer:
1. Why does this problem matter?
2. What gap does the paper address?
3. What did the authors do?
4. What is the key evidence?
5. Why should we trust the result?
6. What is new/reusable/meaningful?
7. Where are the boundaries?

## Slide Structure (Chinese Defense Standard)
1. Title slide (论文题目, 作者, 导师, 学院)
2. Outline (目录/汇报提纲)
3. Research Background (1-2 slides)
4. Research Question & Significance (1 slide)
5. Literature Review — brief, key gaps only (1-2 slides)
6. Methodology (1-2 slides, diagram preferred)
7-10. Key Results (3-5 slides — most important)
11. Discussion (1 slide)
12. Conclusion & Innovation (1 slide)
13. Limitations & Future Work (1 slide)
14. Publications/Achievements (1 slide)
15. Acknowledgements (1 slide)
16. Q&A slide

## Design Rules
- Clean academic — white/light background, dark text, 1 accent color
- No dense text walls — one clear message per slide
- Chinese content with English technical terms where standard
- Font: title ≥ 28pt, body ≥ 18pt, figure labels ≥ 14pt
- All figures readable from 5m away

## Toolchain
- Python-first: PyMuPDF (extraction) + Pillow (cropping) + python-pptx (slides)
- Must work on macOS, Linux, Windows
- No LibreOffice/soffice dependency by default

## Examples

### Before/After: Wall-of-Text → One Message Per Slide

**Before (wall-of-text slide):**
> Title: "Results"
> Body: "The treatment group showed significant improvement on all three primary outcomes. The mean response time decreased by 78 ms (95% CI [49, 107], p < 0.001). Accuracy increased by 12.3 percentage points (p = 0.004). The composite score improved by 0.8 SD (p = 0.002). Secondary outcomes showed mixed results..."

→ Audience reads the slide instead of listening. Three findings compete for attention.

**After (one message per slide):**
> Slide 7 — Title: "Treatment reduced response time by 78 ms"
> Body: Large effect-size visualization + CI bar. One sentence: "Cohen's d = 1.6, consistent across all three task blocks."
> (Accuracy and composite score move to slides 8 and 9.)

### Anti-Pattern: 截图式PPT
**症状：** 把论文段落截图贴到 PPT 上——观众既读不清，也听不懂。表格直接从论文 copy-paste，字号 < 14pt。**修复：** 每张幻灯片只传达一个信息。表格简化为 3-4 行关键对比。全文截图 → 改为摘取关键数字 + 图表。

### Pre-Defense Checklist
- [ ] Every slide has exactly one message (test: can you state it in 5 seconds?)
- [ ] No text walls — maximum 6 lines per slide, 8 words per line
- [ ] All figures readable from 5m (body text ≥ 18pt, figure labels ≥ 14pt)
- [ ] PPT slide count matches script time estimate (±2 slides)
- [ ] Every figure/table in the PPT also appears in the defense script with a transition cue
- [ ] Anticipated Q&A covers every weakness flagged in the T5 review report
- [ ] Acknowledgments slide includes advisor, lab, funder, and AI use declaration reference
