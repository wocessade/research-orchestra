"""检查并锁定 Research Orchestra 的外部 Skill 契约。"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Dict, List


DEFAULT_MANIFEST = Path(__file__).resolve().parents[1] / "config" / "skills.json"
_TOP_LEVEL_FIELDS = {"schema_version", "skills"}
_SKILL_FIELDS = {
    "id", "source", "path", "required", "used_by", "entrypoints",
    "contract_files", "expected_digest", "input_contract", "output_contract",
}
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


def _require_string(value, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _require_string_list(value, field: str, *, non_empty: bool = True) -> List[str]:
    if not isinstance(value, list) or (non_empty and not value):
        suffix = " a non-empty" if non_empty else ""
        raise ValueError(f"{field} must be{suffix} string array")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{field} must contain only non-empty strings")
    if len(value) != len(set(value)):
        raise ValueError(f"{field} must not contain duplicates")
    return value


def _validate_relative_file(value: str, field: str) -> None:
    path = Path(value)
    if (
        path.is_absolute()
        or "\\" in value
        or value != path.as_posix()
        # Windows 跨平台闭环："/abs" 有 root、drive-relative "C:foo" 有 drive，
        # 均非安全相对路径（H-1）。
        or path.drive
        or path.root
        or "." in path.parts
        or ".." in path.parts
    ):
        raise ValueError(f"{field} contains an unsafe relative path: {value}")


def validate_manifest(data: Dict) -> Dict:
    """严格校验 manifest 结构，拒绝未知字段、重复 ID 和可逃逸契约路径。"""
    if not isinstance(data, dict):
        raise ValueError("skills manifest root must be an object")
    unknown = set(data) - _TOP_LEVEL_FIELDS
    missing = _TOP_LEVEL_FIELDS - set(data)
    if unknown or missing:
        raise ValueError(
            f"skills manifest fields mismatch: missing={sorted(missing)} "
            f"unknown={sorted(unknown)}"
        )
    if data["schema_version"] != 1 or isinstance(data["schema_version"], bool):
        raise ValueError("skills manifest schema_version must be 1")
    skills = data["skills"]
    if not isinstance(skills, list) or not skills:
        raise ValueError("skills manifest must contain a non-empty skills array")

    seen_ids = set()
    for index, spec in enumerate(skills):
        prefix = f"skills[{index}]"
        if not isinstance(spec, dict):
            raise ValueError(f"{prefix} must be an object")
        unknown = set(spec) - _SKILL_FIELDS
        missing = _SKILL_FIELDS - set(spec)
        if unknown or missing:
            raise ValueError(
                f"{prefix} fields mismatch: missing={sorted(missing)} "
                f"unknown={sorted(unknown)}"
            )
        skill_id = _require_string(spec["id"], f"{prefix}.id")
        if skill_id in seen_ids:
            raise ValueError(f"duplicate skill id: {skill_id}")
        seen_ids.add(skill_id)
        if spec["source"] != "external":
            raise ValueError(f"{prefix}.source must be external")
        _require_string(spec["path"], f"{prefix}.path")
        if not isinstance(spec["required"], bool):
            raise ValueError(f"{prefix}.required must be boolean")
        _require_string_list(spec["used_by"], f"{prefix}.used_by")
        entrypoints = _require_string_list(
            spec["entrypoints"], f"{prefix}.entrypoints"
        )
        contract_files = _require_string_list(
            spec["contract_files"], f"{prefix}.contract_files"
        )
        for field, values in (
            ("entrypoints", entrypoints),
            ("contract_files", contract_files),
        ):
            for value in values:
                _validate_relative_file(value, f"{prefix}.{field}")
        if not set(entrypoints).issubset(contract_files):
            raise ValueError(f"{prefix}.entrypoints must be included in contract_files")
        expected = spec["expected_digest"]
        if expected is not None and (
            not isinstance(expected, str) or not _DIGEST_RE.fullmatch(expected)
        ):
            raise ValueError(
                f"{prefix}.expected_digest must be null or lowercase SHA-256"
            )
        _require_string(spec["input_contract"], f"{prefix}.input_contract")
        _require_string(spec["output_contract"], f"{prefix}.output_contract")
    return data


def _skill_digest(root: Path, contract_files: List[str]) -> str | None:
    digest = hashlib.sha256()
    for relative in sorted(contract_files):
        path = root / relative
        if not path.is_file():
            return None
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def inspect_skill(spec: Dict) -> Dict:
    root = Path(spec["path"]).expanduser()
    entrypoints = list(spec.get("entrypoints", []))
    contract_files = list(spec.get("contract_files", entrypoints))
    result = {
        "id": spec["id"],
        "required": bool(spec.get("required")),
        "path": str(root),
        "status": "ok",
        "missing_entrypoints": [],
        "actual_digest": None,
        "expected_digest": spec.get("expected_digest"),
    }
    if not root.is_dir():
        result["status"] = "missing"
        return result

    result["missing_entrypoints"] = [
        relative for relative in entrypoints if not (root / relative).is_file()
    ]
    if result["missing_entrypoints"]:
        result["status"] = "incomplete"
        return result

    actual = _skill_digest(root, contract_files)
    if actual is None:
        result["status"] = "incomplete"
        result["missing_entrypoints"] = [
            relative for relative in contract_files if not (root / relative).is_file()
        ]
        return result
    result["actual_digest"] = actual

    expected = spec.get("expected_digest")
    if not expected:
        result["status"] = "unlocked"
    elif expected != actual:
        result["status"] = "drifted"
    return result


def inspect_manifest(data: Dict) -> Dict:
    validate_manifest(data)
    skills = data["skills"]
    results = [inspect_skill(spec) for spec in skills]
    return {
        "schema_version": 1,
        "status": "ok" if all(
            not item["required"] or item["status"] == "ok" for item in results
        ) else "error",
        "skills": results,
    }


def lock_current(data: Dict, report: Dict) -> int:
    by_id = {item["id"]: item for item in report["skills"]}
    updated = 0
    for spec in data["skills"]:
        inspected = by_id[spec["id"]]
        actual = inspected.get("actual_digest")
        if actual and spec.get("expected_digest") != actual:
            spec["expected_digest"] = actual
            updated += 1
    return updated


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check external Skill presence, entrypoints, and contract digests."
    )
    parser.add_argument(
        "--manifest",
        default=str(DEFAULT_MANIFEST),
        help="Path to skills.json.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when a required Skill is missing, incomplete, unlocked, or drifted.",
    )
    parser.add_argument(
        "--lock-current",
        action="store_true",
        help="Write current digests for installed and complete Skills into the manifest.",
    )
    return parser


def _report_invalid(exc: Exception) -> int:
    """结构化错误输出：status=invalid + 退出码 2，不泄漏 traceback。"""
    print(json.dumps({
        "schema_version": 1,
        "status": "invalid",
        "error": str(exc),
        "skills": [],
    }, ensure_ascii=False, indent=2))
    return 2


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    manifest_path = Path(args.manifest)
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        report = inspect_manifest(data)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        return _report_invalid(exc)

    if args.lock_current:
        try:
            updated = lock_current(data, report)
            manifest_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
            return _report_invalid(exc)
        report = inspect_manifest(data)
        report["locks_updated"] = updated

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if args.strict and report["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
