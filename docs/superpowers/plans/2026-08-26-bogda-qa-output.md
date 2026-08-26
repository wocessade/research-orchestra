# Bogda QA Output Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `bogda/agents/qa.py` 落地并行问答的结构化产物：工具强制解析、按题规范化、fail-closed 合并、JSON 落盘。

**Architecture:** 纯库，不改 Coordinator / Prefect / 控制台。模型回复必须带 `tool=submit_answers`，其余字段走 Pydantic；合并只比较规范化后的答案，分歧不多数决；过期 `revision` 拒收。调用方传入结果根目录，写入 `answers/<runner>.json` 与 `merge.json`。

**Tech Stack:** Python 3.11–3.13，Pydantic 2，pytest 8，uv。验证命令一律在 `bogda/` 下用 Python 3.11。

**Spec:** `docs/superpowers/specs/2026-08-26-bogda-qa-output-design.md`

## Global Constraints

- 不修改 `coordinator.py`、`contracts.py`、`flows/`、`orchestra/`、Pi 部署、3100/3101。
- 不建 `TYPE_REGISTRY`、任务卡解析器、补丁广播、CLI、Prefect 接线。
- 不把 `env` / `alerts` / SMTP / cookie 放进本合约。
- fail-closed：缺字段、错误 tool、过期 revision、题号集合不一致一律抛错，不猜测。
- 一致采信规则：全员规范化 `answer` 相同才进 `agreed`；否则进 `pending`。不做多数决。
- 既有 `tests/agents/test_coordinator.py` 必须保持通过。
- 测试用 `uv run --python 3.11 pytest …`；不要对未批准的提交使用 `--no-verify`。
- 本计划中的 commit 仅在 owner 批准执行本计划后进行；commit 不加 Co-Authored-By。

---

## File Map

| File | Responsibility |
|---|---|
| `bogda/src/bogda/agents/qa.py` | `TOOL_SUBMIT_ANSWERS`、规范化、`QAAnswer`/`QAOutput`/`QAMergeResult`、解析、合并、落盘、专用异常 |
| `bogda/tests/agents/test_qa.py` | 本切片全部单测 |
| `bogda/src/bogda/agents/__init__.py` | 导出公开符号 |

---

### Task 1: QA 模型与答案规范化

**Files:**

- Create: `bogda/tests/agents/test_qa.py`
- Create: `bogda/src/bogda/agents/qa.py`

**Interfaces:**

- Consumes: Pydantic 2；spec §3.1–3.2
- Produces: `QAFormat`/`QAConfidence` 字面量、`normalize_answer`、`QAAnswer`、`QARunnerAnswer`、`QAOutput`

- [ ] **Step 1: Write the failing tests**

Create `bogda/tests/agents/test_qa.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```
uv run --python 3.11 pytest tests/agents/test_qa.py::test_normalize_single_multi_judge tests/agents/test_qa.py::test_normalize_rejects_garbage tests/agents/test_qa.py::test_qa_answer_normalizes_and_requires_evidence tests/agents/test_qa.py::test_qa_output_rejects_empty_or_duplicate_qno -v
```

Working directory: `bogda/`

Expected: FAIL with `ModuleNotFoundError: bogda.agents.qa` or import error for `normalize_answer`.

- [ ] **Step 3: Write minimal implementation**

Create `bogda/src/bogda/agents/qa.py`:

```python
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
    def _answers_unique(self) -> "QAOutput":
        if not self.answers:
            raise ValueError("answers must not be empty")
        qnos = [item.qno for item in self.answers]
        if len(qnos) != len(set(qnos)):
            raise ValueError("duplicate qno")
        return self
```

`QAAnswer.answer` 的 validator 依赖 `format` 已解析：Pydantic v2 默认按字段定义顺序校验，`format` 在 `answer` 之前，`info.data["format"]` 可用。若测试显示 `format` 尚未进入 `info.data`，改为 `@model_validator(mode="after")` 内调用 `normalize_answer` 并 `model_copy(update={"answer": ...})`。

- [ ] **Step 4: Run tests to verify they pass**

Run:

```
uv run --python 3.11 pytest tests/agents/test_qa.py::test_normalize_single_multi_judge tests/agents/test_qa.py::test_normalize_rejects_garbage tests/agents/test_qa.py::test_qa_answer_normalizes_and_requires_evidence tests/agents/test_qa.py::test_qa_output_rejects_empty_or_duplicate_qno -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```
git add bogda/src/bogda/agents/qa.py bogda/tests/agents/test_qa.py
git commit -m "Add Bogda QA answer models with fail-closed normalization." -m "Lock per-question format and required evidence so parallel exam outputs can be compared without prompt-side formatting."
```

---

### Task 2: `submit_answers` 解析

**Files:**

- Modify: `bogda/src/bogda/agents/qa.py`
- Modify: `bogda/tests/agents/test_qa.py`

