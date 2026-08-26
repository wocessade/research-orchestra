import pytest
from pydantic import ValidationError

from bogda.agents.coordinator import UnknownTool
from bogda.agents.qa import (
    QAAnswer,
    QAOutput,
    TOOL_SUBMIT_ANSWERS,
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
