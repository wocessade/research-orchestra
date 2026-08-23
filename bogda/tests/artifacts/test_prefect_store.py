import json
from types import SimpleNamespace

from bogda.artifacts import prefect_store
from bogda.contracts import ExecutionStatus, RunResult, ScientificStatus


def sample_result() -> RunResult:
    return RunResult.model_validate(
        {
            "run_id": "36c86e99-d0a1-4399-a30c-4d6c5044444c",
            "job_id": "job-1",
            "execution_status": "Completed",
            "scientific_status": "unreviewed",
            "started_at": "2026-08-24T00:00:00Z",
            "finished_at": "2026-08-24T00:00:01Z",
            "executor": "shell",
            "attempt": 1,
            "declared_artifacts": [],
            "summary": "completed",
        }
    )


def test_save_and_load_run_result_uses_one_versioned_key(monkeypatch) -> None:
    stored = {}

    class FakeArtifact:
        def __init__(self, **values):
            self.values = values

        def create(self):
            stored[self.values["key"]] = json.dumps(self.values["data"])
            return SimpleNamespace()

        @classmethod
        def get(cls, key):
            data = stored.get(key)
            return None if data is None else SimpleNamespace(data=data)

    monkeypatch.setattr(prefect_store, "Artifact", FakeArtifact)
    result = sample_result()

    prefect_store.save_run_result(result)
    loaded = prefect_store.load_run_result(result.run_id)

    assert prefect_store.artifact_key(result.run_id) == f"bogda-run-{result.run_id}"
    assert loaded == result
    assert loaded.execution_status is ExecutionStatus.COMPLETED
    assert loaded.scientific_status is ScientificStatus.UNREVIEWED


def test_load_returns_the_latest_saved_review_version(monkeypatch) -> None:
    stored = {}

    class FakeArtifact:
        def __init__(self, **values):
            self.values = values

        def create(self):
            stored.setdefault(self.values["key"], []).append(
                json.dumps(self.values["data"])
            )
            return SimpleNamespace()

        @classmethod
        def get(cls, key):
            versions = stored.get(key)
            return None if versions is None else SimpleNamespace(data=versions[-1])

    monkeypatch.setattr(prefect_store, "Artifact", FakeArtifact)
    result = sample_result()
    reviewed = result.model_copy(
        update={
            "scientific_status": ScientificStatus.ACCEPTED,
            "review_summary": "human accepted",
        }
    )

    prefect_store.save_run_result(result)
    prefect_store.save_run_result(reviewed)

    loaded = prefect_store.load_run_result(result.run_id)

    assert len(stored[prefect_store.artifact_key(result.run_id)]) == 2
    assert loaded == reviewed
    assert loaded.scientific_status is ScientificStatus.ACCEPTED
    assert loaded.review_summary == "human accepted"
