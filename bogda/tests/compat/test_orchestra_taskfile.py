import ast
import inspect
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from bogda.compat import parse_orchestra_task, to_job_request
from bogda.contracts import (
    AutonomyMode,
    ExecutorKind,
    ModelTier,
    ResourceClass,
    TaskIntent,
)


CARD = """# T-20260828-audit
executor: dsh
net: required
result: T-20260828-audit
timeout: 900
model: pro
mode: audit
detail: deep
depends_on: T-20260827-source
required_outputs: review.json, notes.txt
json_outputs: review.json
validation_output: review.json
validator: radar-render
---
review the evidence
"""


def _budget(tier: str = "pro") -> dict[str, str | None]:
    return {
        "expected_cost": "1",
        "authorized_ceiling": "2",
        "minimum_remaining": "10",
        "requested_tier": tier,
        "fallback_tier": "flash" if tier == "pro" else None,
        "budget_source": "project",
        "pricing_version": "deepseek-cn-2026-08-28",
    }


def _write_card(
    tmp_path: Path, text: str = CARD, name: str = "T-20260828-audit.md"
) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _request(path: Path, *, budget: dict | None = None):
    return to_job_request(
        parse_orchestra_task(path),
        project_id="bogda-main",
        autonomy_mode=AutonomyMode.SUPERVISED,
        resource_class=ResourceClass.CPU,
        budget=budget,
    )


def test_legacy_card_maps_mode_and_model_without_importing_orchestra(
    tmp_path: Path,
) -> None:
    path = _write_card(tmp_path)
    request = _request(path, budget=_budget())

    assert request.intent is TaskIntent.AUDIT
    assert request.model_tier is ModelTier.PRO
    assert request.executor is ExecutorKind.DSH
    assert request.parameters["legacy_orchestra"] == {
        "net": "required",
        "result_dir": "T-20260828-audit",
        "timeout": 900,
        "body": "review the evidence",
        "depends_on": ["T-20260827-source"],
        "detail": "deep",
        "json_outputs": ["review.json"],
        "validation_output": "review.json",
        "validator": "radar-render",
    }
    assert request.expected_artifacts[0].path == "review.json"
    assert request.expected_artifacts[1].path == "notes.txt"


@pytest.mark.parametrize("intent", ["execute", "explore", "decide", "audit", "brief"])
@pytest.mark.parametrize("tier", ["flash", "pro"])
def test_all_legacy_modes_and_tiers_convert(
    intent: str, tier: str, tmp_path: Path
) -> None:
    text = CARD.replace("mode: audit", f"mode: {intent}").replace(
        "model: pro", f"model: {tier}"
    )
    path = _write_card(tmp_path, text, f"T-{intent}-{tier}.md")

    request = _request(path, budget=_budget(tier))

    assert request.intent is TaskIntent(intent)
    assert request.model_tier is ModelTier(tier)


def test_omitted_legacy_model_converts_to_auto(tmp_path: Path) -> None:
    path = _write_card(tmp_path, CARD.replace("model: pro\n", ""))

    request = _request(path, budget=_budget("auto"))

    assert request.model_tier is ModelTier.AUTO


def test_shell_executor_conversion_is_supported(tmp_path: Path) -> None:
    text = CARD.replace("executor: dsh", "executor: shell").replace(
        "model: pro\n", ""
    )
    path = _write_card(tmp_path, text)

    request = _request(path)

    assert request.executor is ExecutorKind.SHELL
    assert request.model_tier is ModelTier.AUTO


def test_legacy_import_boundary_does_not_load_orchestra() -> None:
    source_files = [
        Path(inspect.getfile(parse_orchestra_task)),
        Path(inspect.getfile(sys.modules["bogda.compat"])),
    ]
    for source_file in source_files:
        tree = ast.parse(source_file.read_text(encoding="utf-8"))
        imports = [
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        ] + [
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        ]
        assert not any(
            name == "orchestra" or name.startswith("orchestra.") for name in imports
        )

    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import bogda.compat; assert not any(name == 'orchestra' or name.startswith('orchestra.') for name in sys.modules)",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert probe.stderr == ""


def test_legacy_unknown_key_fails_closed(tmp_path: Path) -> None:
    path = _write_card(tmp_path, CARD.replace("mode: audit", "priority: urgent"))
    with pytest.raises(ValueError, match="unknown field"):
        parse_orchestra_task(path)


def test_legacy_duplicate_key_fails_closed(tmp_path: Path) -> None:
    path = _write_card(tmp_path, CARD.replace("mode: audit", "mode: audit\nmode: brief"))
    with pytest.raises(ValueError, match="duplicate field mode"):
        parse_orchestra_task(path)


def test_legacy_missing_required_key_fails_closed(tmp_path: Path) -> None:
    path = _write_card(tmp_path, CARD.replace("net: required\n", ""))
    with pytest.raises(ValueError, match="missing fields"):
        parse_orchestra_task(path)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("executor", "python"),
        ("net", "sometimes"),
        ("model", "auto"),
        ("mode", "unknown"),
        ("detail", "verbose"),
        ("validator", "radar-delete"),
    ],
)
def test_legacy_invalid_enum_values_fail_closed(
    field: str, value: str, tmp_path: Path
) -> None:
    valid_card_values = {
        "executor": "dsh",
        "net": "required",
        "model": "pro",
        "mode": "audit",
        "detail": "deep",
        "validator": "radar-render",
    }
    path = _write_card(
        tmp_path,
        CARD.replace(
            f"{field}: {valid_card_values[field]}", f"{field}: {value}"
        ),
    )

    with pytest.raises(ValueError):
        parse_orchestra_task(path)


