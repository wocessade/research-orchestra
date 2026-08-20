#!/usr/bin/env python3
"""import_feedback.py — Batch import human scores into feedback log.

Usage:
    python import_feedback.py --csv <path> --report-dir <path> --feedback-log <path>
"""

import argparse
import csv
import json
from datetime import date
from pathlib import Path

try:
    import yaml
except ImportError:
    import sys
    print("ERROR: PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Batch import human scores into feedback log")
    parser.add_argument("--csv", required=True, help="CSV with columns: paper_id, tier, human_score, human_grade")
    parser.add_argument("--report-dir", required=True, help="Directory containing paper/report.json files")
    parser.add_argument("--feedback-log", required=True, help="Path to feedback_log.yaml to append to")
    args = parser.parse_args()

    entries = []
    with open(args.csv, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            paper_id = row["paper_id"]
            report_path = Path(args.report_dir) / paper_id / "report.json"

            if not report_path.exists():
                print(f"WARNING: Report not found: {report_path}")
                continue

            with open(report_path, encoding="utf-8") as rf:
                report = json.load(rf)

            engine_score = report.get("total_score", 0)
            human_score = int(row.get("human_score", 0))
            delta = round(engine_score - human_score, 1)

            entry = {
                "paper": paper_id,
                "tier": row.get("tier", report.get("tier", "unknown")),
                "engine_score": engine_score,
                "engine_grade": report.get("grade", ""),
                "human_score": human_score,
                "human_grade": row.get("human_grade", ""),
                "delta": delta,
                "dimension_deltas": {},
                "dimensions_active": list(report.get("dimension_scores", {}).keys()),
                "timestamp": date.today().isoformat(),
            }
            entries.append(entry)
            print(f"  {paper_id}: engine={engine_score}, human={human_score}, delta={delta:+}")

    # Load existing log
    existing_entries = []
    if Path(args.feedback_log).exists():
        with open(args.feedback_log, encoding="utf-8") as f:
            existing_data = yaml.safe_load(f) or {}
            existing_entries = existing_data.get("entries", [])

    # Merge
    existing_entries.extend(entries)

    with open(args.feedback_log, "w", encoding="utf-8") as f:
        yaml.dump({"entries": existing_entries}, f, allow_unicode=True, default_flow_style=False)

    print(f"\nImported {len(entries)} entries.")
    print(f"Total entries in {args.feedback_log}: {len(existing_entries)}")


if __name__ == "__main__":
    main()
