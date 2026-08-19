#!/usr/bin/env python3
"""run_card.py — experiment card command extractor and ingest glue.

Subcommands:
  commands <card.md> [--arm ID]
      Extract the ``## Commands`` section of an experiment card: shared blocks
      plus one arm's blocks, or (without --arm) list the arm ids.
  ingest <metrics.json> --card <card.md> [options]
      Guard against wrong-card ingestion (exp_id must match the card id),
      validate the card, then delegate to the academic-research-engine scripts
      (validate_experiment_card.py / ingest_run.py) via subprocess.

Stdlib only. The engine scripts live under the Skill path declared and digest-
locked by config/skills.json. ``--engine-dir`` may override the location for a
controlled migration/test but cannot bypass the digest gate. Scripts are invoked
with [sys.executable, script, ...] and are never modified.

Card ``## Commands`` convention
------------------------------
Under the ``## Commands`` heading (up to the next ``## `` heading), each fenced
block (``` or ```bash) holds one shell command per line. A block whose
immediately preceding non-empty line is ``# arm: <id>`` belongs to arm <id>;
unmarked blocks are shared by every arm and are emitted first.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import check_skills

DEFAULT_SKILLS_MANIFEST = Path(__file__).resolve().parents[1] / "config" / "skills.json"
INGEST_SKILL_ID = "academic-research-engine"

_ARM_ANNOTATION_RE = re.compile(r"^\s*#\s*arm:\s*(\S+)\s*$")


def _is_fence(line: str) -> bool:
    return line.strip().startswith("```")


def _commands_section_lines(text: str) -> list[str]:
    """Lines between the ``## Commands`` heading and the next ``## `` heading."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == "## Commands":
            section: list[str] = []
            for line in lines[i + 1:]:
                if line.startswith("## "):
                    break
                section.append(line)
            return section
    return []


def _collect_blocks(section: list[str]) -> list[tuple[str | None, str]]:
    """Scan the Commands section for fenced blocks with optional # arm: annotations.

    Returns (arm_id, content) pairs in order of appearance; arm_id is None for
    shared blocks. An unclosed fence is closed by end of section.
    """
    blocks: list[tuple[str | None, str]] = []
    current_arm: str | None = None
    current_lines: list[str] | None = None
    prev_nonblank: str | None = None
    for line in section:
        if current_lines is None:
            if _is_fence(line):
                arm_id = None
                if prev_nonblank:
                    m = _ARM_ANNOTATION_RE.match(prev_nonblank)
                    if m:
                        arm_id = m.group(1)
                current_arm, current_lines = arm_id, []
            elif line.strip():
                prev_nonblank = line
        else:
            if _is_fence(line):
                blocks.append((current_arm, "\n".join(current_lines)))
                current_arm, current_lines = None, None
                prev_nonblank = line
            else:
                current_lines.append(line)
    if current_lines is not None:
        blocks.append((current_arm, "\n".join(current_lines)))
    return blocks


def _join_blocks(contents: list[str]) -> str:
    non_empty = [content.strip() for content in contents if content.strip()]
    return "\n\n".join(non_empty)


def extract_commands(text: str, arm: str | None = None) -> str:
    """Extract the executable commands of an experiment card.

    - ``arm=None``: if the card has arm blocks, return the arm ids (one per
      line, deduped, in order of first appearance); otherwise return the
      shared blocks' content.
    - ``arm=<id>``: return the shared blocks plus that arm's blocks, in order
      of appearance, blocks separated by a blank line. Raises ValueError for
      an unknown arm.
    - No ``## Commands`` section: return "".
    """
    blocks = _collect_blocks(_commands_section_lines(text))
    arms: list[str] = []
    for arm_id, _ in blocks:
        if arm_id is not None and arm_id not in arms:
            arms.append(arm_id)
    if arm is None:
        if arms:
            return "\n".join(arms)
        return _join_blocks([content for _, content in blocks])
    if arm not in arms:
        raise ValueError(f"unknown arm: {arm}")
    selected = [
        content for arm_id, content in blocks if arm_id is None or arm_id == arm
    ]
    return _join_blocks(selected)


def _strip_inline_comment(value: str) -> str:
    """Remove a YAML-style inline comment (``#`` outside quotes) from a value."""
    in_single = in_double = False
    out: list[str] = []
    for ch in value:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            break
        out.append(ch)
    return "".join(out).strip()


