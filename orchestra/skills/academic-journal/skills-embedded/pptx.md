---
name: pptx
description: "PowerPoint (.pptx) creation for defense presentations and academic slides. Used at T7 for thesis defense PPT."
source: pptx v1.0 | snapshot: 2026-06-06
---

# PPTX Creation (Pipeline Extract)

## Quick Reference

| Task | Guide |
|------|-------|
| Read content | `python -m markitdown presentation.pptx` |
| Visual overview | `python scripts/thumbnail.py presentation.pptx` |
| Create from scratch | pptxgenjs — see below |
| Edit from template | Unpack → manipulate slides → edit → pack |

## Creating from Scratch (pptxgenjs)

```bash
npm install -g pptxgenjs
```

Use when no template is available. Generate via JS, convert to images, inspect, fix, repeat.

## Design Ideas

### Color Palettes (pick one that fits the topic)

| Theme | Primary | Secondary | Accent |
|-------|---------|-----------|--------|
| Midnight Executive | `1E2761` (navy) | `CADCFC` (ice blue) | `FFFFFF` (white) |
| Forest & Moss | `2C5F2D` (forest) | `97BC62` (moss) | `F5F5F5` (cream) |
| Coral Energy | `F96167` (coral) | `F9E795` (gold) | `2F3C7E` (navy) |
| Warm Terracotta | `B85042` (terracotta) | `E7E8D1` (sand) | `A7BEAE` (sage) |
| Charcoal Minimal | `36454F` (charcoal) | `F2F2F2` (off-white) | `212121` (black) |
| Teal Trust | `028090` (teal) | `00A896` (seafoam) | `02C39A` (mint) |
| Sage Calm | `84B59F` (sage) | `69A297` (eucalyptus) | `50808E` (slate) |

### Layout Rules

- One color dominates (60-70%), 1-2 supports, one accent
- Dark backgrounds for title/conclusion, light for content slides
- Every slide needs a visual element (image, chart, icon, shape)
- 0.5" minimum margins, 0.3-0.5" between content blocks
- Titles: 36-44pt bold; section headers: 20-24pt bold; body: 14-16pt
- Don't center body text; don't repeat same layout across slides
- **NEVER use accent lines under titles** (hallmark of AI slides)

### Font Pairings

| Header | Body |
|--------|------|
| Georgia | Calibri |
| Arial Black | Arial |
| Cambria | Calibri |
| Palatino | Garamond |

## QA Process (Required)

```bash
# Convert to PDF then images
python scripts/office/soffice.py --headless --convert-to pdf output.pptx
pdftoppm -jpeg -r 150 output.pdf slide

# Check for placeholder text
python -m markitdown output.pptx | grep -iE "xxxx|lorem|ipsum|this.*(page|slide).*layout"
```

**Visual inspection checklist:**
- Overlapping elements (text through shapes, lines through words)
- Text overflow or cut off at edges
- Decorative lines positioned for single-line but title wrapped
- Elements too close (< 0.3" gaps)
- Insufficient margin from slide edges (< 0.5")
- Low-contrast text/icons
- Leftover placeholder content

**Verification loop:** Generate → inspect → list issues → fix → re-verify. Never declare success after one pass.

## Dependencies

- `pip install "markitdown[pptx]"` — text extraction
- `npm install -g pptxgenjs` — creating from scratch
- LibreOffice (`soffice`) — PDF conversion
- Poppler (`pdftoppm`) — PDF to images
