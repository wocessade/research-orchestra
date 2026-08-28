from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from bogda.contracts import (
    ArtifactSpec,
    AutonomyMode,
    ExecutorKind,
    JobRequest,
    ModelTier,
    ResourceClass,
    RunBudgetEnvelope,
    TaskIntent,
)


class LegacyOrchestraTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    executor: ExecutorKind
    net: Literal["required", "optional"]
    result_dir: str
    timeout: int = Field(default=3600, ge=1, le=86400)
    body: str = Field(min_length=1)
    model: Literal["flash", "pro"] | None = None
    depends_on: tuple[str, ...] = ()
    mode: TaskIntent = TaskIntent.EXECUTE
    detail: Literal["brief", "standard", "deep"] = "standard"
    required_outputs: tuple[str, ...] = ()
    json_outputs: tuple[str, ...] = ()
    validation_output: str | None = None
    validator: Literal["radar-fetch", "radar-rank", "radar-render"] | None = None


_REQUIRED = {"executor", "net", "result"}
_ALLOWED = {
    "executor",
    "net",
    "result",
    "timeout",
    "model",
    "depends_on",
    "mode",
    "detail",
    "required_outputs",
    "json_outputs",
    "validation_output",
    "validator",
}
_VALID_EXECUTORS = {item.value for item in ExecutorKind}
_VALID_NETS = {"required", "optional"}
_VALID_MODELS = {"flash", "pro"}
_VALID_MODES = {item.value for item in TaskIntent}
_VALID_DETAILS = {"brief", "standard", "deep"}
_VALID_VALIDATORS = {"radar-fetch", "radar-rank", "radar-render"}
_TIMEOUT_MIN = 1
_TIMEOUT_MAX = 86400


def _csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _safe_relative(value: str, field: str, source: Path) -> None:
    candidates = (PurePosixPath(value), PureWindowsPath(value))
    if value in ("", ".") or any(
        candidate.is_absolute() or candidate.drive or ".." in candidate.parts
        for candidate in candidates
    ):
        raise ValueError(f"{source}: {field} must be a safe relative path")


def _validate_enum(
    fields: dict[str, str], field: str, valid: set[str], source: Path
) -> None:
    value = fields.get(field)
    if value is not None and value not in valid:
        choices = "|".join(sorted(valid))
        raise ValueError(f"{source}: {field} must be one of {choices}")


def parse_orchestra_task(path: str | Path) -> LegacyOrchestraTask:
    source = Path(path)
    header, separator, body = source.read_text(encoding="utf-8").partition("\n---\n")
    if not separator:
        raise ValueError(f"{source}: missing task body separator")

    fields: dict[str, str] = {}
    for raw_line in header.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"{source}: invalid header line")
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if key in fields:
            raise ValueError(f"{source}: duplicate field {key}")
        if key not in _ALLOWED:
            raise ValueError(f"{source}: unknown field {key}")
        fields[key] = value

    missing = sorted(_REQUIRED - fields.keys())
    if missing:
        raise ValueError(f"{source}: missing fields {missing}")

    _validate_enum(fields, "executor", _VALID_EXECUTORS, source)
    _validate_enum(fields, "net", _VALID_NETS, source)
    _validate_enum(fields, "model", _VALID_MODELS, source)
    _validate_enum(fields, "mode", _VALID_MODES, source)
    _validate_enum(fields, "detail", _VALID_DETAILS, source)
    _validate_enum(fields, "validator", _VALID_VALIDATORS, source)

    body = body.strip()
    if not body:
        raise ValueError(f"{source}: empty body")

    try:
        timeout = int(fields.get("timeout", "3600"))
    except ValueError:
        raise ValueError(f"{source}: timeout must be an integer") from None
    if not _TIMEOUT_MIN <= timeout <= _TIMEOUT_MAX:
        raise ValueError(
            f"{source}: timeout must be between {_TIMEOUT_MIN} and {_TIMEOUT_MAX} seconds"
        )

    depends_on = _csv(fields.get("depends_on", ""))
    if source.stem in depends_on:
        raise ValueError(f"{source}: self dependency")
    if len(depends_on) != len(set(depends_on)):
        raise ValueError(f"{source}: duplicate dependency")

    required_outputs = _csv(fields.get("required_outputs", ""))
    json_outputs = _csv(fields.get("json_outputs", ""))
    validation_output = fields.get("validation_output") or None
    validator = fields.get("validator") or None

    _safe_relative(fields["result"], "result", source)
    for output in required_outputs:
        _safe_relative(output, "required_outputs", source)
    for output in json_outputs:
        _safe_relative(output, "json_outputs", source)
    if validation_output is not None:
        _safe_relative(validation_output, "validation_output", source)

    if set(json_outputs) - set(required_outputs):
        raise ValueError(f"{source}: json_outputs must also be required_outputs")
    if validation_output is not None and validation_output not in json_outputs:
        raise ValueError(f"{source}: validation_output must also be a json_output")
    if validator is not None and not required_outputs:
        raise ValueError(f"{source}: validator requires required_outputs")

    return LegacyOrchestraTask(
        slug=source.stem,
        executor=fields["executor"],
        net=fields["net"],
        result_dir=fields["result"],
        timeout=timeout,
        body=body,
        model=fields.get("model"),
        depends_on=depends_on,
        mode=fields.get("mode", "execute"),
        detail=fields.get("detail", "standard"),
        required_outputs=required_outputs,
        json_outputs=json_outputs,
        validation_output=validation_output,
        validator=validator,
    )


def to_job_request(
    card: LegacyOrchestraTask,
    *,
    project_id: str,
    autonomy_mode: AutonomyMode,
    resource_class: ResourceClass,
    budget: RunBudgetEnvelope | dict | None,
) -> JobRequest:
    parsed_budget = None if budget is None else RunBudgetEnvelope.model_validate(budget)
    return JobRequest(
        job_id=card.slug,
        project_id=project_id,
        task_type="legacy-orchestra-task",
        resource_class=resource_class,
        autonomy_mode=autonomy_mode,
        intent=card.mode,
        model_tier=ModelTier(card.model or "auto"),
        executor=card.executor,
        budget=parsed_budget,
        parameters={
            "legacy_orchestra": {
                "net": card.net,
                "result_dir": card.result_dir,
                "timeout": card.timeout,
                "body": card.body,
                "depends_on": list(card.depends_on),
                "detail": card.detail,
                "json_outputs": list(card.json_outputs),
                "validation_output": card.validation_output,
                "validator": card.validator,
            }
        },
        expected_artifacts=tuple(
            ArtifactSpec(path=output) for output in card.required_outputs
        ),
    )