def parse_card_id(text: str) -> str:
    """Return the ``id`` value from the card's YAML front-matter.

    The front-matter is the text between the first two ``---`` lines. Inline
    comments (``#`` outside quotes) are stripped. Raises ValueError when the
    front-matter or the ``id`` key is missing/empty.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("card has no YAML front-matter")
    second = next(
        (i for i in range(1, len(lines)) if lines[i].strip() == "---"), None
    )
    if second is None:
        raise ValueError("card front-matter is not closed")
    for raw in lines[1:second]:
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        if key.strip() == "id":
            parsed = _strip_inline_comment(value)
            if not parsed:
                raise ValueError("card front-matter id is empty")
            return parsed
    raise ValueError("card front-matter has no id key")


def resolve_ingest_engine(
    manifest_path: Path, engine_dir: str | Path | None = None
) -> Path:
    """从 skills.json 解析并校验 ingest Skill；任何未锁定或漂移都硬失败。"""
    try:
        data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        check_skills.validate_manifest(data)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"invalid skills manifest: {exc}") from exc

    matches = [spec for spec in data["skills"] if spec["id"] == INGEST_SKILL_ID]
    if len(matches) != 1:
        raise ValueError(
            f"skills manifest must contain exactly one {INGEST_SKILL_ID}"
        )
    spec = dict(matches[0])
    if not spec["required"]:
        raise ValueError(f"{INGEST_SKILL_ID} must be required for ingest")
    if "orchestra/scripts/run_card.py ingest" not in spec["used_by"]:
        raise ValueError(f"{INGEST_SKILL_ID} used_by does not declare run_card ingest")
    if engine_dir is not None:
        spec["path"] = str(Path(engine_dir))
    inspected = check_skills.inspect_skill(spec)
    if inspected["status"] != "ok":
        raise ValueError(
            f"{INGEST_SKILL_ID} contract gate failed: {inspected['status']}"
        )
    return Path(spec["path"]).expanduser()


def do_commands(path: Path, arm: str | None = None) -> int:
    """CLI ``commands`` subcommand: print extracted commands; exit 2 on error."""
    try:
        text = Path(path).read_text(encoding="utf-8")
        out = extract_commands(text, arm)
    except ValueError as e:
        print(f"HARD: {e}")
        return 2
    except OSError as e:
        print(f"HARD: cannot read {path}: {e}")
        return 2
    print(out)
    return 0


def do_ingest(args: argparse.Namespace) -> int:
    """CLI ``ingest`` subcommand: exp_id guard, engine validate, engine ingest."""
    try:
        card_text = Path(args.card).read_text(encoding="utf-8")
    except OSError as e:
        print(f"HARD: cannot read card {args.card}: {e}")
        return 2
    try:
        card_id = parse_card_id(card_text)
    except ValueError as e:
        print(f"HARD: {e}")
        return 2
    try:
        with Path(args.metrics).open(encoding="utf-8") as f:
            metrics_data = json.load(f)
    except (OSError, ValueError) as e:
        print(f"HARD: cannot read metrics {args.metrics}: {e}")
        return 2

    exp_id = metrics_data.get("exp_id")
    if exp_id != card_id:
        print(f"HARD: exp_id mismatch: metrics={exp_id} card={card_id}")
        return 2

    manifest_path = Path(
        getattr(args, "skills_manifest", None) or DEFAULT_SKILLS_MANIFEST
    )
    try:
        engine_dir = resolve_ingest_engine(
            manifest_path, getattr(args, "engine_dir", None)
        )
    except (ValueError, OSError) as exc:
        # OSError 来自 inspect_skill → _skill_digest 的 read_bytes（contract 文件
        # 被独占锁定/不可读等），同样按 HARD 语义结构化输出，不泄漏 traceback（M-9）
        print(f"HARD: {exc}")
        return 2
    scripts_dir = engine_dir / "scripts"

    validate_script = scripts_dir / "validate_experiment_card.py"
    rc = subprocess.run(
        [sys.executable, str(validate_script), str(Path(args.card))]
    ).returncode
    if rc != 0:
        print("HARD: card validation failed")
        return 2

    ingest_script = scripts_dir / "ingest_run.py"
    cmd = [
        sys.executable,
        str(ingest_script),
        str(Path(args.metrics)),
        "--research-root",
        str(Path(args.research_root)),
    ]
    if getattr(args, "paper_dir", None):
        cmd += ["--paper-dir", str(Path(args.paper_dir))]
    if getattr(args, "open_neg_on_fail", False):
        cmd += ["--open-neg-on-fail"]
    rc = subprocess.run(cmd).returncode
    if rc != 0:
        return rc

    run_id = metrics_data.get("run_id")
    print(f"OK: ingested {run_id} → {exp_id}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Thin argparse shell around do_commands / do_ingest."""
    parser = argparse.ArgumentParser(
        prog="run_card.py",
        description="Experiment card command extractor and ingest glue.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    cmd_p = sub.add_parser(
        "commands", help="extract the ## Commands section of a card"
    )
    cmd_p.add_argument("card", type=Path, help="path to experiments/EXP-*/card.md")
    cmd_p.add_argument(
        "--arm",
        default=None,
        help="print shared blocks + this arm's blocks (default: list arm ids)",
    )

    ing_p = sub.add_parser(
        "ingest", help="validate card vs run metrics and ingest the run"
    )
    ing_p.add_argument("metrics", type=Path, help="path to the run's metrics.json")
    ing_p.add_argument(
        "--card", required=True, type=Path, help="path to experiments/EXP-*/card.md"
    )
    ing_p.add_argument(
        "--research-root", default=".research", help="research root (default: .research)"
    )
    ing_p.add_argument(
        "--engine-dir",
        default=None,
        help="override the Skill path for testing/migration; manifest digest still applies",
    )
    ing_p.add_argument(
        "--skills-manifest",
        default=str(DEFAULT_SKILLS_MANIFEST),
        help="strict external Skill manifest and digest lock",
    )
    ing_p.add_argument(
        "--paper-dir", default=None, help="if set, update .paper/issues.csv and map"
    )
    ing_p.add_argument(
        "--open-neg-on-fail",
        action="store_true",
        help="open a NEG entry when the run fails criteria",
    )

    args = parser.parse_args(argv)
    if args.command == "commands":
        return do_commands(args.card, args.arm)
    return do_ingest(args)


if __name__ == "__main__":
    raise SystemExit(main())
