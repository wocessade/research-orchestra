#!/usr/bin/env python3
"""calibrate.py — Calibration file generation/update from feedback logs.

Computes time-decayed weighted average of engine-vs-human deltas,
applies sample count thresholds to determine update action.

Usage:
    python calibrate.py --feedback-log <path> --calibration-file <path> \
        [--lambda 0.01]

    python calibrate.py --csv <path> --report-dir <path> \
        --feedback-log <path>  (interactive mode)
"""

import argparse
import csv
import json
import math
import os
from datetime import date, datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    import sys
    print("ERROR: PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)


def time_decay_weight(days_elapsed, lambda_=0.01):
    """Compute exponential decay weight."""
    return math.exp(-lambda_ * max(0, days_elapsed))


def compute_calibration(feedback_entries, lambda_=0.01):
    """Compute time-decayed calibration from feedback entries.

    Args:
        feedback_entries: list of dicts with keys:
            - delta: float (engine - human)
            - timestamp: str (ISO date)
        lambda_: decay factor

    Returns:
        dict with action, adjustment, message, sample_count
    """
    today = date.today()
    total_weight = 0.0
    weighted_sum = 0.0
    n = len(feedback_entries)

    for entry in feedback_entries:
        try:
            ts = datetime.fromisoformat(entry["timestamp"]).date()
        except (ValueError, TypeError):
            ts = today
        days = (today - ts).days
        w = time_decay_weight(days, lambda_)
        weighted_sum += entry.get("delta", 0) * w
        total_weight += w

    adjusted_delta = weighted_sum / total_weight if total_weight > 0 else 0.0

    if n < 5:
        return {
            "action": "record_only",
            "adjustment": round(adjusted_delta, 1),
            "message": f"记录偏差 {adjusted_delta:+.1f}，样本数({n})不足，需积累更多样本后自动校准",
            "sample_count": n,
            "min_samples_needed": 5,
        }
    elif n < 20:
        return {
            "action": "warn",
            "adjustment": round(adjusted_delta, 1),
            "message": f"样本{n}条，平均偏差 {adjusted_delta:+.1f}，建议人工复核",
            "sample_count": n,
            "min_samples_needed": 20,
        }
    else:
        return {
            "action": "update",
            "adjustment": round(adjusted_delta, 1),
            "message": f"校准已更新（基于{n}条反馈）",
            "sample_count": n,
            "min_samples_needed": 20,
        }


def update_calibration_file(calibration_path, adjustment, sample_count):
    """Update or create calibration YAML file with new values."""
    # Load existing or create default
    if Path(calibration_path).exists():
        with open(calibration_path, encoding="utf-8") as f:
            cal = yaml.safe_load(f) or {}
    else:
        cal = {
            "source": "auto-generated from feedback",
            "tier": "unknown",
            "adjustment": {"type": "additive", "value": 0, "confidence": 0},
            "samples": 0,
        }

    # Update
    old_value = cal.get("adjustment", {}).get("value", 0)
    new_value = adjustment

    # Degradation check
    if abs(new_value) > abs(old_value) * 1.5 and old_value != 0:
        print(f"WARNING: New calibration ({new_value:+}) is 1.5x larger than old ({old_value:+}).")
        print("Auto-rollback recommended. Run with --force to override.")

    cal["adjustment"]["value"] = new_value
    cal["samples"] = sample_count
    cal["last_updated"] = date.today().isoformat()
    cal["confidence"] = min(0.9, sample_count / 50)

    with open(calibration_path, "w", encoding="utf-8") as f:
        yaml.dump(cal, f, allow_unicode=True, default_flow_style=False)

    print(f"Calibration updated: {calibration_path}")
    print(f"  Adjustment: {new_value:+}")
    print(f"  Samples: {sample_count}")
    print(f"  Confidence: {cal['confidence']:.0%}")


def main():
    parser = argparse.ArgumentParser(description="Calibration file management")
    parser.add_argument("--feedback-log", help="Path to feedback_log.yaml")
    parser.add_argument("--calibration-file", help="Path to calibration YAML to update")
    parser.add_argument("--lambda", dest="lambda_", type=float, default=0.01,
                        help="Time decay factor (default: 0.01)")
    parser.add_argument("--csv", help="CSV with paper_id,tier,human_score,human_grade")
    parser.add_argument("--report-dir", help="Directory containing engine report.json files")
    parser.add_argument("--force", action="store_true", help="Bypass degradation check")
    args = parser.parse_args()

    # Mode 1: feedback log → calibration update
    if args.feedback_log and args.calibration_file:
        with open(args.feedback_log, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        entries = data.get("entries", [])
        if not entries:
            print("No feedback entries found.")
            return

        result = compute_calibration(entries, args.lambda_)
        print(result["message"])

        if result["action"] == "update" or args.force:
            update_calibration_file(
                args.calibration_file,
                result["adjustment"],
                result["sample_count"],
            )
        else:
            print(f"No update applied (action={result['action']}). "
                  f"Need {result.get('min_samples_needed', 20)} samples for auto-update.")

    # Mode 2: CSV import (convenience)
    elif args.csv and args.report_dir and args.feedback_log:
        entries = []
        with open(args.csv, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                report_path = Path(args.report_dir) / row["paper_id"] / "report.json"
                if not report_path.exists():
                    print(f"WARNING: Report not found: {report_path}")
                    continue
                with open(report_path, encoding="utf-8") as rf:
                    report = json.load(rf)
                entry = {
                    "paper": row["paper_id"],
                    "tier": row.get("tier", report.get("tier", "unknown")),
                    "engine_score": report.get("total_score", 0),
                    "engine_grade": report.get("grade", ""),
                    "human_score": int(row.get("human_score", 0)),
                    "human_grade": row.get("human_grade", ""),
                    "delta": report.get("total_score", 0) - int(row.get("human_score", 0)),
                    "timestamp": date.today().isoformat(),
                }
                entries.append(entry)

        existing = []
        if Path(args.feedback_log).exists():
            with open(args.feedback_log, encoding="utf-8") as f:
                existing_data = yaml.safe_load(f) or {}
                existing = existing_data.get("entries", [])

        existing.extend(entries)
        with open(args.feedback_log, "w", encoding="utf-8") as f:
            yaml.dump({"entries": existing}, f, allow_unicode=True, default_flow_style=False)

        print(f"Imported {len(entries)} entries into {args.feedback_log}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
