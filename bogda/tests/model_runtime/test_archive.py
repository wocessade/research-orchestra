from hashlib import sha256
from pathlib import Path

import pytest
from pydantic import ValidationError

from bogda.model_runtime.archive import FilePromptArchive, PromptArchiveConflictError
from bogda.model_runtime.contracts import DshTokenUsageV1


def test_archive_writes_exact_prompt_and_returns_hash(tmp_path):
    archive = FilePromptArchive(tmp_path)
    artifact = archive.archive("run-1", "call-1", "审计这个结果")
    assert Path(artifact.path).read_text(encoding="utf-8") == "审计这个结果"
    assert artifact.sha256 == sha256("审计这个结果".encode()).hexdigest()


def test_archive_is_idempotent_only_for_same_content(tmp_path):
    archive = FilePromptArchive(tmp_path)
    assert archive.archive("run-1", "call-1", "same") == archive.archive(
        "run-1", "call-1", "same"
    )
    with pytest.raises(PromptArchiveConflictError):
        archive.archive("run-1", "call-1", "different")


def test_usage_rejects_float_and_serializes_decimal_cost_as_string():
    with pytest.raises(ValidationError):
        DshTokenUsageV1(
            input_tokens=1,
            cache_read_tokens=0,
            output_tokens=1,
            actual_cost_cny=0.1,
            reference="dsh",
        )


def test_usage_serializes_decimal_cost_as_string():
    usage = DshTokenUsageV1(
        input_tokens=1,
        cache_read_tokens=0,
        output_tokens=1,
        actual_cost_cny="0.10",
        reference="dsh",
    )
    assert usage.model_dump(mode="json")["actual_cost_cny"] == "0.10"


@pytest.mark.parametrize("identifier", ["run/1", "run\\1"])
def test_archive_rejects_path_separators_in_identifiers(tmp_path, identifier):
    archive = FilePromptArchive(tmp_path)
    with pytest.raises(ValueError):
        archive.archive(identifier, "call-1", "prompt")


def test_archive_conflict_exception_does_not_leak_prompt(tmp_path):
    archive = FilePromptArchive(tmp_path)
    archive.archive("run-1", "call-1", "first prompt")

    with pytest.raises(PromptArchiveConflictError) as raised:
        archive.archive("run-1", "call-1", "sensitive prompt")

    assert "sensitive prompt" not in str(raised.value)
    assert "sensitive prompt" not in repr(raised.value)
