import pytest

from bogda.artifacts.validation import validate_artifacts
from bogda.contracts import ArtifactSpec


def test_validate_artifacts_reports_present_and_optional_missing(tmp_path) -> None:
    (tmp_path / "result.txt").write_text("ok", encoding="utf-8")

    records = validate_artifacts(
        tmp_path,
        (
            ArtifactSpec(path="result.txt"),
            ArtifactSpec(path="optional.json", required=False),
        ),
    )

    assert records[0].exists is True
    assert records[0].size_bytes == 2
    assert records[1].exists is False
    assert records[1].size_bytes is None


def test_validate_artifacts_rejects_paths_outside_attempt(tmp_path) -> None:
    attempt_dir = tmp_path / "attempt"
    attempt_dir.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("not from this attempt", encoding="utf-8")

    records = validate_artifacts(
        attempt_dir,
        (
            ArtifactSpec(path=str(outside.resolve())),
            ArtifactSpec(path="../outside.txt"),
        ),
    )

    assert [record.exists for record in records] == [False, False]
    assert [record.size_bytes for record in records] == [None, None]


@pytest.mark.parametrize("artifact_path", ["", "output-directory"])
def test_validate_artifacts_requires_a_real_file(tmp_path, artifact_path) -> None:
    (tmp_path / "output-directory").mkdir()

    (record,) = validate_artifacts(
        tmp_path,
        (ArtifactSpec(path=artifact_path),),
    )

    assert record.exists is False
    assert record.size_bytes is None
