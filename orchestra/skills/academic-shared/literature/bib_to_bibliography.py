#!/usr/bin/env python3
"""Convert a BibTeX (.bib) file into bibliography.json for verify_citations.py.

Usage:
    python bib_to_bibliography.py refs.bib -o bibliography.json
    python bib_to_bibliography.py refs.bib -o bibliography.json --and-verify --output-dir ./verification

Does not invent metadata. Missing title/DOI fields are left empty for the verifier.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


ENTRY_RE = re.compile(r"@(?P<type>\w+)\s*\{\s*(?P<key>[^,\s]+)\s*,", re.I)
FIELD_RE = re.compile(
    r"(?P<field>title|author|year|doi|journal|booktitle|url)\s*=\s*"
    r"(?:\{(?P<braced>.*?)\}|\"(?P<quoted>.*?)\")\s*,?",
    re.I | re.S,
)


def strip_tex(s: str) -> str:
    s = s.replace("\&", "&").replace("\%", "%")
    s = re.sub(r"[{}]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_bib(text: str) -> list[dict]:
    # Drop @string / @comment / @preamble
    text = re.sub(r"@string\s*\{.*?\}", "", text, flags=re.I | re.S)
    text = re.sub(r"@comment\s*\{.*?\}", "", text, flags=re.I | re.S)
    text = re.sub(r"@preamble\s*\{.*?\}", "", text, flags=re.I | re.S)

    entries: list[dict] = []
    for m in ENTRY_RE.finditer(text):
        etype = m.group("type").lower()
        if etype in {"string", "comment", "preamble"}:
            continue
        key = m.group("key")
        start = m.end()
        # naive brace balance for entry body
        depth = 1
        i = start
        while i < len(text) and depth:
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
            i += 1
        body = text[start : i - 1]
        fields: dict[str, str] = {}
        for fm in FIELD_RE.finditer(body):
            val = fm.group("braced") if fm.group("braced") is not None else fm.group("quoted")
            fields[fm.group("field").lower()] = strip_tex(val or "")
        authors = fields.get("author", "")
        author_list = [a.strip() for a in re.split(r"\s+and\s+", authors) if a.strip()] if authors else []
        entries.append(
            {
                "citation_key": key,
                "title": fields.get("title", ""),
                "authors": author_list,
                "year": fields.get("year", ""),
                "doi": fields.get("doi", ""),
                "venue": fields.get("journal") or fields.get("booktitle") or "",
                "source": "bibtex",
                "url": fields.get("url", ""),
            }
        )
    return entries


def main() -> int:
    ap = argparse.ArgumentParser(description="BibTeX → bibliography.json for verify_citations.py")
    ap.add_argument("bib", type=Path, help="Path to .bib file")
    ap.add_argument("-o", "--output", type=Path, default=Path("bibliography.json"))
    ap.add_argument("--and-verify", action="store_true", help="Also run verify_citations.py")
    ap.add_argument("--output-dir", type=Path, default=Path("./verification"))
    args = ap.parse_args()

    if not args.bib.is_file():
        print(f"ERROR: bib not found: {args.bib}", file=sys.stderr)
        return 2

    entries = parse_bib(args.bib.read_text(encoding="utf-8", errors="replace"))
    args.output.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(entries)} entries → {args.output}")

    if args.and_verify:
        verify = Path(__file__).with_name("verify_citations.py")
        cmd = [
            sys.executable,
            str(verify),
            "--input",
            str(args.output),
            "--output-dir",
            str(args.output_dir),
        ]
        print("Running:", " ".join(cmd))
        return subprocess.call(cmd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
