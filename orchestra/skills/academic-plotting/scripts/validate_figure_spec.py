#!/usr/bin/env python3
"""Validate figure_specs.yaml (per-figure required fields)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REQUIRED = [
    "figure_id", "filename", "figure_class", "message", "backend", "source", "caption_takeaway"
]
ALLOWED_CLASS = {"evidence-result", "concept-method"}

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None


def as_list(doc):
    if doc is None:
        return []
    if isinstance(doc, list):
        return doc
    if isinstance(doc, dict):
        if "figures" in doc and isinstance(doc["figures"], list):
            return doc["figures"]
        return [doc]
    return []


def validate_item(item: dict, idx: int) -> list[str]:
    problems = []
    prefix = f"figure[{idx}]"
    if not isinstance(item, dict):
        return [f"{prefix}: not a mapping"]
    for key in REQUIRED:
        if key not in item or item[key] in (None, ""):
            problems.append(f"{prefix}: missing `{key}`")
    fc = str(item.get("figure_class", ""))
    if fc and fc not in ALLOWED_CLASS:
        problems.append(f"{prefix}: figure_class must be evidence-result|concept-method (got {fc!r})")
    return problems


def validate_markdown_fallback(text: str, path: Path) -> list[str]:
    """Weak fallback when PyYAML missing or file is md: require keys per ## figure block."""
    problems = []
    blocks = [b for b in text.split("\n## ") if b.strip()]
    if len(blocks) <= 1 and "figure_id" in text:
        blocks = [text]
    for i, block in enumerate(blocks):
        low = block.lower()
        for key in REQUIRED:
            if key.lower() not in low:
                problems.append(f"{path.name} block[{i}]: missing key `{key}`")
        if "figure_class" in low and "evidence-result" not in low and "concept-method" not in low:
            problems.append(f"{path.name} block[{i}]: figure_class must include evidence-result or concept-method")
    if not blocks:
        problems.append(f"{path}: empty spec")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", type=Path)
    args = ap.parse_args()
    if not args.spec.exists():
        print(f"ERROR: {args.spec} not found")
        return 2
    text = args.spec.read_text(encoding="utf-8", errors="replace")
    problems: list[str] = []
    if args.spec.suffix.lower() in {".yaml", ".yml"} and yaml is not None:
        doc = yaml.safe_load(text)
        items = as_list(doc)
        if not items:
            problems.append(f"{args.spec}: no figure entries")
        for i, item in enumerate(items):
            problems.extend(validate_item(item, i))
    else:
        if args.spec.suffix.lower() in {".yaml", ".yml"} and yaml is None:
            print("WARN: PyYAML not installed; using markdown-like key scan", file=sys.stderr)
        problems = validate_markdown_fallback(text, args.spec)

    if problems:
        print("FAIL")
        for p_ in problems:
            print(" ", p_)
        return 1
    print("OK: figure-spec valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())