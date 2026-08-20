# Generate Image (Embedded)

**Source:** `generate-image` | **Snapshot:** 2026-06-06
**Pipeline usage:** S5 — fallback for schematics when scientific-schematics unavailable

## When to Use
- **Use for:** Photos, illustrations, artwork, graphical abstracts, visual concepts
- **Use scientific-schematics instead for:** Flowcharts, circuits, pathways, system architectures

## Requirements
- OpenRouter API key required (`OPENROUTER_API_KEY` env var or `.env` file)
- Uses FLUX.2 Pro / Gemini 3.1 Flash Image Preview models

## Usage
```bash
python scripts/generate_image.py "description of image to generate"
python scripts/generate_image.py "make the sky purple" --input photo.jpg  # edit
```
