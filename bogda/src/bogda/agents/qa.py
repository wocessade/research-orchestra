from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

QAFormat = Literal["single", "multi", "judge"]
QAConfidence = Literal["high", "medium", "low"]

_JUDGE_TRUE = frozenset({"对", "正确", "true", "t", "yes"})
_JUDGE_FALSE = frozenset({"错", "错误", "false", "f", "no"})


def normalize_answer(fmt: QAFormat, raw: str) -> str:
    text = (raw or "").strip()
    if fmt == "single":
        letter = text.upper()
        if letter in {"A", "B", "C", "D"}:
            return letter
        raise ValueError(f"invalid single answer: {raw!r}")
    if fmt == "multi":
        letters = sorted({ch for ch in text.upper() if ch in "ABCD"})
        if letters:
            return "".join(letters)
        raise ValueError(f"invalid multi answer: {raw!r}")
    if fmt == "judge":
        key = text.lower()
        if text in {"对", "正确"} or key in _JUDGE_TRUE:
            return "对"
        if text in {"错", "错误"} or key in _JUDGE_FALSE:
            return "错"
        raise ValueError(f"invalid judge answer: {raw!r}")
    raise ValueError(f"unknown format: {fmt!r}")


class QAAnswer(BaseModel):
    qno: int = Field(ge=1)
    format: QAFormat
    answer: str
    evidence: str = Field(min_length=1)
    confidence: QAConfidence

    @field_validator("answer")
    @classmethod
    def _normalize_answer_field(cls, value: str, info):
        fmt = info.data.get("format")
        if fmt is None:
            return value
        return normalize_answer(fmt, value)


class QARunnerAnswer(QAAnswer):
    runner: str = Field(min_length=1)


class QAOutput(BaseModel):
    task_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    runner: str = Field(min_length=1)
    answers: tuple[QAAnswer, ...]

    @model_validator(mode="after")
    def _answers_unique(self) -> QAOutput:
        if not self.answers:
            raise ValueError("answers must not be empty")
        qnos = [item.qno for item in self.answers]
        if len(qnos) != len(set(qnos)):
            raise ValueError("duplicate qno")
        return self
