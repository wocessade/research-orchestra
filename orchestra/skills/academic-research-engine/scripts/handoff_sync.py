#!/usr/bin/env python3
"""Sync .research/handoff into .paper writing artifacts (verified-only hard claims)."""
from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import date
from pathlib import Path

ISSUE_FIELDS = [
    "issue_id",
    "section",
    "claim_id",
    "contribution_id",
    "evidence_status",
    "artifact_path",
    "notes",
    "done",
]


def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def reject_planned_strong_numbers(handoff_text: str) -> list[str]:
    """Heuristic: flag lines that look like strong numbers tagged planned."""
    problems = []
    for i, line in enumerate(handoff_text.splitlines(), 1):
        low = line.lower()
        if "planned" in low and re.search(r"\d+(\.\d+)?%|\bp\s*<\s*0\.\d+", line):
            problems.append(f"line {i}: planned + strong number pattern")
    return problems


def ensure_contribution(paper: Path, handoff: Path, force: bool) -> None:
    dst = paper / "confirmed_contribution.md"
    if dst.exists() and not force:
        print(f"keep existing {dst}")
        return
    # Minimal seed — user must confirm
    tpl = Path(__file__).resolve().parents[2] / "academic-shared" / "contribution" / "confirmed_contribution.template.md"
    text = tpl.read_text(encoding="utf-8") if tpl.is_file() else "# Confirmed Contribution\n\n```yaml\nuser_confirmed: false\n```\n"
    # Annotate source
    banner = f"\n\n<!-- seeded by handoff_sync from {handoff.as_posix()} on {date.today().isoformat()} — set user_confirmed after explicit OK -->\n"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text + banner, encoding="utf-8", newline="\n")
    print(f"wrote {dst}")


def ensure_map(paper: Path) -> None:
    dst = paper / "contribution_experiment_map.md"
    if dst.exists():
        return
    tpl = Path(__file__).resolve().parents[2] / "academic-shared" / "contribution" / "contribution-experiment-map.template.md"
    text = tpl.read_text(encoding="utf-8") if tpl.is_file() else "# map\n"
    dst.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {dst}")


def ensure_issues(paper: Path) -> None:
    dst = paper / "issues.csv"
    if dst.exists():
        return
    tpl = Path(__file__).resolve().parents[2] / "academic-shared" / "issues" / "issues.template.csv"
    text = tpl.read_text(encoding="utf-8") if tpl.is_file() else ",".join(ISSUE_FIELDS) + "\n"
    dst.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {dst}")


def ensure_bank(paper: Path, research_root: Path) -> None:
    dst = paper / "citation_support_bank.md"
    if dst.exists():
        return
    tpl = Path(__file__).resolve().parents[2] / "academic-shared" / "citation" / "citation_support_bank.template.md"
    text = tpl.read_text(encoding="utf-8") if tpl.is_file() else "# Citation Support Bank\n"
    reads = research_root / "reads"
    extra = "\n## Seeded from .research/reads\n\n"
    if reads.is_dir():
        for p in sorted(reads.glob("*.md")):
            extra += f"- `{p.name}` — import locators (S/C/F/T) manually into bank rows\n"
    else:
        extra += "- (no reads yet)\n"
    dst.write_text(text + extra, encoding="utf-8", newline="\n")
    print(f"wrote {dst}")


def scan_verified_runs(research_root: Path) -> list[dict[str, str]]:
    rows = []
    exp_root = research_root / "experiments"
    if not exp_root.is_dir():
        return rows
    for metrics in exp_root.glob("EXP-*/runs/*/metrics.json"):
        import json
        data = json.loads(metrics.read_text(encoding="utf-8"))
        if data.get("status") == "completed" and data.get("meets_success_criteria") is True:
            rows.append(data)
    return rows


