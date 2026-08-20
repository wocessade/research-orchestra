# Concept / method diagrams

## When

Architecture, system design, pipelines, frameworks, teasers, graphical abstracts (draft).

## Style lock

Pick **one** visual style per paper and keep it:

- Classic accent-bar academic (safe, grayscale-friendly)
- Modern minimal
- Soft sketch / 简笔画 (overview only; check venue taste)
- Illustrated technical (icon-rich)

## Prompt structure (6 parts)

1. Framing — venue, takeaway, tone
2. Visual style — full style block
3. Color palette — exact hex + semantics
4. Layout — every box, region, reading order
5. Connections — every arrow (source, target, style, label)
6. Constraints — no logos, watermarks, fake numbers, tiny text, unsupported terms

Extract **exact terminology** from the paper; do not invent module names.

## Generation practice

- Prefer multiple attempts; pick best (quality varies).
- Minimize text in the image; overlay critical labels if glyphs distort.
- Save `figures/fig_<name>_prompt.md` + final asset.
- Optional TikZ reference for terminology alignment / compile fallback.

## TikZ path

Use when labels must be exact and re-editable. Ship `.tex` + compiled PDF.
Colorblind-safe fills; journal widths; compile with pdflatex/xelatex separately from main paper if heavy.

### Narrow-column routing rule

In two-column layouts (IEEE, ACM, `article`+`twocolumn`), column width is
typically 3.3–3.5 in (8.4–8.9 cm).  Curved edge routing via
`to[out=0, in=0]` or `to[out=-30, in=30]` produces large arcs that
overflow the column and trigger pgf "Returning node center" warnings.

Prefer orthogonal routing in narrow columns:
```latex
% Safe (orthogonal):
\draw[->] (a.south) -- ++(0,-0.3) -| (b.north);
\draw[->] (a.east)  -- ++(0.3,0)  |- (b.west);

% Problematic in < 4 in width:
\draw[->] (a.east) to[out=0, in=0] (b.east);   % arc may exceed column
```
Combine with `rounded corners=2pt` on the `tikzpicture` or individual
`\draw` for a polished look without the overflow risk.

## Never

- Put experimental numbers into a generated schematic and treat as results.
- Clip-art / stock icons / photorealistic clutter unless user asks.
