from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Callable, Mapping
from uuid import UUID

from prefect.artifacts import Artifact
from prefect.input import RunInput

from bogda.contracts import AutonomyMode
from bogda.contracts.decisions import (
    CheckpointKind,
    DecisionVerdict,
    ResearchDecision,
    StageStatus,
)

DECISION_TYPE = "bogda.research-decision"


class CheckpointRejected(Exception):
    def __init__(self, decision: ResearchDecision):
        super().__init__(f"{decision.kind} rejected")
        self.decision = decision


class CheckpointInput(RunInput):
    verdict: str
    rationale: str | None = None
    decided_by: str = "human"
    command_version: str | None = None


def decision_key(run_id: str, kind: CheckpointKind) -> str:
    return f"bogda-decision-{kind}-{UUID(run_id)}"


def required_checkpoints(mode: AutonomyMode) -> tuple[CheckpointKind, ...]:
    if mode is AutonomyMode.AUTONOMOUS:
        return ()
    return (
        CheckpointKind.PLAN_APPROVAL,
        CheckpointKind.EXPERIMENT_APPROVAL,
        CheckpointKind.SCIENTIFIC_REVIEW,
    )


def shell_checkpoints(
    mode: AutonomyMode, phase: str
) -> tuple[CheckpointKind, ...]:
    kinds = required_checkpoints(mode)
    wanted = (
        CheckpointKind.EXPERIMENT_APPROVAL
        if phase == "before"
        else CheckpointKind.SCIENTIFIC_REVIEW
    )
    return tuple(kind for kind in kinds if kind is wanted)


def decision_command_version(
    run_id: str,
    kind: CheckpointKind,
    stage: StageStatus,
    verdict: DecisionVerdict | None,
) -> str:
    payload = f"{run_id}:{kind}:{stage}:{verdict or 'pending'}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def save_decision(decision: ResearchDecision) -> None:
    Artifact(
        key=decision_key(decision.run_id, decision.kind),
        type=DECISION_TYPE,
        description=f"Bogda {decision.kind} for {decision.run_id}",
        data=decision.model_dump(mode="json"),
        flow_run_id=UUID(decision.run_id),
    ).create()


def load_decision(run_id: str, kind: CheckpointKind) -> ResearchDecision | None:
    artifact = Artifact.get(key=decision_key(run_id, kind))
    if artifact is None:
        return None
    data = json.loads(artifact.data) if isinstance(artifact.data, str) else artifact.data
    return ResearchDecision.model_validate(data)


def _is_accepted(decision: ResearchDecision | None) -> bool:
    return (
        decision is not None
        and decision.stage is StageStatus.ACCEPTED
        and decision.verdict is DecisionVerdict.APPROVED
    )


def _is_rejected(decision: ResearchDecision | None) -> bool:
    return decision is not None and decision.verdict is DecisionVerdict.REJECTED


def _apply_payload(
    pending: ResearchDecision, payload: Mapping[str, Any]
) -> ResearchDecision:
    version = payload.get("command_version")
    if version and version != pending.command_version:
        return pending
    verdict_raw = payload.get("verdict")
    if verdict_raw not in {DecisionVerdict.APPROVED.value, DecisionVerdict.REJECTED.value}:
        return pending
    verdict = DecisionVerdict(verdict_raw)
    stage = StageStatus.ACCEPTED if verdict is DecisionVerdict.APPROVED else StageStatus.DONE
    return pending.model_copy(
        update={
            "verdict": verdict,
            "stage": stage,
            "rationale": payload.get("rationale"),
            "decided_by": payload.get("decided_by"),
            "decided_at": datetime.now(UTC),
            "command_version": decision_command_version(
                pending.run_id, pending.kind, stage, verdict
            ),
        }
    )


def prefect_receive(pending: ResearchDecision) -> dict[str, Any]:
    from prefect.flow_runs import pause_flow_run

    payload = pause_flow_run(
        wait_for_input=CheckpointInput,
        timeout=86400,
        key=f"{pending.kind}-{pending.command_version}",
        poll_interval=5,
    )
    if payload is None:
        return {}
    if hasattr(payload, "model_dump"):
        return payload.model_dump()
    return dict(payload)


def wait_for_decision(
    run_id: str,
    kind: CheckpointKind,
    receive: Callable[[ResearchDecision], Mapping[str, Any]] | None = None,
) -> ResearchDecision:
    receiver = receive or prefect_receive
    while True:
        current = load_decision(run_id, kind)
        if _is_accepted(current):
            return current
        if _is_rejected(current):
            raise CheckpointRejected(current)
        pending = current or ResearchDecision(
            run_id=run_id,
            kind=kind,
            stage=StageStatus.DONE,
            verdict=None,
            command_version=decision_command_version(
                run_id, kind, StageStatus.DONE, None
            ),
        )
        if current is None:
            save_decision(pending)
        payload = receiver(pending)
        decided = _apply_payload(pending, payload)
        if decided is pending or decided.verdict is None:
            continue
        save_decision(decided)
        if decided.verdict is DecisionVerdict.REJECTED:
            raise CheckpointRejected(decided)
        return decided