def refresh_ready(handoff_dir: Path, research_root: Path, paper_dir: Path, module: str) -> Path:
    handoff_dir.mkdir(parents=True, exist_ok=True)
    ready = handoff_dir / "ready_for_writing.md"
    verified = scan_verified_runs(research_root)
    neg_dir = research_root / "negatives"
    forbidden = []
    if neg_dir.is_dir():
        for n in sorted(neg_dir.glob("NEG-*.md")):
            forbidden.append(f"- from `{n.name}`: do not hard-claim linked H/EXP")
    lines = [
        "---",
        f"generated: {date.today().isoformat()}",
        f"research_root: {research_root.as_posix()}",
        f"paper_dir: {paper_dir.as_posix()}",
        f"suggested_module: {module}",
        "suggested_entry_point: idea-first",
        "suggested_writing_format: latex",
        "user_confirmed_handoff: false",
        "---",
        "",
        "# Ready for writing",
        "",
        "## Verified evidence only",
        "",
        "| Ci / claim | EXP / run | artifact | metric summary | ISS seed |",
        "|------------|-----------|----------|----------------|----------|",
    ]
    for d in verified:
        metrics_s = ", ".join(f"{k}={v}" for k, v in list((d.get("metrics") or {}).items())[:4])
        lines.append(
            f"| {d.get('contribution_id') or ''} | {d.get('exp_id')}/{d.get('run_id')} | "
            f"`experiments/{d.get('exp_id')}/runs/{d.get('run_id')}/metrics.json` | {metrics_s} | |"
        )
    if not verified:
        lines.append("| — | — | — | *no verified runs* | — |")
    lines += ["", "## Forbidden hard-claims (from NEG / unverified)", ""]
    lines += forbidden or ["- (none filed)"]
    lines += [
        "",
        "## Hard rules",
        "",
        "1. No `planned` strong numbers in this package.",
        "2. Journal/thesis S1/S3/T1 preload this folder when present.",
        "3. Set `user_confirmed_handoff: true` only after explicit user OK.",
        "",
    ]
    ready.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return ready


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--research-root", type=Path, default=Path(".research"))
    ap.add_argument("--paper-dir", type=Path, required=True)
    ap.add_argument("--module", default="academic-journal", choices=["academic-journal", "academic-thesis"])
    ap.add_argument("--force-contribution", action="store_true")
    ap.add_argument("--allow-empty-verified", action="store_true",
                    help="Allow sync when no verified runs (still blocks strong numbers)")
    args = ap.parse_args()

    research = args.research_root
    handoff_dir = research / "handoff"
    paper = args.paper_dir / ".paper"
    paper.mkdir(parents=True, exist_ok=True)

    ready = refresh_ready(handoff_dir, research, args.paper_dir, args.module)
    text = read_text(ready)
    problems = reject_planned_strong_numbers(text)
    if problems:
        print("HARD: handoff contains planned strong-number patterns:")
        for p in problems:
            print(" ", p)
        return 2

    verified = scan_verified_runs(research)
    if not verified and not args.allow_empty_verified:
        print("HARD: no verified runs — refusing to imply strong Results; pass --allow-empty-verified to seed scaffolds only")
        # still write ready file; do not invent issues verified rows
        ensure_contribution(paper, ready, args.force_contribution)
        ensure_map(paper)
        ensure_issues(paper)
        ensure_bank(paper, research)
        print("seeded scaffolds only; ready_for_writing.md updated")
        return 2

    ensure_contribution(paper, ready, args.force_contribution)
    ensure_map(paper)
    ensure_issues(paper)
    ensure_bank(paper, research)

    # If verified runs have contribution_id, mark matching issues verified
    issues_path = paper / "issues.csv"
    if issues_path.is_file() and verified:
        with issues_path.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        by_c = {d.get("contribution_id"): d for d in verified if d.get("contribution_id")}
        for r in rows:
            cid = r.get("contribution_id")
            if cid in by_c:
                d = by_c[cid]
                r["evidence_status"] = "verified"
                r["artifact_path"] = f"experiments/{d['exp_id']}/runs/{d['run_id']}/metrics.json"
        with issues_path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=ISSUE_FIELDS)
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in ISSUE_FIELDS})

    print(f"OK: handoff synced → {paper}")
    print(f"     ready: {ready}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
