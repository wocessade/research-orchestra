from __future__ import annotations

import re
from enum import StrEnum
from typing import Self

from pathlib import PurePosixPath

from pydantic import BaseModel, ConfigDict, Field, model_validator

from bogda.contracts.models import JobRequest, ResourceClass

PI_SERVICE_POOL = "pi-service"
RESEARCH_POOL = "dorm-x86"
INBOX_ROOT = "/mnt/nas/.bogda/inbox"
RESEARCH_TASK_TYPES = frozenset(
    {"paper_reproduce", "paper_reproduce_slice", "research"}
)
_WINDOWS_PATH = re.compile(r"^[A-Za-z]:[\\/]|^\\\\")
_GIT_COMMIT = re.compile(r"^[0-9a-f]{7,40}$")
_INBOX_TOKEN = re.compile(r"^[A-Za-z0-9._-]{1,180}$")


class AttachmentKind(StrEnum):
    GIT = "git"
    STAGED = "staged"
    INBOX = "inbox"


class AdmitStatus(StrEnum):
    ADMITTED = "admitted"
    BLOCKED_MISSING_INPUTS = "blocked_missing_inputs"
    POOL_FORBIDDEN = "pool_forbidden"


class AttachmentRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: AttachmentKind
    url: str | None = None
    commit: str | None = None
    path: str | None = None

    @model_validator(mode="after")
    def validate_kind_fields(self) -> Self:
        if self.path is not None and _WINDOWS_PATH.search(self.path):
            raise ValueError("attachment path must be runner-resolvable, not a fill-in Windows path")
        if self.kind is AttachmentKind.GIT:
            if not self.url:
                raise ValueError("git attachments require url")
        elif self.kind is AttachmentKind.STAGED:
            if not self.path:
                raise ValueError("staged attachments require path")
        elif self.kind is AttachmentKind.INBOX:
            if not self.path:
                raise ValueError("inbox attachments require path")
            _assert_inbox_path(self.path)
        return self


class RunnerPacket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    work_pool: str = Field(min_length=1)
    attachments: tuple[AttachmentRef, ...]
    runbook: str = Field(min_length=1)
    commands: tuple[str, ...] = Field(min_length=1)
    success_criteria: tuple[str, ...] = Field(min_length=1)
    failure_criteria: tuple[str, ...] = Field(min_length=1)
    network_allowlist: tuple[str, ...] = ()
    forbidden: tuple[str, ...] = ()
    gpu_class: str | None = None
    max_attempts: int = Field(default=1, ge=1)


class AdmitDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: AdmitStatus
    reasons: tuple[str, ...] = ()


def _assert_inbox_path(path: str) -> None:
    posix = PurePosixPath(path)
    try:
        relative = posix.relative_to(INBOX_ROOT)
    except ValueError as error:
        raise ValueError("inbox path must be under /mnt/nas/.bogda/inbox") from error
    if len(relative.parts) != 2:
        raise ValueError("inbox path must be /mnt/nas/.bogda/inbox/<run_id>/<file>")
    run_id, name = relative.parts
    if run_id in {".", ".."} or name in {".", ".."}:
        raise ValueError("inbox path must not contain parent segments")
    if not _INBOX_TOKEN.fullmatch(run_id) or not _INBOX_TOKEN.fullmatch(name):
        raise ValueError("inbox path tokens must be run-id safe")
    if ".." in run_id or ".." in name:
        raise ValueError("inbox path must not contain parent segments")


def _is_research(request: JobRequest) -> bool:
    return (
        request.task_type in RESEARCH_TASK_TYPES
        or request.resource_class is ResourceClass.GPU
    )


def admit_runner_packet(request: JobRequest, packet: RunnerPacket) -> AdmitDecision:
    if packet.work_pool == PI_SERVICE_POOL and _is_research(request):
        return AdmitDecision(
            status=AdmitStatus.POOL_FORBIDDEN,
            reasons=("research jobs must not use pi-service",),
        )
    reasons: list[str] = []
    if _is_research(request) and not packet.attachments:
        reasons.append("research jobs require at least one attachment")
    for index, attachment in enumerate(packet.attachments):
        if attachment.kind is AttachmentKind.GIT:
            if not attachment.commit:
                reasons.append(f"attachments[{index}] git commit is required")
            elif not _GIT_COMMIT.fullmatch(attachment.commit):
                reasons.append(f"attachments[{index}] git commit is not a hex sha")
    if reasons:
        return AdmitDecision(
            status=AdmitStatus.BLOCKED_MISSING_INPUTS,
            reasons=tuple(reasons),
        )
    return AdmitDecision(status=AdmitStatus.ADMITTED, reasons=())
