from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, Field, field_validator, model_validator

from bogda.agents.coordinator import UnknownTool

QAFormat = Literal["single", "multi", "judge"]
QAConfidence = Literal["high", "medium", "low"]

TOOL_SUBMIT_ANSWERS = "submit_answers"

_CONF_RANK = {"high": 2, "medium": 1, "low": 0}

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


class StaleRevision(ValueError):
    pass


class TaskIdMismatch(ValueError):
    pass


class IncompleteAnswers(ValueError):
    pass


class FormatConflict(ValueError):
    pass


class QAConsensus(BaseModel):
    qno: int
    format: QAFormat
    answer: str
    evidence: tuple[str, ...]
    confidence: QAConfidence


class QADivergence(BaseModel):
    qno: int
    format: QAFormat
    by_runner: tuple[QARunnerAnswer, ...]


class QAMergeResult(BaseModel):
    task_id: str
    revision: int
    agreed: tuple[QAConsensus, ...]
    pending: tuple[QADivergence, ...]


def merge_qa_outputs(
    outputs: Sequence[QAOutput],
    *,
    task_id: str,
    revision: int,
) -> QAMergeResult:
    if not outputs:
        raise ValueError("no outputs")
    runners = [item.runner for item in outputs]
    if len(runners) != len(set(runners)):
        raise ValueError("duplicate runner")
    for item in outputs:
        if item.task_id != task_id:
            raise TaskIdMismatch(item.task_id)
        if item.revision != revision:
            raise StaleRevision(str(item.revision))
    qno_sets = [frozenset(ans.qno for ans in item.answers) for item in outputs]
    if any(qset != qno_sets[0] for qset in qno_sets[1:]):
        raise IncompleteAnswers("qno sets differ")
    by_qno: dict[int, list[QARunnerAnswer]] = {}
    for item in outputs:
        for ans in item.answers:
            by_qno.setdefault(ans.qno, []).append(
                QARunnerAnswer(
                    qno=ans.qno,
                    format=ans.format,
                    answer=ans.answer,
                    evidence=ans.evidence,
                    confidence=ans.confidence,
                    runner=item.runner,
                )
            )
    agreed: list[QAConsensus] = []
    pending: list[QADivergence] = []
    for qno in sorted(by_qno):
        rows = tuple(by_qno[qno])
        formats = {row.format for row in rows}
        if len(formats) != 1:
            raise FormatConflict(f"qno {qno}")
        fmt = rows[0].format
        answers = {row.answer for row in rows}
        if len(answers) == 1:
            evidence: list[str] = []
            for row in rows:
                if row.evidence not in evidence:
                    evidence.append(row.evidence)
            lowest = min(rows, key=lambda row: _CONF_RANK[row.confidence])
            agreed.append(
                QAConsensus(
                    qno=qno,
                    format=fmt,
                    answer=rows[0].answer,
                    evidence=tuple(evidence),
                    confidence=lowest.confidence,
                )
            )
        else:
            pending.append(QADivergence(qno=qno, format=fmt, by_runner=rows))
    return QAMergeResult(
        task_id=task_id,
        revision=revision,
        agreed=tuple(agreed),
        pending=tuple(pending),
    )


def parse_qa_reply(reply: Mapping[str, Any]) -> QAOutput:
    tool = reply.get("tool")
    if tool != TOOL_SUBMIT_ANSWERS:
        raise UnknownTool(tool)
    payload = {key: value for key, value in reply.items() if key != "tool"}
    return QAOutput.model_validate(payload)


def write_runner_answers(root: Path, output: QAOutput) -> Path:
    dest = root / "answers" / f"{output.runner}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(output.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return dest


def write_merge_result(root: Path, merged: QAMergeResult) -> Path:
    dest = root / "merge.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(merged.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return dest
