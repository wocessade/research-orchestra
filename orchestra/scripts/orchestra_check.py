#!/usr/bin/env python3
"""Thin Orchestra gate: tests, skill digest, tracked-but-ignored paths.

Does not scan historical reports or SSH the Pi. Unlocked skill digest is
reported (check_skills --strict non-zero) and makes overall ok=false until
the owner locks it.

Usage (from anywhere):
  python orchestra/scripts/orchestra_check.py
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
ORCHESTRA_DIR = SCRIPTS_DIR.parent
REPO_ROOT = ORCHESTRA_DIR.parent
BROKER_DIR = ORCHESTRA_DIR / "broker"
CHECK_SKILLS = SCRIPTS_DIR / "check_skills.py"
_IGNORED_PREFIXES = ("orchestra/results/", "orchestra/logs/")


def _run(cmd: list[str], cwd: Path) -> dict:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {
        "rc": proc.returncode,
        "cmd": cmd,
        "cwd": str(cwd),
    }


def _git_sha(repo: Path) -> str | None:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def tracked_ignored_files(repo: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "ls-files", "-z", "--", "orchestra/results", "orchestra/logs"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        return []
    names = [n.replace("\\", "/") for n in proc.stdout.split("\0") if n]
    return [n for n in names if n.startswith(_IGNORED_PREFIXES)]


def build_report(*, python: str | None = None, repo: Path | None = None) -> dict:
    py = python or sys.executable
    root = repo or REPO_ROOT
    steps = {
        "broker_tests": _run(
            [py, "-m", "unittest", "discover", "-s", "tests", "-q"],
            BROKER_DIR,
        ),
        "scripts_tests": _run(
            [py, "-m", "unittest", "discover", "-s", "tests", "-q"],
            SCRIPTS_DIR,
        ),
        "check_skills": _run(
            [py, str(CHECK_SKILLS), "--strict"],
            SCRIPTS_DIR,
        ),
    }
    ignored = tracked_ignored_files(root)
    steps["tracked_ignored"] = {
        "rc": 1 if ignored else 0,
        "files": ignored,
    }
    ok = all(step["rc"] == 0 for step in steps.values())
    return {
        "ok": ok,
        "git_sha": _git_sha(root),
        "steps": steps,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    report = build_report()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