**Interfaces:**

- Consumes: `UnknownTool` from `bogda.agents.coordinator`；`QAOutput`
- Produces: `TOOL_SUBMIT_ANSWERS = "submit_answers"`；`parse_qa_reply(reply: Mapping[str, Any]) -> QAOutput`

- [ ] **Step 1: Write the failing tests**

Append to `bogda/tests/agents/test_qa.py`:

```python
from bogda.agents.coordinator import UnknownTool
from bogda.agents.qa import TOOL_SUBMIT_ANSWERS, parse_qa_reply


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```
uv run --python 3.11 pytest tests/agents/test_qa.py::test_parse_qa_reply_accepts_submit_answers_tool tests/agents/test_qa.py::test_parse_qa_reply_rejects_wrong_tool tests/agents/test_qa.py::test_parse_qa_reply_rejects_missing_confidence -v
```

Expected: FAIL with `ImportError` / `cannot import name parse_qa_reply`.

- [ ] **Step 3: Write minimal implementation**

Add to `bogda/src/bogda/agents/qa.py` (imports go at file top; do not duplicate `from __future__`):

```python
from typing import Any, Mapping

from bogda.agents.coordinator import UnknownTool

TOOL_SUBMIT_ANSWERS = "submit_answers"


def parse_qa_reply(reply: Mapping[str, Any]) -> QAOutput:
    tool = reply.get("tool")
    if tool != TOOL_SUBMIT_ANSWERS:
        raise UnknownTool(tool)
    payload = {key: value for key, value in reply.items() if key != "tool"}
    return QAOutput.model_validate(payload)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```
uv run --python 3.11 pytest tests/agents/test_qa.py -v
```

Expected: all tests in this file passed, including Task 1.

- [ ] **Step 5: Commit**

```
git add bogda/src/bogda/agents/qa.py bogda/tests/agents/test_qa.py
git commit -m "Parse submit_answers replies through QAOutput validation." -m "Reject unknown tools and missing confidence instead of reading free-form exam lists."
```

---

### Task 3: fail-closed 合并

**Files:**

- Modify: `bogda/src/bogda/agents/qa.py`
- Modify: `bogda/tests/agents/test_qa.py`

**Interfaces:**

- Consumes: `QAOutput`、`QAAnswer`、`QARunnerAnswer`
- Produces: `StaleRevision`、`TaskIdMismatch`、`IncompleteAnswers`、`FormatConflict`、`QAConsensus`、`QADivergence`、`QAMergeResult`、`merge_qa_outputs(outputs, *, task_id, revision)`

- [ ] **Step 1: Write the failing tests**

Append to `bogda/tests/agents/test_qa.py`:

```python
from bogda.agents.qa import (
    FormatConflict,
    IncompleteAnswers,
    StaleRevision,
    TaskIdMismatch,
    merge_qa_outputs,
    parse_qa_reply,
)


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```
uv run --python 3.11 pytest tests/agents/test_qa.py::test_merge_agrees_on_identical_normalized_answers tests/agents/test_qa.py::test_merge_pending_when_answers_differ tests/agents/test_qa.py::test_merge_uses_lowest_confidence_on_agreement tests/agents/test_qa.py::test_merge_rejects_stale_revision_and_task_mismatch tests/agents/test_qa.py::test_merge_rejects_incomplete_or_format_conflict -v
```

Expected: FAIL importing `merge_qa_outputs` / the exception types.

- [ ] **Step 3: Write minimal implementation**

Add to `bogda/src/bogda/agents/qa.py`:

```python
from typing import Sequence

_CONF_RANK = {"high": 2, "medium": 1, "low": 0}


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```
uv run --python 3.11 pytest tests/agents/test_qa.py -v
```

Expected: all passed.

- [ ] **Step 5: Commit**

```
git add bogda/src/bogda/agents/qa.py bogda/tests/agents/test_qa.py
git commit -m "Merge parallel QA outputs with stale-revision rejection." -m "Agreement requires identical normalized answers; disagreements stay pending with no majority vote."
```

---

### Task 4: 落盘与公开导出

**Files:**

- Modify: `bogda/src/bogda/agents/qa.py`
- Modify: `bogda/tests/agents/test_qa.py`
- Modify: `bogda/src/bogda/agents/__init__.py`

**Interfaces:**

- Consumes: `QAOutput`、`QAMergeResult`
- Produces: `write_runner_answers(root: Path, output: QAOutput) -> Path`；`write_merge_result(root: Path, merged: QAMergeResult) -> Path`；`__init__.py` 导出下表全部公开名

Public exports:

`TOOL_SUBMIT_ANSWERS`, `QAAnswer`, `QARunnerAnswer`, `QAOutput`, `QAConsensus`, `QADivergence`, `QAMergeResult`, `parse_qa_reply`, `merge_qa_outputs`, `write_runner_answers`, `write_merge_result`, `normalize_answer`, `StaleRevision`, `TaskIdMismatch`, `IncompleteAnswers`, `FormatConflict`

