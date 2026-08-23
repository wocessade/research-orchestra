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