@pytest.mark.parametrize(
    "unsafe", [".", "../out", "/tmp/out", "C:\\tmp\\out", "C:/tmp/out"]
)
@pytest.mark.parametrize(
    "field", ["result", "required_outputs", "json_outputs", "validation_output"]
)
def test_unsafe_posix_or_windows_paths_fail_closed(
    unsafe: str, field: str, tmp_path: Path
) -> None:
    text = CARD
    if field == "result":
        text = text.replace("result: T-20260828-audit", f"result: {unsafe}")
    elif field == "required_outputs":
        text = text.replace(
            "required_outputs: review.json, notes.txt", f"required_outputs: {unsafe}"
        )
        text = text.replace("json_outputs: review.json", "json_outputs: ")
        text = text.replace("validation_output: review.json\n", "")
        text = text.replace("validator: radar-render\n", "")
    elif field == "json_outputs":
        text = text.replace("json_outputs: review.json", f"json_outputs: {unsafe}")
    else:
        text = text.replace("validation_output: review.json", f"validation_output: {unsafe}")
    path = _write_card(tmp_path, text)

    with pytest.raises(ValueError, match="safe relative path"):
        parse_orchestra_task(path)


@pytest.mark.parametrize("rooted", ["\\", "\\tmp\\out"])
def test_windows_rooted_paths_fail_closed(rooted: str, tmp_path: Path) -> None:
    path = _write_card(
        tmp_path, CARD.replace("result: T-20260828-audit", f"result: {rooted}")
    )

    with pytest.raises(ValueError, match="safe relative path"):
        parse_orchestra_task(path)


def test_malformed_csv_with_empty_item_fails_closed(tmp_path: Path) -> None:
    path = _write_card(
        tmp_path,
        CARD.replace(
            "depends_on: T-20260827-source", "depends_on: T-20260827-a,,T-20260827-b"
        ),
    )

    with pytest.raises(ValueError, match="malformed CSV"):
        parse_orchestra_task(path)


def test_self_dependency_fails_closed(tmp_path: Path) -> None:
    path = _write_card(
        tmp_path,
        CARD.replace(
            "depends_on: T-20260827-source", "depends_on: T-20260828-audit"
        ),
    )
    with pytest.raises(ValueError, match="self dependency"):
        parse_orchestra_task(path)


def test_duplicate_dependency_fails_closed(tmp_path: Path) -> None:
    path = _write_card(
        tmp_path,
        CARD.replace(
            "depends_on: T-20260827-source",
            "depends_on: T-20260827-source, T-20260827-source",
        ),
    )
    with pytest.raises(ValueError, match="duplicate dependency"):
        parse_orchestra_task(path)


def test_undeclared_json_output_fails_closed(tmp_path: Path) -> None:
    path = _write_card(
        tmp_path,
        CARD.replace("json_outputs: review.json", "json_outputs: missing.json"),
    )
    with pytest.raises(ValueError, match="json_outputs must also be required_outputs"):
        parse_orchestra_task(path)


def test_validation_output_must_be_json_output(tmp_path: Path) -> None:
    path = _write_card(
        tmp_path,
        CARD.replace(
            "validation_output: review.json", "validation_output: notes.txt"
        ),
    )
    with pytest.raises(ValueError, match="validation_output must also be a json_output"):
        parse_orchestra_task(path)


def test_validator_requires_required_outputs(tmp_path: Path) -> None:
    text = CARD.replace("required_outputs: review.json, notes.txt", "required_outputs: ")
    text = text.replace("json_outputs: review.json\n", "").replace("validation_output: review.json\n", "")
    path = _write_card(tmp_path, text)
    with pytest.raises(ValueError, match="validator requires required_outputs"):
        parse_orchestra_task(path)


def test_empty_body_fails_closed(tmp_path: Path) -> None:
    path = _write_card(tmp_path, CARD.split("---\n", 1)[0] + "---\n\n")
    with pytest.raises(ValueError, match="empty body"):
        parse_orchestra_task(path)


@pytest.mark.parametrize("timeout", ["0", "86401", "not-an-integer"])
def test_invalid_timeout_fails_closed(timeout: str, tmp_path: Path) -> None:
    path = _write_card(tmp_path, CARD.replace("timeout: 900", f"timeout: {timeout}"))
    with pytest.raises(ValueError):
        parse_orchestra_task(path)


def test_dsh_requires_budget(tmp_path: Path) -> None:
    path = _write_card(tmp_path)
    with pytest.raises(ValidationError, match="dsh requests require a budget"):
        _request(path, budget=None)


def test_explicit_model_tier_requires_matching_budget(tmp_path: Path) -> None:
    path = _write_card(tmp_path)
    with pytest.raises(
        ValidationError, match="model_tier must match budget.requested_tier"
    ):
        _request(path, budget=_budget("flash"))
