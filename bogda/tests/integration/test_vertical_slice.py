import sys

import pytest
from prefect.testing.utilities import prefect_test_harness

from bogda.artifacts import load_run_result
from bogda.contracts import (
    ArtifactSpec,
    AutonomyMode,
    JobRequest,
    ResourceClass,
    RunResult,
    ScientificStatus,
)
from bogda.flows import review_run_result, run_shell_job


@pytest.mark.integration
def test_local_vertical_slice(tmp_path) -> None:
    with prefect_test_harness(server_startup_timeout=60):
        request = JobRequest(
            job_id="integration-job",
            project_id="bogda",
            task_type="shell",
            resource_class=ResourceClass.CPU,
            autonomy_mode=AutonomyMode.SUPERVISED,
            parameters={
                "argv": [
                    sys.executable,
                    "-c",
                    "from pathlib import Path; Path('result.txt').write_text('bogda ok', encoding='utf-8')",
                ]
            },
            expected_artifacts=(ArtifactSpec(path="result.txt"),),
        )

        returned = RunResult.model_validate(
            run_shell_job(
                request.model_dump(mode="json"),
                str(tmp_path),
            )
        )
        stored = load_run_result(returned.run_id)

        assert returned.execution_status.value == "Completed"
        assert stored is not None
        assert stored.scientific_status is ScientificStatus.UNREVIEWED

        reviewed = RunResult.model_validate(
            review_run_result(
                returned.run_id,
                ScientificStatus.ACCEPTED.value,
                "human accepted",
            )
        )
        latest = load_run_result(returned.run_id)

        assert reviewed.execution_status == returned.execution_status
        assert latest is not None
        assert latest.scientific_status is ScientificStatus.ACCEPTED
        assert latest.summary == returned.summary
        assert latest.review_summary == "human accepted"

        missing_request = request.model_copy(
            update={
                "job_id": "integration-missing",
                "parameters": {
                    "argv": [sys.executable, "-c", "print('no artifact')"]
                },
            }
        )
        failed_state = run_shell_job(
            missing_request.model_dump(mode="json"),
            str(tmp_path),
            return_state=True,
        )
        failed_run_id = str(failed_state.state_details.flow_run_id)
        failed_result = load_run_result(failed_run_id)

        assert failed_state.name == "Failed"
        assert failed_result is not None
        assert failed_result.execution_status.value == "Failed"
        assert "result.txt" in failed_result.summary
