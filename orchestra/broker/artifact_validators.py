"""Broker 内置产物语义校验器，独立于生成产物的模型。"""
from __future__ import annotations

import json
import hashlib
import re
from pathlib import Path


SCORE_LIMITS = {
    "topic": (0, 40),
    "method": (0, 25),
    "applied": (0, 20),
    "archival": (0, 15),
    "novelty": (0, 10),
}
TOTAL_FIELDS = ("topic", "method", "applied", "archival")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _load_json(root: Path, name: str, errors: list[str]):
    path = root / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"{name}: cannot load JSON: {exc}")
        return None


def _string_list(value) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _validate_paper(item, index: int, errors: list[str]) -> str | None:
    prefix = f"papers_all.json[{index}]"
    if not isinstance(item, dict):
        errors.append(f"{prefix}: must be an object")
        return None
    for field in ("title", "arxiv_id", "url", "submitted_at", "abstract"):
        if not isinstance(item.get(field), str) or not item[field].strip():
            errors.append(f"{prefix}.{field}: must be a non-empty string")
    for field in ("categories", "authors"):
        if not _string_list(item.get(field)):
            errors.append(f"{prefix}.{field}: must be a string array")
    arxiv_id = item.get("arxiv_id")
    return arxiv_id if isinstance(arxiv_id, str) else None


def validate_fetch(root: Path) -> list[str]:
    errors: list[str] = []
    papers = _load_json(root, "papers_all.json", errors)
    summary = _load_json(root, "fetch_summary.json", errors)
    if not isinstance(papers, list) or not papers:
        errors.append("papers_all.json: must be a non-empty array")
        papers = []
    ids = []
    for index, item in enumerate(papers):
        arxiv_id = _validate_paper(item, index, errors)
        if arxiv_id:
            ids.append(arxiv_id)
    if len(ids) != len(set(ids)):
        errors.append("papers_all.json: duplicate arxiv_id")
    if not isinstance(summary, dict):
        errors.append("fetch_summary.json: must be an object")
    else:
        if summary.get("deduplicated_count") != len(papers):
            errors.append("fetch_summary.json: deduplicated_count mismatch")
        counts = summary.get("source_counts")
        if not isinstance(counts, dict) or not all(
            isinstance(counts.get(key), int) and counts[key] >= 0
            for key in ("cs.CL", "cs.LG")
        ):
            errors.append("fetch_summary.json: invalid source_counts")
    return errors


