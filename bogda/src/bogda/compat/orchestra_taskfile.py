from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)

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


class _LegacyTaskInput(BaseModel):
    """Validated representation of the legacy header before conversion."""

    model_config = ConfigDict(extra="forbid")

    executor: ExecutorKind
    net: Literal["required", "optional"]
    result: str
    timeout: int = Field(default=3600, ge=1, le=86400)
    model: Literal["flash", "pro"] | None = None
    depends_on: tuple[str, ...] = ()
    mode: TaskIntent = TaskIntent.EXECUTE
    detail: Literal["brief", "standard", "deep"] = "standard"
    required_outputs: tuple[str, ...] = ()
    json_outputs: tuple[str, ...] = ()
    validation_output: str | None = None
    validator: Literal["radar-fetch", "radar-rank", "radar-render"] | None = None

    @model_validator(mode="before")
    @classmethod
    def require_known_header_fields(cls, values: object) -> object:
        if not isinstance(values, dict):
            return values
        unknown = sorted(set(values) - set(cls.model_fields))
        if unknown:
            raise ValueError(f"unknown field {unknown[0]}")
        missing = sorted(
            field for field in ("executor", "net", "result") if field not in values
        )
        if missing:
            raise ValueError(f"missing fields {missing}")
        return values

    @field_validator("depends_on", "required_outputs", "json_outputs", mode="before")
    @classmethod
    def decode_csv(cls, value: object) -> tuple[str, ...]:
        if value is None:
            return ()
        if not isinstance(value, str):
            raise ValueError("malformed CSV")
        if not value.strip():
            return ()
        items = tuple(item.strip() for item in value.split(","))
        if any(not item for item in items):
            raise ValueError("malformed CSV")
        return items

    @field_validator("validation_output", "validator", mode="before")
    @classmethod
    def normalize_empty_optional(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("result", "required_outputs", "json_outputs", "validation_output")
    @classmethod
    def reject_unsafe_paths(cls, value: object, info: ValidationInfo) -> object:
        paths = (
            value
            if isinstance(value, tuple)
            else ()
            if value is None
            else (value,)
        )
        for path in paths:
            if not isinstance(path, str):
                continue
            posix = PurePosixPath(path)
            windows = PureWindowsPath(path)
            if path in ("", ".") or any(
                candidate.is_absolute()
                or candidate.anchor
                or candidate.drive
                or ".." in candidate.parts
                for candidate in (posix, windows)
            ):
                raise ValueError(f"{info.field_name} must be a safe relative path")
        return value

    @model_validator(mode="after")
    def validate_relationships(self, info: ValidationInfo) -> Self:
        slug = (info.context or {}).get("slug")
        if slug in self.depends_on:
            raise ValueError("self dependency")
        if len(self.depends_on) != len(set(self.depends_on)):
            raise ValueError("duplicate dependency")
        if set(self.json_outputs) - set(self.required_outputs):
            raise ValueError("json_outputs must also be required_outputs")
        if (
            self.validation_output is not None
            and self.validation_output not in self.json_outputs
        ):
            raise ValueError("validation_output must also be a json_output")
        if self.validator is not None and not self.required_outputs:
            raise ValueError("validator requires required_outputs")
        return self


def _decode_card(text: str, source: Path) -> tuple[dict[str, str], str]:
    header, separator, body = text.partition("\n---\n")
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
        fields[key] = value
    return fields, body.strip()


def parse_orchestra_task(path: str | Path) -> LegacyOrchestraTask:
    source = Path(path)
    fields, body = _decode_card(source.read_text(encoding="utf-8"), source)
    if not body:
        raise ValueError(f"{source}: empty body")
    try:
        header = _LegacyTaskInput.model_validate(
            fields, context={"slug": source.stem}
        )
    except ValidationError as exc:
        raise ValueError(f"{source}: {exc}") from None
    return LegacyOrchestraTask(
        slug=source.stem,
        executor=header.executor,
        net=header.net,
        result_dir=header.result,
        timeout=header.timeout,
        body=body,
        model=header.model,
        depends_on=header.depends_on,
        mode=header.mode,
        detail=header.detail,
        required_outputs=header.required_outputs,
        json_outputs=header.json_outputs,
        validation_output=header.validation_output,
        validator=header.validator,
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
