import pytest
from pydantic import ValidationError

from bogda.agents.qa import QAAnswer, QAOutput, normalize_answer


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
