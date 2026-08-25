import json
import sys
from pathlib import Path

import pytest
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import ArtifactFilter, ArtifactFilterKey
from prefect.client.schemas.sorting import ArtifactSort
from prefect.testing.utilities import prefect_test_harness

from bogda.artifacts import artifact_key, load_run_result
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
            autonomy_mode=AutonomyMode.AUTONOMOUS,
            parameters={
                "argv": [
                    sys.executable,
                    "-c",
                    "from pathlib import Path; Path('result.txt').write_text('bogda ok', encoding='utf-8')",
                ]
            },
            expected_artifacts=(ArtifactSpec(path="result.txt"),),
        )

        completed_state = run_shell_job(
            request.model_dump(mode="json"),
            str(tmp_path),
            return_state=True,
        )
        returned = RunResult.model_validate(completed_state.result())
        stored = load_run_result(returned.run_id)

        assert completed_state.name == "Completed"
        assert returned.execution_status.value == "Completed"
        assert Path(returned.declared_artifacts[0].uri).is_file()
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

        with get_client(sync_client=True) as client:
            retained_artifacts = client.read_artifacts(
                artifact_filter=ArtifactFilter(
                    key=ArtifactFilterKey(any_=[artifact_key(returned.run_id)])
                ),
                sort=ArtifactSort.CREATED_DESC,
            )

        retained_results = [
            RunResult.model_validate(
                json.loads(artifact.data)
                if isinstance(artifact.data, str)
                else artifact.data
            )
            for artifact in retained_artifacts
        ]
        assert len(retained_results) == 2
        assert [result.scientific_status for result in retained_results] == [
            ScientificStatus.ACCEPTED,
            ScientificStatus.UNREVIEWED,
        ]
        assert retained_results[0] == latest
        assert retained_results[1] == returned

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

        retry_request = request.model_copy(
            update={
                "job_id": "integration-retry",
                "retryable": True,
                "parameters": {
                    "argv": [
                        sys.executable,
                        "-c",
                        (
                            "from pathlib import Path\n"
                            "if Path.cwd().name == 'attempt-0001':\n"
                            "    raise SystemExit(17)\n"
                            "Path('result.txt').write_text('retry ok', encoding='utf-8')\n"
                        ),
                    ]
                },
            }
        )
        retried_state = run_shell_job(
            retry_request.model_dump(mode="json"),
            str(tmp_path),
            return_state=True,
        )
        retried = RunResult.model_validate(retried_state.result())
        retry_dir = tmp_path / retry_request.job_id / retried.run_id

        assert retried_state.name == "Completed"
        assert retried.attempt == 2
        assert (retry_dir / "attempt-0001").is_dir()
        assert (retry_dir / "attempt-0002" / "result.txt").read_text(
            encoding="utf-8"
        ) == "retry ok"
        assert not (retry_dir / "attempt-0003").exists()
        assert load_run_result(retried.run_id) == retried
