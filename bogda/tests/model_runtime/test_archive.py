from hashlib import sha256
from pathlib import Path

import pytest
from pydantic import ValidationError

from bogda.model_runtime.archive import FilePromptArchive, PromptArchiveConflictError
from bogda.model_runtime.contracts import (
    DshTokenUsageV1,
    ModelCallOutcome,
    ModelCallRequest,
    ModelCallResult,
)


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


def usage():
    return DshTokenUsageV1(
        input_tokens=1,
        cache_read_tokens=0,
        output_tokens=1,
        actual_cost_cny="0.10",
        reference="dsh",
    )


def test_model_call_result_repr_does_not_leak_output():
    result = ModelCallResult(
        outcome=ModelCallOutcome.FINISHED,
        output="sensitive model output",
        usage=usage(),
    )
    assert "sensitive model output" not in repr(result)


def test_model_call_request_requires_concrete_route_and_execution_settings(tmp_path):
    request = ModelCallRequest(
        run_id="run-1",
        call_id="call-1",
        effective_tier="flash",
        attempt_dir=tmp_path,
        timeout_seconds=5.0,
        prompt="secret-free prompt",
    )
    assert request.effective_tier.value == "flash"
    assert request.attempt_dir == tmp_path
    assert request.timeout_seconds == 5.0


def test_model_call_request_rejects_auto_route(tmp_path):
    with pytest.raises(ValidationError):
        ModelCallRequest(
            run_id="run-1",
            call_id="call-1",
            effective_tier="auto",
            attempt_dir=tmp_path,
            timeout_seconds=5.0,
            prompt="secret-free prompt",
        )


@pytest.mark.parametrize("timeout_seconds", [0, -1, 0.0, -0.1])
def test_model_call_request_rejects_non_positive_timeout(tmp_path, timeout_seconds):
    with pytest.raises(ValidationError):
        ModelCallRequest(
            run_id="run-1",
            call_id="call-1",
            effective_tier="flash",
            attempt_dir=tmp_path,
            timeout_seconds=timeout_seconds,
            prompt="secret-free prompt",
        )


@pytest.mark.parametrize(
    "result",
    [
        {"outcome": "finished", "output": "answer", "usage": None},
        {"outcome": "finished", "output": None, "usage": usage()},
        {"outcome": "not_started", "output": "answer", "usage": None},
        {"outcome": "not_started", "output": None, "usage": usage()},
        {"outcome": "usage_unknown", "output": "partial", "usage": usage()},
    ],
)
def test_model_call_result_rejects_inconsistent_states(result):
    with pytest.raises(ValidationError):
        ModelCallResult(**result)


def test_model_call_result_accepts_finished_and_unknown_states():
    finished = ModelCallResult(
        outcome=ModelCallOutcome.FINISHED,
        output="answer",
        usage=usage(),
    )
    unknown = ModelCallResult(
        outcome=ModelCallOutcome.USAGE_UNKNOWN,
        output="partial answer",
    )
    assert finished.output == "answer"
    assert unknown.output == "partial answer"
