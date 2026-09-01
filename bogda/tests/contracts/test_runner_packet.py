from __future__ import annotations

import pytest
from pydantic import ValidationError

from bogda.contracts import (
    AdmitDecision,
    AdmitStatus,
    AttachmentKind,
    AttachmentRef,
    AutonomyMode,
    JobRequest,
    ResourceClass,
    RunnerPacket,
    admit_runner_packet,
)


def _job(*, task_type: str = "paper_reproduce_slice", resource=ResourceClass.GPU) -> JobRequest:
    return JobRequest(
        job_id="jr-packet-1",
        project_id="personal-cs-radar",
        task_type=task_type,
        resource_class=resource,
        autonomy_mode=AutonomyMode.SUPERVISED,
    )


def _packet(**overrides: object) -> RunnerPacket:
    values: dict[str, object] = {
        "work_pool": "dorm-x86",
        "attachments": (
            AttachmentRef(
                kind=AttachmentKind.GIT,
                url="https://github.com/Muennighoff/prefix-sliding",
                commit="0123456789abcdef0123456789abcdef01234567",
            ),
        ),
        "runbook": "clone frozen repo; run training-free eval only",
        "commands": ("python eval_prefix_sliding.py --out $OUTDIR/metrics.json",),
        "success_criteria": ("metrics.json exists with aime avg@64",),
        "failure_criteria": ("empty repo; implement custom attention kernels",),
        "network_allowlist": ("github.com/Muennighoff/prefix-sliding",),
    }
    values.update(overrides)
    return RunnerPacket.model_validate(values)


def test_research_packet_with_frozen_git_is_admitted() -> None:
    decision = admit_runner_packet(_job(), _packet())
    assert decision == AdmitDecision(status=AdmitStatus.ADMITTED, reasons=())


def test_git_attachment_without_commit_is_blocked() -> None:
    packet = _packet(
        attachments=(
            AttachmentRef(
                kind=AttachmentKind.GIT,
                url="https://github.com/Muennighoff/prefix-sliding",
                commit=None,
            ),
        )
    )
    decision = admit_runner_packet(_job(), packet)
    assert decision.status is AdmitStatus.BLOCKED_MISSING_INPUTS
    assert any("commit" in reason for reason in decision.reasons)


def test_windows_drive_path_is_not_a_runner_attachment() -> None:
    with pytest.raises(ValidationError, match="runner-resolvable"):
        AttachmentRef(kind=AttachmentKind.STAGED, path=r"D:\papers\a.pdf")


def test_research_job_on_pi_service_is_forbidden() -> None:
    packet = _packet(work_pool="pi-service")
    decision = admit_runner_packet(_job(), packet)
    assert decision.status is AdmitStatus.POOL_FORBIDDEN
    assert any("pi-service" in reason for reason in decision.reasons)


def test_light_job_may_use_pi_service() -> None:
    job = _job(task_type="brief", resource=ResourceClass.PI)
    packet = _packet(
        work_pool="pi-service",
        attachments=(
            AttachmentRef(
                kind=AttachmentKind.INBOX,
                path="/mnt/nas/.bogda/inbox/jr-packet-1/fail.log",
            ),
        ),
        gpu_class=None,
    )
    decision = admit_runner_packet(job, packet)
    assert decision.status is AdmitStatus.ADMITTED


def test_brief_job_must_use_pi_service() -> None:
    job = _job(task_type="brief", resource=ResourceClass.PI)
    packet = _packet(work_pool="dorm-x86", gpu_class=None)
    decision = admit_runner_packet(job, packet)
    assert decision.status is AdmitStatus.POOL_FORBIDDEN
    assert any("pi-service" in reason for reason in decision.reasons)


def test_inbox_attachment_must_live_under_nas_inbox() -> None:
    with pytest.raises(ValidationError, match="inbox"):
        AttachmentRef(kind=AttachmentKind.INBOX, path="runs/jr-packet-1/fail.log")


def test_inbox_attachment_rejects_parent_segments() -> None:
    with pytest.raises(ValidationError, match="inbox"):
        AttachmentRef(
            kind=AttachmentKind.INBOX,
            path="/mnt/nas/.bogda/inbox/jr-packet-1/../secret.pdf",
        )


def test_packet_rejects_scientific_status_field() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        RunnerPacket.model_validate(
            {
                **_packet().model_dump(mode="json"),
                "scientific_status": "accepted",
            }
        )
