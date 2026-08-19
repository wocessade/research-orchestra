#!/usr/bin/env python3
"""确定性校验、选择和渲染夜间文献雷达结果。"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import artifact_validators


ALGORITHM_VERSION = "radar-render-v1"
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "in", "is", "it", "of", "on", "or", "that", "the", "this", "to",
    "using", "via", "we", "with",
}


def _attempt_number(path: Path) -> int:
    try:
        return int(path.name.split("-", 1)[1])
    except (IndexError, ValueError):
        return -1


def latest_successful_attempt(root: Path) -> Path:
    for attempt in sorted(root.glob("attempt-*"), key=_attempt_number, reverse=True):
        try:
            state = json.loads((attempt / "state.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if state.get("status") == "done" and (attempt / "scored_papers.json").is_file():
            return attempt
    raise ValueError(f"no successful ranking attempt under {root}")


def _sort_key(item: dict):
    return (-item["total"], -item["confidence"], item["arxiv_id"])


def _tokens(item: dict) -> set[str]:
    text = f"{item.get('title', '')} {item.get('abstract', '')}".lower()
    return {token for token in _TOKEN_RE.findall(text) if token not in _STOPWORDS}


def _jaccard_distance(left: set[str], right: set[str]) -> float:
    union = left | right
    return 1.0 if not union else 1.0 - len(left & right) / len(union)


def _diversity_score(candidate: dict, selected: list[dict]) -> float:
    if not selected:
        return 1.0
    candidate_tokens = _tokens(candidate)
    return min(
        _jaccard_distance(candidate_tokens, _tokens(item)) for item in selected
    )


def select_papers(scored: list[dict]) -> tuple[list[dict], list[dict]]:
    eligible = sorted(
        (item for item in scored if item["scores"]["topic"] >= 10),
        key=_sort_key,
    )
    selected: list[dict] = []
    selected_ids: set[str] = set()

    def add(item: dict, reason: str, **trace_fields) -> None:
        copy = dict(item)
        copy["selection_reason"] = reason
        copy.update(trace_fields)
        selected.append(copy)
        selected_ids.add(item["arxiv_id"])

    for item in eligible[:3]:
        add(item, "overall")

    remaining = [item for item in eligible if item["arxiv_id"] not in selected_ids]
    if remaining and len(selected) < 5:
        novelty = sorted(
            remaining,
            key=lambda item: (
                -item["scores"]["novelty"], -item["total"],
                -item["confidence"], item["arxiv_id"],
            ),
        )[0]
        add(novelty, "novelty")

    remaining = [item for item in eligible if item["arxiv_id"] not in selected_ids]
    if remaining and len(selected) < 5:
        scored_diversity = [
            (_diversity_score(item, selected), item) for item in remaining
        ]
        distance, diversity = sorted(
            scored_diversity,
            key=lambda pair: (
                -pair[0], -pair[1]["total"], -pair[1]["confidence"],
                pair[1]["arxiv_id"],
            ),
        )[0]
        add(diversity, "diversity", diversity_score=round(distance, 6))
    return eligible, selected


def _write_json(path: Path, value) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def _render_text(date: str, selected: list[dict]) -> str:
    lines = [f"文献日报 {date}", ""]
    if not selected:
        lines.append("今日没有论文通过主题相关性门槛。")
        return "\n".join(lines) + "\n"
    reason_names = {"overall": "综合", "novelty": "探索", "diversity": "多样性"}
    for index, item in enumerate(selected, 1):
        lines.append(
            f"{index}. {item['title']} [{item['arxiv_id']}] "
            f"总分 {item['total']}，{reason_names[item['selection_reason']]}槽位"
        )
        lines.append(item["rationale"].strip())
        if item["evidence"]:
            lines.append("关键证据：" + "；".join(item["evidence"][:3]))
        if item["unknowns"]:
            lines.append("主要不确定性：" + "；".join(item["unknowns"][:2]))
        lines.append(item["url"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render(input_root: Path, output_dir: Path, date: str) -> dict:
    attempt = latest_successful_attempt(input_root)
    input_file = attempt / "scored_papers.json"
    ranking_errors = artifact_validators.validate_rank(attempt)
    if ranking_errors:
        raise ValueError("invalid ranking artifact: " + "; ".join(ranking_errors))
    raw = input_file.read_bytes()
    scored = json.loads(raw.decode("utf-8"))
    eligible, selected = select_papers(scored)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "digest.json", eligible)
    _write_json(output_dir / "top5.json", selected)
    (output_dir / "digest.txt").write_text(
        _render_text(date, selected), encoding="utf-8"
    )
    validation = {
        "date": date,
        "status": "passed",
        "algorithm_version": ALGORITHM_VERSION,
        "input_path": str(input_file),
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "input_count": len(scored),
        "eligible_count": len(eligible),
        "selected_count": len(selected),
        "selection_trace": [
            {
                "arxiv_id": item["arxiv_id"],
                "reason": item["selection_reason"],
                **({"diversity_score": item["diversity_score"]}
                   if "diversity_score" in item else {}),
            }
            for item in selected
        ],
        "checks": {
            "input_semantics": True,
            "unique_ids": True,
            "score_bounds": True,
            "totals_match": True,
            "confidence_bounds": True,
            "stable_tiebreakers": True,
        },
    }
    _write_json(output_dir / "validation.json", validation)
    render_errors = artifact_validators.validate_render(output_dir)
    if render_errors:
        raise ValueError("render validation failed: " + "; ".join(render_errors))
    return validation


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", required=True)
    parser.add_argument("--output-dir", default=".")
    parser.add_argument("--date", required=True)
    args = parser.parse_args(argv)
    result = render(Path(args.input_root), Path(args.output_dir), args.date)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