def _validate_scored_items(items, label: str, errors: list[str]) -> list[str]:
    if not isinstance(items, list):
        errors.append(f"{label}: must be an array")
        return []
    ids = []
    for index, item in enumerate(items):
        prefix = f"{label}[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix}: must be an object")
            continue
        for field in ("title", "arxiv_id", "url", "abstract", "rationale"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                errors.append(f"{prefix}.{field}: must be a non-empty string")
        if not _string_list(item.get("categories")):
            errors.append(f"{prefix}.categories: must be a string array")
        for field in ("evidence", "counter_evidence", "unknowns"):
            if not _string_list(item.get(field)):
                errors.append(f"{prefix}.{field}: must be a string array")
        quality_signals = item.get("quality_signals")
        if not isinstance(quality_signals, dict) or any(
            quality_signals.get(field) not in ("yes", "no", "unknown")
            for field in ("peer_reviewed", "code_available", "dataset_available")
        ):
            errors.append(f"{prefix}.quality_signals: invalid")
        scores = item.get("scores")
        if not isinstance(scores, dict):
            errors.append(f"{prefix}.scores: must be an object")
            continue
        for field, (low, high) in SCORE_LIMITS.items():
            value = scores.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
                errors.append(f"{prefix}.scores.{field}: out of range")
        if all(isinstance(scores.get(field), (int, float)) and not isinstance(scores.get(field), bool)
               for field in TOTAL_FIELDS):
            if item.get("total") != sum(scores[field] for field in TOTAL_FIELDS):
                errors.append(f"{prefix}.total: does not match score sum")
        confidence = item.get("confidence")
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            errors.append(f"{prefix}.confidence: must be within 0..1")
        if isinstance(item.get("arxiv_id"), str):
            ids.append(item["arxiv_id"])
    if len(ids) != len(set(ids)):
        errors.append(f"{label}: duplicate arxiv_id")
    return ids


def _attempt_number(path: Path) -> int:
    try:
        return int(path.name.split("-", 1)[1])
    except (IndexError, ValueError):
        return -1


def _fetch_root_for_rank(root: Path) -> Path | None:
    rank_task = root.parent
    match = re.fullmatch(r"T-(\d+)-nightly-radar-20-rank", rank_task.name)
    if match is None:
        return None
    return rank_task.parent / f"T-{match.group(1)}-nightly-radar-10-fetch"


def _latest_valid_fetch(root: Path, errors: list[str]) -> tuple[list, bytes] | None:
    for attempt in sorted(root.glob("attempt-*"), key=_attempt_number, reverse=True):
        try:
            state = json.loads((attempt / "state.json").read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if state.get("status") != "done":
            continue
        fetch_errors = validate_fetch(attempt)
        if fetch_errors:
            continue
        raw = (attempt / "papers_all.json").read_bytes()
        return json.loads(raw.decode("utf-8")), raw
    errors.append(f"upstream fetch: no validated successful attempt under {root}")
    return None


def validate_rank(root: Path, fetch_root: Path | None = None) -> list[str]:
    errors: list[str] = []
    papers = _load_json(root, "scored_papers.json", errors)
    summary = _load_json(root, "ranking_summary.json", errors)
    ids = _validate_scored_items(papers, "scored_papers.json", errors)
    if not ids:
        errors.append("scored_papers.json: must contain at least one valid paper")
    if not isinstance(summary, dict):
        errors.append("ranking_summary.json: must be an object")
    elif isinstance(papers, list):
        eligible = sum(
            isinstance(item, dict)
            and isinstance(item.get("scores"), dict)
            and isinstance(item["scores"].get("topic"), (int, float))
            and not isinstance(item["scores"].get("topic"), bool)
            and item["scores"]["topic"] >= 10
            for item in papers
        )
        if summary.get("candidate_count") != len(papers):
            errors.append("ranking_summary.json: candidate_count mismatch")
        if summary.get("eligible_count") != eligible:
            errors.append("ranking_summary.json: eligible_count mismatch")
    fetch_root = fetch_root or _fetch_root_for_rank(root)
    if fetch_root is None:
        errors.append("upstream fetch: cannot derive fetch result root from rank path")
        return errors
    upstream = _latest_valid_fetch(fetch_root, errors)
    if upstream is None:
        return errors
    fetch_papers, fetch_raw = upstream
    fetch_ids = [
        item.get("arxiv_id") for item in fetch_papers if isinstance(item, dict)
    ]
    if len(ids) != len(fetch_ids):
        errors.append("scored_papers.json: count does not match upstream fetch")
    if set(ids) != set(fetch_ids):
        errors.append("scored_papers.json: arxiv_id set does not match upstream fetch")
    fetch_by_id = {
        item["arxiv_id"]: item
        for item in fetch_papers
        if isinstance(item, dict) and isinstance(item.get("arxiv_id"), str)
    }
    for index, item in enumerate(papers if isinstance(papers, list) else []):
        if not isinstance(item, dict):
            continue
        arxiv_id = item.get("arxiv_id")
        upstream_item = fetch_by_id.get(arxiv_id)
        if upstream_item is None:
            continue
        for field in ("title", "url", "categories", "abstract"):
            if item.get(field) != upstream_item.get(field):
                errors.append(
                    f"scored_papers.json[{index}].{field}: "
                    f"does not exactly match upstream fetch for arxiv_id {arxiv_id}"
                )
    if isinstance(summary, dict):
        if summary.get("input_count") != len(fetch_papers):
            errors.append("ranking_summary.json: input_count mismatch")
        input_sha = summary.get("input_sha256")
        if not isinstance(input_sha, str) or not _SHA256_RE.fullmatch(input_sha):
            errors.append("ranking_summary.json: invalid input_sha256")
        elif input_sha != hashlib.sha256(fetch_raw).hexdigest():
            errors.append("ranking_summary.json: input_sha256 mismatch")
    return errors


def validate_render(root: Path) -> list[str]:
    errors: list[str] = []
    digest = _load_json(root, "digest.json", errors)
    top = _load_json(root, "top5.json", errors)
    validation = _load_json(root, "validation.json", errors)
    digest_ids = _validate_scored_items(digest, "digest.json", errors)
    top_ids = _validate_scored_items(top, "top5.json", errors)
    if len(top_ids) > 5:
        errors.append("top5.json: contains more than five papers")
    if not set(top_ids).issubset(set(digest_ids)):
        errors.append("top5.json: contains paper outside digest.json")
    if isinstance(top, list):
        for index, item in enumerate(top):
            if isinstance(item, dict) and item.get("selection_reason") not in (
                "overall", "novelty", "diversity"
            ):
                errors.append(f"top5.json[{index}].selection_reason: invalid")
    if not isinstance(validation, dict):
        errors.append("validation.json: must be an object")
    else:
        if validation.get("status") != "passed":
            errors.append("validation.json: status is not passed")
        if validation.get("algorithm_version") != "radar-render-v1":
            errors.append("validation.json: unexpected algorithm_version")
        if not _SHA256_RE.fullmatch(str(validation.get("input_sha256", ""))):
            errors.append("validation.json: invalid input_sha256")
        if validation.get("eligible_count") != len(digest_ids):
            errors.append("validation.json: eligible_count mismatch")
        if validation.get("selected_count") != len(top_ids):
            errors.append("validation.json: selected_count mismatch")
        checks = validation.get("checks")
        if not isinstance(checks, dict) or not checks or not all(value is True for value in checks.values()):
            errors.append("validation.json: checks must all pass")
    digest_text = root / "digest.txt"
    if not digest_text.is_file() or not digest_text.read_text(encoding="utf-8").strip():
        errors.append("digest.txt: must be non-empty")
    return errors


VALIDATORS = {
    "radar-fetch": validate_fetch,
    "radar-rank": validate_rank,
    "radar-render": validate_render,
}


def validate_artifacts(name: str, root: Path) -> list[str]:
    validator = VALIDATORS.get(name)
    if validator is None:
        return [f"unknown artifact validator: {name}"]
    try:
        return validator(root)
    except Exception as exc:
        return [f"artifact validator {name} crashed: {exc}"]
