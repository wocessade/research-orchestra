import pytest
from pydantic import ValidationError

from bogda.agents.coordinator import UnknownTool
from bogda.agents.qa import (
    FormatConflict,
    IncompleteAnswers,
    QAAnswer,
    QAOutput,
    StaleRevision,
    TaskIdMismatch,
    TOOL_SUBMIT_ANSWERS,
    merge_qa_outputs,
    normalize_answer,
    parse_qa_reply,
)


def test_normalize_single_multi_judge() -> None:
    assert normalize_answer("single", " b ") == "B"
    assert normalize_answer("multi", "b,a") == "AB"
    assert normalize_answer("multi", "BA") == "AB"
    assert normalize_answer("judge", "True") == "对"
    assert normalize_answer("judge", "F") == "错"


def test_normalize_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        normalize_answer("single", "E")
    with pytest.raises(ValueError):
        normalize_answer("multi", "xyz")
    with pytest.raises(ValueError):
        normalize_answer("judge", "maybe")


def test_qa_answer_normalizes_and_requires_evidence() -> None:
    item = QAAnswer(
        qno=1,
        format="single",
        answer="a",
        evidence="手册第3章",
        confidence="high",
    )
    assert item.answer == "A"
    with pytest.raises(ValidationError):
        QAAnswer(
            qno=1,
            format="single",
            answer="A",
            evidence="",
            confidence="high",
        )


def test_qa_output_rejects_empty_or_duplicate_qno() -> None:
    row = dict(
        qno=1,
        format="single",
        answer="A",
        evidence="手册",
        confidence="high",
    )
    with pytest.raises(ValidationError):
        QAOutput(task_id="T-1", revision=1, runner="h1", answers=())
    with pytest.raises(ValidationError):
        QAOutput(
            task_id="T-1",
            revision=1,
            runner="h1",
            answers=(
                QAAnswer(**row),
                QAAnswer(**row),
            ),
        )


def _reply(**overrides):
    body = {
        "tool": TOOL_SUBMIT_ANSWERS,
        "task_id": "T-20260826-001",
        "revision": 1,
        "runner": "h1",
        "answers": [
            {
                "qno": 1,
                "format": "single",
                "answer": "A",
                "evidence": "手册第3章",
                "confidence": "high",
            },
            {
                "qno": 21,
                "format": "multi",
                "answer": "BD",
                "evidence": "多选依据",
                "confidence": "medium",
            },
            {
                "qno": 31,
                "format": "judge",
                "answer": "对",
                "evidence": "常识",
                "confidence": "low",
            },
        ],
    }
    body.update(overrides)
    return body


def test_parse_qa_reply_accepts_submit_answers_tool() -> None:
    out = parse_qa_reply(_reply())
    assert out.task_id == "T-20260826-001"
    assert out.runner == "h1"
    assert [a.format for a in out.answers] == ["single", "multi", "judge"]


def test_parse_qa_reply_rejects_wrong_tool() -> None:
    with pytest.raises(UnknownTool) as raised:
        parse_qa_reply(_reply(tool="write_plan"))
    assert raised.value.tool == "write_plan"


def test_parse_qa_reply_rejects_missing_confidence() -> None:
    bad = _reply()
    del bad["answers"][0]["confidence"]
    with pytest.raises(ValidationError):
        parse_qa_reply(bad)


def _output(runner: str, answers: list[dict], revision: int = 1, task_id: str = "T-1"):
    return parse_qa_reply(
        {
            "tool": TOOL_SUBMIT_ANSWERS,
            "task_id": task_id,
            "revision": revision,
            "runner": runner,
            "answers": answers,
        }
    )


def _q(qno: int, fmt: str, answer: str) -> dict:
    return {
        "qno": qno,
        "format": fmt,
        "answer": answer,
        "evidence": f"e-{qno}-{answer}",
        "confidence": "high",
    }


def test_merge_agrees_on_identical_normalized_answers() -> None:
    a = _output("h1", [_q(1, "single", "a"), _q(2, "judge", "对")])
    b = _output("h2", [_q(1, "single", "A"), _q(2, "judge", "true")])
    merged = merge_qa_outputs((a, b), task_id="T-1", revision=1)
    assert [row.qno for row in merged.agreed] == [1, 2]
    assert merged.pending == ()
    assert merged.agreed[0].answer == "A"
    assert merged.agreed[1].answer == "对"


def test_merge_pending_when_answers_differ() -> None:
    a = _output("h1", [_q(1, "single", "A")])
    b = _output("o1", [_q(1, "single", "B")])
    merged = merge_qa_outputs((a, b), task_id="T-1", revision=1)
    assert merged.agreed == ()
    assert len(merged.pending) == 1
    assert {item.runner for item in merged.pending[0].by_runner} == {"h1", "o1"}


def test_merge_uses_lowest_confidence_on_agreement() -> None:
    low = _q(1, "single", "A")
    low["confidence"] = "low"
    a = _output("h1", [low])
    b = _output("h2", [_q(1, "single", "A")])
    merged = merge_qa_outputs((a, b), task_id="T-1", revision=1)
    assert merged.agreed[0].confidence == "low"
    assert merged.agreed[0].evidence == ("e-1-A",)


def test_merge_rejects_stale_revision_and_task_mismatch() -> None:
    current = _output("h1", [_q(1, "single", "A")], revision=2)
    with pytest.raises(StaleRevision):
        merge_qa_outputs((current,), task_id="T-1", revision=1)
    other = _output("h1", [_q(1, "single", "A")], task_id="T-9")
    with pytest.raises(TaskIdMismatch):
        merge_qa_outputs((other,), task_id="T-1", revision=1)


def test_merge_rejects_incomplete_or_format_conflict() -> None:
    a = _output("h1", [_q(1, "single", "A"), _q(2, "judge", "对")])
    b = _output("h2", [_q(1, "single", "A")])
    with pytest.raises(IncompleteAnswers):
        merge_qa_outputs((a, b), task_id="T-1", revision=1)
    c = _output("h2", [_q(1, "judge", "对"), _q(2, "judge", "对")])
    with pytest.raises(FormatConflict):
        merge_qa_outputs((a, c), task_id="T-1", revision=1)
