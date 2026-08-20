# Color palettes

## Okabe–Ito (default categorical, colorblind-safe)

| Name | Hex |
|------|-----|
| orange | `#E69F00` |
| sky blue | `#56B4E9` |
| bluish green | `#009E73` |
| yellow | `#F0E442` |
| blue | `#0072B2` |
| vermillion | `#D55E00` |
| reddish purple | `#CC79A7` |
| black | `#000000` |

## Ocean Dusk (optional distinctive set)

`#264653`, `#2A9D8F`, `#E9C46A`, `#F4A261`, `#E76F51`

Use "Ours" = warm accent; baselines = gray `#B0BEC5`.

## Rules

- Prefer preset palettes; record `palette_name` in audit.
- Redundant encode categories (shape/line/hatch), not color alone.
- Sequential data: viridis/cividis — never jet/rainbow.
- Diverging: only when a meaningful midpoint exists.
- Test grayscale readability for category encodings.
