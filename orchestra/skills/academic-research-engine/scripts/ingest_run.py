#!/usr/bin/env python3
"""Ingest a run metrics.json into the experiment registry and optionally .paper issues/map."""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    jsonschema = None  # type: ignore

SKILLS = Path(__file__).resolve().parents[2]
SCHEMA_PATH = SKILLS / "academic-shared" / "research" / "metrics.schema.json"
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


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_metrics(data: dict) -> list[str]:
    errs: list[str] = []
    for k in ("run_id", "exp_id", "status", "metrics"):
        if k not in data:
            errs.append(f"missing key {k}")
    if "exp_id" in data and not re.match(r"^EXP-\d{3,}$", str(data["exp_id"])):
        errs.append(f"bad exp_id {data.get('exp_id')!r}")
    if "status" in data and data["status"] not in {"completed", "aborted", "failed", "partial"}:
        errs.append(f"bad status {data.get('status')!r}")
    if jsonschema is None:
        errs.append("jsonschema is required (pip install jsonschema)")
    elif not SCHEMA_PATH.is_file():
        errs.append(f"schema file missing: {SCHEMA_PATH}")
    else:
        try:
            jsonschema.validate(data, load_schema())
        except Exception as e:  # noqa: BLE001
            errs.append(f"schema: {e}")
    return errs


def find_card(research_root: Path, exp_id: str) -> Path | None:
    p = research_root / "experiments" / exp_id / "card.md"
    return p if p.is_file() else None


def append_run_row(card: Path, run_id: str, metrics_path: Path, meets: str, notes: str) -> None:
    text = card.read_text(encoding="utf-8")
    row = f"| {run_id} | ingested | {metrics_path.as_posix()} | {meets} | {notes} |"
    marker = "## Run log"
    if marker not in text:
        text = text.rstrip() + f"\n\n{marker}\n\n| run_id | status | metrics path | meets_success | notes |\n|--------|--------|--------------|---------------|-------|\n{row}\n"
    else:
        # append before next ## if possible
        lines = text.splitlines()
        out: list[str] = []
        i = 0
        while i < len(lines):
            out.append(lines[i])
            if lines[i].strip() == marker:
                # copy until blank after table header or next ##
                i += 1
                while i < len(lines) and not lines[i].startswith("## "):
                    out.append(lines[i])
                    i += 1
                out.append(row)
                continue
            i += 1
        text = "\n".join(out) + "\n"
    card.write_text(text, encoding="utf-8", newline="\n")


def update_issues(issues_csv: Path, data: dict, artifact: str) -> None:
    issues_csv.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    if issues_csv.is_file():
        with issues_csv.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
    cid = data.get("contribution_id") or ""
    updated = False
    for r in rows:
        if cid and r.get("contribution_id") == cid:
            if data.get("status") == "completed" and data.get("meets_success_criteria") is True:
                r["evidence_status"] = "verified"
                r["artifact_path"] = artifact
                r["notes"] = (r.get("notes") or "") + f"; ingest {data.get('run_id')}"
                updated = True
    if not updated and cid:
        n = len(rows) + 1
        rows.append({
            "issue_id": f"ISS-{n:03d}",
            "section": "4.1",
            "claim_id": f"CLM-{n:03d}",
            "contribution_id": str(cid),
            "evidence_status": "verified" if data.get("meets_success_criteria") else "placeholder",
            "artifact_path": artifact,
            "notes": f"ingest {data.get('run_id')}",
            "done": "false",
        })
    with issues_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ISSUE_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in ISSUE_FIELDS})


def patch_map(map_path: Path, data: dict, artifact: str) -> None:
    cid = data.get("contribution_id")
    if not cid or not map_path.is_file():
        return
    text = map_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    out = []
    for line in lines:
        if line.startswith("|") and (f"| {cid} |" in line or f"| {cid} " in line):
            if data.get("meets_success_criteria") is True and data.get("status") == "completed":
                line = re.sub(r"\b(planned|placeholder)\b", "verified", line, count=1)
        out.append(line)
    map_path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("metrics_json", type=Path)
    ap.add_argument("--research-root", type=Path, default=Path(".research"))
    ap.add_argument("--paper-dir", type=Path, default=None, help="If set, update .paper/issues.csv and map")
    ap.add_argument("--open-neg-on-fail", action="store_true")
    args = ap.parse_args()

    if not args.metrics_json.is_file():
        print(f"HARD: missing {args.metrics_json}")
        return 2
    data = json.loads(args.metrics_json.read_text(encoding="utf-8"))
    errs = validate_metrics(data)
    if errs:
        print("HARD: metrics invalid:")
        for e in errs:
            print(" ", e)
        return 2

    exp_id = data["exp_id"]
    card = find_card(args.research_root, exp_id)
    if card is None:
        print(f"HARD: no card for {exp_id} under {args.research_root}/experiments/")
        return 2

    meets = data.get("meets_success_criteria")
    meets_s = "true" if meets is True else ("false" if meets is False else "")
    append_run_row(card, str(data["run_id"]), args.metrics_json, meets_s, data.get("notes") or "")

    # copy/pointer into runs/
    run_dir = args.research_root / "experiments" / exp_id / "runs" / str(data["run_id"])
    run_dir.mkdir(parents=True, exist_ok=True)
    dest = run_dir / "metrics.json"
    if dest.resolve() != args.metrics_json.resolve():
        dest.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")

    if args.paper_dir:
        paper = args.paper_dir / ".paper"
        update_issues(paper / "issues.csv", data, str(dest.as_posix()))
        patch_map(paper / "contribution_experiment_map.md", data, str(dest.as_posix()))
        print(f"updated {paper}")

    if args.open_neg_on_fail and (meets is False or data.get("status") in {"failed", "aborted"}):
        neg_dir = args.research_root / "negatives"
        neg_dir.mkdir(parents=True, exist_ok=True)
        neg_id = f"NEG-{len(list(neg_dir.glob('NEG-*.md'))) + 1:03d}"
        neg = neg_dir / f"{neg_id}.md"
        if not neg.exists():
            neg.write_text(
                f"---\nid: {neg_id}\nexp_ids: [{exp_id}]\nhypothesis_ids: {data.get('hypothesis_ids', [])}\n"
                f"impact: weakens\n---\n\n# {neg_id} auto-opened by ingest_run\n\n"
                f"Run `{data['run_id']}` did not meet success criteria. Fill causes before handoff.\n",
                encoding="utf-8",
                newline="\n",
            )
            print(f"opened {neg}")

    print(f"OK: ingested {data['run_id']} → {exp_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