- [ ] **Step 1: Write the failing tests**

Append to `bogda/tests/agents/test_qa.py`:

```python
import json
from pathlib import Path

from bogda.agents.qa import write_merge_result, write_runner_answers


def test_write_runner_and_merge_json(tmp_path: Path) -> None:
    out = _output("h1", [_q(1, "single", "A")])
    other = _output("h2", [_q(1, "single", "B")])
    ans_path = write_runner_answers(tmp_path, out)
    assert ans_path == tmp_path / "answers" / "h1.json"
    dumped = json.loads(ans_path.read_text(encoding="utf-8"))
    assert dumped["runner"] == "h1"
    assert dumped["answers"][0]["answer"] == "A"
    merged = merge_qa_outputs((out, other), task_id="T-1", revision=1)
    merge_path = write_merge_result(tmp_path, merged)
    assert merge_path == tmp_path / "merge.json"
    body = json.loads(merge_path.read_text(encoding="utf-8"))
    assert body["pending"][0]["qno"] == 1
    assert body["agreed"] == []
```

Also add:

```python
import bogda.agents as agents


def test_public_exports() -> None:
    assert hasattr(agents, "parse_qa_reply")
    assert hasattr(agents, "merge_qa_outputs")
    assert hasattr(agents, "TOOL_SUBMIT_ANSWERS")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```
uv run --python 3.11 pytest tests/agents/test_qa.py::test_write_runner_and_merge_json tests/agents/test_qa.py::test_public_exports -v
```

Expected: FAIL missing `write_runner_answers` / `parse_qa_reply` not on `bogda.agents`.

- [ ] **Step 3: Write minimal implementation**

Add to `bogda/src/bogda/agents/qa.py`:

```python
from pathlib import Path


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
```

Update `bogda/src/bogda/agents/__init__.py` to import and list the public names from Task 4 Interfaces. Keep existing Coordinator exports:

```python
from bogda.agents.contracts import (
    AgentBudget,
    CoordinatorResult,
    ExperimentProposal,
    ResearchPlan,
)
from bogda.agents.coordinator import (
    TOOL_PROPOSE_EXPERIMENT,
    TOOL_WRITE_PLAN,
    Coordinator,
    UnknownTool,
)
from bogda.agents.qa import (
    TOOL_SUBMIT_ANSWERS,
    FormatConflict,
    IncompleteAnswers,
    QAAnswer,
    QAConsensus,
    QADivergence,
    QAMergeResult,
    QAOutput,
    QARunnerAnswer,
    StaleRevision,
    TaskIdMismatch,
    merge_qa_outputs,
    normalize_answer,
    parse_qa_reply,
    write_merge_result,
    write_runner_answers,
)

__all__ = [
    "AgentBudget",
    "Coordinator",
    "CoordinatorResult",
    "ExperimentProposal",
    "FormatConflict",
    "IncompleteAnswers",
    "QAAnswer",
    "QAConsensus",
    "QADivergence",
    "QAMergeResult",
    "QAOutput",
    "QARunnerAnswer",
    "ResearchPlan",
    "StaleRevision",
    "TOOL_PROPOSE_EXPERIMENT",
    "TOOL_SUBMIT_ANSWERS",
    "TOOL_WRITE_PLAN",
    "TaskIdMismatch",
    "UnknownTool",
    "merge_qa_outputs",
    "normalize_answer",
    "parse_qa_reply",
    "write_merge_result",
    "write_runner_answers",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```
uv run --python 3.11 pytest tests/agents/test_qa.py tests/agents/test_coordinator.py -v
```

Expected: both files fully passed. Do not run integration tests.

- [ ] **Step 5: Commit**

```
git add bogda/src/bogda/agents/qa.py bogda/src/bogda/agents/__init__.py bogda/tests/agents/test_qa.py
git commit -m "Persist QA runner answers and merge.json under a caller root." -m "Export the QA contract from bogda.agents without changing Coordinator research-cycle behavior."
```

Also add the spec and plan if they are not yet committed:

```
git add docs/superpowers/specs/2026-08-26-bogda-qa-output-design.md docs/superpowers/plans/2026-08-26-bogda-qa-output.md
git commit -m "Document Bogda QA output contract and implementation plan."
```

Prefer folding spec/plan into the first execution commit if they are still untracked at Task 1.

---

## Self-review

- Spec §3 合约、解析、合并、落盘均有对应 Task 1–4。
- 线 B / 任务卡 / 类型注册表明确不在任务中。
- 无 TBD 占位；异常名与导出表前后一致。
- `parse_qa_reply` 依赖 Task 1 的 `QAOutput`；`merge_qa_outputs` 依赖 Task 2 的解析以构造夹具。
