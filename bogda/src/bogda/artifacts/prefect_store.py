import json
from uuid import UUID

from prefect.artifacts import Artifact

from bogda.contracts import RunResult


def artifact_key(run_id: str) -> str:
    return f"bogda-run-{UUID(run_id)}"


def save_run_result(result: RunResult) -> None:
    Artifact(
        key=artifact_key(result.run_id),
        type="bogda.run-result",
        description=f"Bogda result for {result.job_id}",
        data=result.model_dump(mode="json"),
        flow_run_id=UUID(result.run_id),
    ).create()


def load_run_result(run_id: str) -> RunResult | None:
    artifact = Artifact.get(key=artifact_key(run_id))
    if artifact is None:
        return None
    data = json.loads(artifact.data) if isinstance(artifact.data, str) else artifact.data
    return RunResult.model_validate(data)
