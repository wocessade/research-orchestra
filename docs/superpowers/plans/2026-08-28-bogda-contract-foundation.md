# Bogda Contract Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 建立 Bogda 智能协作的版本化领域契约，统一任务意图、模型档位、动态预算和结构化事件类型，并提供不依赖 Orchestra 包的单向旧任务卡转换。

**Architecture:** 本计划只交付纯 Python/Pydantic 契约与兼容转换，不连接 DeepSeek、Prefect 写接口、dsh 或前端。现有 `JobRequest` 以向后兼容默认值扩展；所有金额从 `float` 收敛为 `Decimal`，后续预算内核和 Console 都消费这里定义的单一事实源。

**Tech Stack:** Python 3.11–3.13、Pydantic 2.11、pytest 8.4、stdlib `Decimal`/`StrEnum`/`datetime`。

**Spec:** `docs/superpowers/specs/2026-08-28-bogda-intelligent-collaboration-budget-design.md`

## Global Constraints

- 本计划不得修改 RK3528、Prefect、systemd、`prefect.db`、`bogda.env`、工作池或现网并发。
- Bogda 不得导入 `orchestra` 包、旧 Broker 数据库或任务扫描循环。
- `autonomy_mode`、`intent`、`model_tier` 和 `executor` 必须保持正交；Pro 不扩大权限。
- 金额统一使用 `Decimal`，JSON 中序列化为十进制字符串；不得重新引入 `float` 金额。
- 未知 schema、intent、model tier、executor 和价格偏好必须 fail-closed。
- 已有 shell 纵向切片、科研检查点和 autonomy 策略必须保持兼容。
- 本计划不实现价格计算、余额 API、模型路由、运行时暂停、JSONL writer 或前端窗口。
- 每个任务严格执行 TDD：先观察聚焦测试失败，再写最小实现，再运行相关全量测试。
- 每个任务单独提交；SOL 在下一个任务开始前审查 diff、接口和测试证据。

## Program Decomposition

本规格按以下独立计划链交付，避免提前为尚未存在的运行时代码写陈旧大计划：

| 顺序 | 独立交付 | 本计划是否包含 | 下一计划的启动条件 |
|---|---|---|---|
| A | 领域契约、Decimal、Orchestra 单向兼容、事件 schema | 是 | 本计划全量测试和审查通过 |
| B | UsagePort、价格目录、工作量预测、预算门禁和预留 | 否 | A 的类型稳定并发布内部 schema v1 |
| C | Flash/Pro 路由、dsh 调用、prompt 归档、暂停/恢复 | 否 | B 的 fake provider 集成验收通过 |
| D | Console 决策中心、策略窗口、运行详情和审批 API | 否 | C 产出稳定只读/命令契约 |
| E | 影子决策、强制门禁、错峰调度与生产迁移 | 否 | A–D 本地验收完成且 owner 单独批准现网阶段 |

后续计划在前一阶段完成后基于实际代码生成，不在本计划中猜测尚不存在的签名。

## SOL / Luna 协作规则

- Luna 优先实现 Task 1、2、4、5；每次只领取一个边界明确的任务。
- SOL 负责 Task 3、6、任务间接口审查、冲突处理、全量验证和是否进入下一阶段的裁决。
- Luna 不修改本任务 `Files` 列表之外的文件；发现额外依赖必须返回 `CONCERN`，不能自行扩域。
- Luna 的返回必须包含聚焦测试命令、失败前证据、通过后证据和提交 SHA。
- SOL 不接受只报“测试通过”的结果；必须复核 staged/committed diff 和在当前工作树重新运行验证。

---

### Task 1: Task Intent、Model Tier 与调度窗口契约

**Preferred implementer:** Luna；SOL 复核枚举命名、时区验证和导出面。

**Files:**
- Create: `bogda/src/bogda/contracts/tasks.py`
- Modify: `bogda/src/bogda/contracts/__init__.py`
- Create: `bogda/tests/contracts/test_tasks.py`

**Interfaces:**
- Produces: `TaskIntent`, `ModelTier`, `ExecutorKind`, `PricePreference`, `SchedulePolicy`。
- `SchedulePolicy(earliest_start, deadline, price_preference)` 只接受带时区时间；若两者同时存在，`deadline` 必须晚于 `earliest_start`。
- Later tasks import these types only from `bogda.contracts`, not from private module paths.

- [x] **Step 1: Write failing enum and schedule tests**

```python
from datetime import datetime

import pytest
from pydantic import ValidationError

from bogda.contracts import (
    ExecutorKind,
    ModelTier,
    PricePreference,
    SchedulePolicy,
    TaskIntent,
)


def test_task_axes_have_stable_wire_values() -> None:
    assert [item.value for item in TaskIntent] == [
        "execute", "explore", "decide", "audit", "brief"
    ]
    assert [item.value for item in ModelTier] == ["auto", "flash", "pro"]
    assert [item.value for item in ExecutorKind] == ["dsh", "shell"]


def test_schedule_policy_requires_aware_ordered_times() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        SchedulePolicy(earliest_start=datetime(2026, 8, 28, 18, 0))

    with pytest.raises(ValidationError, match="deadline must be after earliest_start"):
        SchedulePolicy(
            earliest_start="2026-08-28T20:00:00+08:00",
            deadline="2026-08-28T19:00:00+08:00",
        )


def test_schedule_defaults_to_cheapest_before_deadline() -> None:
    policy = SchedulePolicy()
    assert policy.price_preference is PricePreference.CHEAPEST_BEFORE_DEADLINE
```

- [x] **Step 2: Run the focused test and verify the expected failure**

Run:

```powershell
Set-Location D:\pythonProject\bogda
uv run --python 3.11 pytest tests/contracts/test_tasks.py -v
```

Expected: collection fails because the five exported contract types do not exist.

- [x] **Step 3: Implement the minimal task-axis contracts**

```python
# bogda/src/bogda/contracts/tasks.py
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, model_validator


class TaskIntent(StrEnum):
    EXECUTE = "execute"
    EXPLORE = "explore"
    DECIDE = "decide"
    AUDIT = "audit"
    BRIEF = "brief"


class ModelTier(StrEnum):
    AUTO = "auto"
    FLASH = "flash"
    PRO = "pro"


class ExecutorKind(StrEnum):
    DSH = "dsh"
    SHELL = "shell"


class PricePreference(StrEnum):
    IMMEDIATE = "immediate"
    CHEAPEST_BEFORE_DEADLINE = "cheapest_before_deadline"


class SchedulePolicy(BaseModel):
    earliest_start: datetime | None = None
    deadline: datetime | None = None
    price_preference: PricePreference = PricePreference.CHEAPEST_BEFORE_DEADLINE

    @model_validator(mode="after")
    def validate_window(self) -> Self:
        for name in ("earliest_start", "deadline"):
            value = getattr(self, name)
            if value is not None and value.utcoffset() is None:
                raise ValueError(f"{name} must be timezone-aware")
        if (
            self.earliest_start is not None
            and self.deadline is not None
            and self.deadline <= self.earliest_start
        ):
            raise ValueError("deadline must be after earliest_start")
        return self
```

Add all five names to `bogda/contracts/__init__.py` imports and `__all__`.

- [x] **Step 4: Run focused and existing contract tests**

Run:

```powershell
uv run --python 3.11 pytest tests/contracts/test_tasks.py tests/contracts/test_models.py -v
```

Expected: all tests pass; existing `JobRequest` behavior is unchanged.

- [x] **Step 5: Commit the task**

```powershell
git add bogda/src/bogda/contracts/tasks.py bogda/src/bogda/contracts/__init__.py bogda/tests/contracts/test_tasks.py
git commit -m "feat(bogda): add task routing contracts"
```

---

### Task 2: Decimal Budget Envelope 与现有 Agent 金额迁移

**Preferred implementer:** Luna；SOL 复核所有金额字段，禁止残留 float 算术。

**Files:**
- Create: `bogda/src/bogda/contracts/budgets.py`
- Modify: `bogda/src/bogda/contracts/__init__.py`
- Modify: `bogda/src/bogda/agents/contracts.py`
- Modify: `bogda/src/bogda/agents/coordinator.py`
- Modify: `bogda/tests/agents/test_coordinator.py`
- Modify: `bogda/tests/flows/test_research_cycle.py`
- Create: `bogda/tests/contracts/test_budgets.py`

**Interfaces:**
- Consumes: `ModelTier` from Task 1.
- Produces: `BudgetSource`, `RunBudgetEnvelope` and Decimal-based `AgentBudget.max_cost_cny` / `CoordinatorResult.cost_cny_used`.
- `RunBudgetEnvelope` serializes all monetary fields as JSON strings and rejects expected cost above the authorized ceiling.
- `fallback_tier` accepts only `flash` or `None`; Pro/Auto are not fallback tiers in schema v1.

- [x] **Step 1: Write failing budget-envelope tests**

```python
from decimal import Decimal

import pytest
from pydantic import ValidationError

from bogda.contracts import BudgetSource, ModelTier, RunBudgetEnvelope


def envelope(**updates) -> RunBudgetEnvelope:
    values = {
        "expected_cost": "2.880000",
        "authorized_ceiling": "5.320000",
        "minimum_remaining": "10.000000",
        "requested_tier": "pro",
        "fallback_tier": "flash",
        "budget_source": "project",
        "pricing_version": "deepseek-cn-2026-08-28",
    }
    values.update(updates)
    return RunBudgetEnvelope(**values)


def test_budget_money_round_trips_as_decimal_strings() -> None:
    budget = envelope()
    payload = budget.model_dump(mode="json")
    assert budget.schema_version == 1
    assert budget.expected_cost == Decimal("2.880000")
    assert payload["expected_cost"] == "2.880000"
    assert payload["authorized_ceiling"] == "5.320000"
    assert budget.budget_source is BudgetSource.PROJECT


def test_budget_rejects_tight_ceiling_and_invalid_fallback() -> None:
    with pytest.raises(ValidationError, match="expected_cost cannot exceed"):
        envelope(expected_cost="6", authorized_ceiling="5")
    with pytest.raises(ValidationError, match="fallback_tier must be flash"):
        envelope(fallback_tier=ModelTier.PRO)


def test_budget_rejects_float_money_input() -> None:
    with pytest.raises(ValidationError, match="money values must not be floats"):
        envelope(expected_cost=2.88)
```

- [x] **Step 2: Add failing regression tests for Decimal agent accounting**

Update `bogda/tests/agents/test_coordinator.py`:

```python
from decimal import Decimal


def test_agent_cost_accounting_uses_decimal() -> None:
    model = ScriptedModel([
        {
            "tool": TOOL_WRITE_PLAN,
            "plan": {"goal": "g", "steps": ["s"], "rationale": "r"},
        }
    ])
    result = make_coordinator(
        model,
        max_steps=1,
        max_model_calls=1,
        max_cost_cny="0.30",
        cost_per_call="0.10",
    ).run("g")
    assert result.cost_cny_used == Decimal("0.10")
    assert isinstance(result.cost_cny_used, Decimal)
```

- [x] **Step 3: Run tests and verify float-based code fails**

Run:

```powershell
uv run --python 3.11 pytest tests/contracts/test_budgets.py tests/agents/test_coordinator.py -v
```

Expected: budget contract import fails and the existing coordinator returns `float` cost.

- [x] **Step 4: Implement the budget envelope**

```python
# bogda/src/bogda/contracts/budgets.py
from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self

from pydantic import (
    BaseModel,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from bogda.contracts.tasks import ModelTier


class BudgetSource(StrEnum):
    RUN = "run"
    PROJECT = "project"
    GLOBAL_DEFAULT = "global-default"


class RunBudgetEnvelope(BaseModel):
    schema_version: Literal[1] = 1
    currency: Literal["CNY"] = "CNY"
    expected_cost: Decimal = Field(ge=0)
    authorized_ceiling: Decimal = Field(ge=0)
    minimum_remaining: Decimal = Field(ge=0)
    requested_tier: ModelTier
    fallback_tier: ModelTier | None = None
    budget_source: BudgetSource
    pricing_version: str = Field(min_length=1)

    @field_validator(
        "expected_cost", "authorized_ceiling", "minimum_remaining", mode="before"
    )
    @classmethod
    def reject_float_money(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("money values must not be floats")
        return value

    @field_serializer("expected_cost", "authorized_ceiling", "minimum_remaining")
    def serialize_money(self, value: Decimal) -> str:
        return format(value, "f")

    @model_validator(mode="after")
    def validate_envelope(self) -> Self:
        if self.expected_cost > self.authorized_ceiling:
            raise ValueError("expected_cost cannot exceed authorized_ceiling")
        if self.fallback_tier not in (None, ModelTier.FLASH):
            raise ValueError("fallback_tier must be flash or null")
        return self
```

Export `BudgetSource` and `RunBudgetEnvelope` from `bogda.contracts`.

- [x] **Step 5: Replace existing float money with Decimal**

Apply these exact type changes:

```python
# bogda/src/bogda/agents/contracts.py
from decimal import Decimal
from pydantic import BaseModel, field_validator

class AgentBudget(BaseModel):
    max_steps: int
    max_model_calls: int
    max_cost_cny: Decimal
    allowed_experiment_types: tuple[str, ...] = ("shell",)

    @field_validator("max_cost_cny", mode="before")
    @classmethod
    def reject_float_money(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("money values must not be floats")
        return value

class CoordinatorResult(BaseModel):
    status: str
    checkpoint: CheckpointKind | None = None
    scientific_status: ScientificStatus = ScientificStatus.UNREVIEWED
    plan: ResearchPlan | None = None
    proposal: ExperimentProposal | None = None
    steps_used: int = 0
    model_calls_used: int = 0
    cost_cny_used: Decimal = Decimal("0")
```

```python
# bogda/src/bogda/agents/coordinator.py
from decimal import Decimal

def _money(value: Decimal | str | int) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))

# __init__
self.cost_per_call = _money(cost_per_call)
self.cost_cny_used = Decimal("0")
```

Change the constructor annotation to `cost_per_call: Decimal | str | int = Decimal("0.5")`. In `make_coordinator`, replace defaults `10.0` and `0.5` with strings `"10.0"` and `"0.5"`; in `tests/flows/test_research_cycle.py`, replace `max_cost_cny=10.0` with `max_cost_cny="10.0"`. No later calculation may cast the amount back to float.

- [x] **Step 6: Run focused and research-cycle tests**

Run:

```powershell
uv run --python 3.11 pytest tests/contracts/test_budgets.py tests/agents/test_coordinator.py tests/flows/test_research_cycle.py -v
```

Expected: all tests pass; budget exhaustion behavior and human checkpoints remain unchanged.

- [x] **Step 7: Commit the task**

```powershell
git add bogda/src/bogda/contracts/budgets.py bogda/src/bogda/contracts/__init__.py bogda/src/bogda/agents/contracts.py bogda/src/bogda/agents/coordinator.py bogda/tests/contracts/test_budgets.py bogda/tests/agents/test_coordinator.py bogda/tests/flows/test_research_cycle.py
git commit -m "refactor(bogda): use decimal budget contracts"
```

---

### Task 3: Versioned JobRequest Integration

**Preferred implementer:** SOL；该任务横跨现有纵向切片，Luna 可补充独立测试但不独立决定兼容语义。

**Files:**
- Modify: `bogda/src/bogda/contracts/models.py`
- Modify: `bogda/src/bogda/contracts/__init__.py`
- Modify: `bogda/tests/contracts/test_models.py`
- Modify: `bogda/tests/control/test_cli.py`
- Modify: `bogda/tests/flows/test_shell_job.py`
- Modify: `bogda/tests/flows/test_research_checkpoint.py`
- Modify: `bogda/tests/integration/test_vertical_slice.py`

**Interfaces:**
- Consumes: Task 1 `TaskIntent`, `ModelTier`, `ExecutorKind`, `SchedulePolicy`; Task 2 `RunBudgetEnvelope`.
- Produces: `JobRequest.schema_version == 1`, plus request-bound `intent`, `model_tier`, `executor`, `budget` and `schedule_policy` values persisted in the request; this does not imply an immutable Pydantic object.
- Existing shell callers remain valid through conservative defaults: execute + auto + shell + no paid budget.
- Dsh requests require a budget envelope; an explicit model tier must match `budget.requested_tier`.

- [x] **Step 1: Add failing JobRequest contract tests**

Append to `bogda/tests/contracts/test_models.py`:

```python
import pytest
from pydantic import ValidationError

from bogda.contracts import ExecutorKind, ModelTier, TaskIntent


def test_existing_shell_request_gets_versioned_conservative_defaults() -> None:
    request = JobRequest(
        job_id="job-1",
        project_id="project-1",
        task_type="shell",
        resource_class=ResourceClass.CPU,
        autonomy_mode=AutonomyMode.SUPERVISED,
    )
    assert request.schema_version == 1
    assert request.intent is TaskIntent.EXECUTE
    assert request.model_tier is ModelTier.AUTO
    assert request.executor is ExecutorKind.SHELL
    assert request.budget is None


def test_dsh_request_requires_budget() -> None:
    with pytest.raises(ValidationError, match="dsh requests require a budget"):
        JobRequest(
            job_id="job-2",
            project_id="project-1",
            task_type="legacy-orchestra-task",
            resource_class=ResourceClass.CPU,
            autonomy_mode=AutonomyMode.SUPERVISED,
            executor="dsh",
            model_tier="pro",
        )
```

- [x] **Step 2: Run focused tests and confirm missing fields**

Run:

```powershell
uv run --python 3.11 pytest tests/contracts/test_models.py -v
```

Expected: assertions fail because `JobRequest` does not expose the new fields.

- [x] **Step 3: Extend JobRequest without changing existing shell call sites**

```python
# additions in bogda/src/bogda/contracts/models.py
from typing import Any, Literal, Self
from pydantic import BaseModel, Field, model_validator

from bogda.contracts.budgets import RunBudgetEnvelope
from bogda.contracts.tasks import (
    ExecutorKind,
    ModelTier,
    SchedulePolicy,
    TaskIntent,
)

class JobRequest(BaseModel):
    schema_version: Literal[1] = 1
    job_id: str
    project_id: str
    task_type: str
    resource_class: ResourceClass
    autonomy_mode: AutonomyMode
    policy_revision: int = Field(default=0, ge=0)
    intent: TaskIntent = TaskIntent.EXECUTE
    model_tier: ModelTier = ModelTier.AUTO
    executor: ExecutorKind = ExecutorKind.SHELL
    budget: RunBudgetEnvelope | None = None
    schedule_policy: SchedulePolicy = Field(default_factory=SchedulePolicy)
    parameters: dict[str, Any] = Field(default_factory=dict)
    retryable: bool = False
    expected_artifacts: tuple[ArtifactSpec, ...] = ()

    @model_validator(mode="after")
    def validate_paid_execution(self) -> Self:
        if self.executor is ExecutorKind.DSH and self.budget is None:
            raise ValueError("dsh requests require a budget envelope")
        if (
            self.budget is not None
            and self.model_tier is not ModelTier.AUTO
            and self.budget.requested_tier is not self.model_tier
        ):
            raise ValueError("model_tier must match budget.requested_tier")
        return self
```

Keep the existing model fields once; do not duplicate the class body. Update `bogda.contracts.__all__` only for names not already exported.

- [x] **Step 4: Add JSON round-trip and mismatch tests**

```python
def test_versioned_request_round_trips_without_changing_frozen_axes() -> None:
    request = JobRequest(
        job_id="job-3",
        project_id="project-1",
        task_type="shell",
        resource_class="cpu",
        autonomy_mode="supervised",
        intent="audit",
        model_tier="auto",
    )
    restored = JobRequest.model_validate_json(request.model_dump_json())
    assert restored == request
    assert restored.intent is TaskIntent.AUDIT
```

- [x] **Step 5: Run all direct JobRequest consumers**

Run:

```powershell
uv run --python 3.11 pytest tests/contracts/test_models.py tests/control/test_cli.py tests/executors/test_shell.py tests/flows/test_shell_job.py tests/flows/test_research_checkpoint.py tests/integration/test_vertical_slice.py -v
```

Expected: all tests pass without editing production deployment files.

- [x] **Step 6: Commit the task**

```powershell
git add bogda/src/bogda/contracts/models.py bogda/src/bogda/contracts/__init__.py bogda/tests/contracts/test_models.py bogda/tests/control/test_cli.py bogda/tests/flows/test_shell_job.py bogda/tests/flows/test_research_checkpoint.py bogda/tests/integration/test_vertical_slice.py
git commit -m "feat(bogda): version task request axes"
```

---

### Task 4: Orchestra Task Card 单向兼容转换

**Preferred implementer:** Luna；SOL 复核与旧 parser 的 fixture 等价性和无运行时依赖。

**Files:**
- Create: `bogda/src/bogda/compat/__init__.py`
- Create: `bogda/src/bogda/compat/orchestra_taskfile.py`
- Create: `bogda/tests/compat/test_orchestra_taskfile.py`

**Interfaces:**
- Produces: `LegacyOrchestraTask`, `parse_orchestra_task(path)`, `to_job_request(card, *, project_id, autonomy_mode, resource_class, budget)`.
- Parser accepts exactly the existing Orchestra keys; unknown/duplicate fields and unsafe relative paths fail closed.
- Converter maps `mode -> intent`, `model None -> auto`, `model flash|pro -> model_tier`, and preserves old execution details under namespaced `parameters["legacy_orchestra"]`.
- The module must not import anything under `orchestra`.

- [x] **Step 1: Write failing compatibility tests using an in-test card**

```python
from pathlib import Path

import pytest

from bogda.compat import parse_orchestra_task, to_job_request
from bogda.contracts import AutonomyMode, ModelTier, ResourceClass, TaskIntent


CARD = """# T-20260828-audit
executor: dsh
net: required
result: T-20260828-audit
timeout: 900
model: pro
mode: audit
detail: deep
required_outputs: review.json
json_outputs: review.json
---
review the evidence
"""


def test_legacy_card_maps_mode_and_model_without_importing_orchestra(tmp_path: Path) -> None:
    path = tmp_path / "T-20260828-audit.md"
    path.write_text(CARD, encoding="utf-8")
    card = parse_orchestra_task(path)
    request = to_job_request(
        card,
        project_id="bogda-main",
        autonomy_mode=AutonomyMode.SUPERVISED,
        resource_class=ResourceClass.CPU,
        budget={
            "expected_cost": "1",
            "authorized_ceiling": "2",
            "minimum_remaining": "10",
            "requested_tier": "pro",
            "fallback_tier": "flash",
            "budget_source": "project",
            "pricing_version": "deepseek-cn-2026-08-28",
        },
    )
    assert request.intent is TaskIntent.AUDIT
    assert request.model_tier is ModelTier.PRO
    assert request.parameters["legacy_orchestra"]["body"] == "review the evidence"
    assert request.expected_artifacts[0].path == "review.json"


def test_legacy_unknown_key_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "T-bad.md"
    path.write_text(CARD.replace("mode: audit", "priority: urgent"), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown field"):
        parse_orchestra_task(path)
```

- [x] **Step 2: Run the test and verify missing compatibility module**

Run:

```powershell
uv run --python 3.11 pytest tests/compat/test_orchestra_taskfile.py -v
```

Expected: collection fails because `bogda.compat` does not exist.

- [x] **Step 3: Implement the isolated legacy model and parser**

The production module must define these exact interfaces:

```python
class LegacyOrchestraTask(BaseModel):
    slug: str
    executor: ExecutorKind
    net: Literal["required", "optional"]
    result_dir: str
    timeout: int = Field(default=3600, ge=1, le=86400)
    body: str = Field(min_length=1)
    model: Literal["flash", "pro"] | None = None
    depends_on: tuple[str, ...] = ()
    mode: TaskIntent = TaskIntent.EXECUTE
    detail: Literal["brief", "standard", "deep"] = "standard"
    required_outputs: tuple[str, ...] = ()
    json_outputs: tuple[str, ...] = ()
    validation_output: str | None = None
    validator: Literal["radar-fetch", "radar-rank", "radar-render"] | None = None


_REQUIRED = {"executor", "net", "result"}
_ALLOWED = {
    "executor", "net", "result", "timeout", "model", "depends_on", "mode",
    "detail", "required_outputs", "json_outputs", "validation_output", "validator",
}


def _csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _safe_relative(value: str, field: str, source: Path) -> None:
    candidates = (PurePosixPath(value), PureWindowsPath(value))
    if value in ("", ".") or any(
        candidate.is_absolute() or candidate.drive or ".." in candidate.parts
        for candidate in candidates
    ):
        raise ValueError(f"{source}: {field} must be a safe relative path")


def parse_orchestra_task(path: str | Path) -> LegacyOrchestraTask:
    source = Path(path)
    header, separator, body = source.read_text(encoding="utf-8").partition("\n---\n")
    if not separator:
        raise ValueError(f"{source}: missing task body separator")
    fields: dict[str, str] = {}
    for raw_line in header.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"{source}: invalid header line")
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if key in fields:
            raise ValueError(f"{source}: duplicate field {key}")
        if key not in _ALLOWED:
            raise ValueError(f"{source}: unknown field {key}")
        fields[key] = value
    missing = sorted(_REQUIRED - fields.keys())
    if missing:
        raise ValueError(f"{source}: missing fields {missing}")
    body = body.strip()
    if not body:
        raise ValueError(f"{source}: empty body")
    try:
        timeout = int(fields.get("timeout", "3600"))
    except ValueError:
        raise ValueError(f"{source}: timeout must be an integer") from None
    depends_on = _csv(fields.get("depends_on", ""))
    if source.stem in depends_on:
        raise ValueError(f"{source}: self dependency")
    if len(depends_on) != len(set(depends_on)):
        raise ValueError(f"{source}: duplicate dependency")
    required_outputs = _csv(fields.get("required_outputs", ""))
    json_outputs = _csv(fields.get("json_outputs", ""))
    validation_output = fields.get("validation_output") or None
    validator = fields.get("validator") or None
    _safe_relative(fields["result"], "result", source)
    for value in required_outputs:
        _safe_relative(value, "required_outputs", source)
    for value in json_outputs:
        _safe_relative(value, "json_outputs", source)
    if validation_output is not None:
        _safe_relative(validation_output, "validation_output", source)
    if set(json_outputs) - set(required_outputs):
        raise ValueError(f"{source}: json_outputs must also be required_outputs")
    if validation_output is not None and validation_output not in json_outputs:
        raise ValueError(f"{source}: validation_output must also be a json_output")
    if validator is not None and not required_outputs:
        raise ValueError(f"{source}: validator requires required_outputs")
    return LegacyOrchestraTask(
        slug=source.stem,
        executor=fields["executor"],
        net=fields["net"],
        result_dir=fields["result"],
        timeout=timeout,
        body=body,
        model=fields.get("model") or None,
        depends_on=depends_on,
        mode=fields.get("mode", "execute"),
        detail=fields.get("detail", "standard"),
        required_outputs=required_outputs,
        json_outputs=json_outputs,
        validation_output=validation_output,
        validator=validator,
    )


def to_job_request(
    card: LegacyOrchestraTask,
    *,
    project_id: str,
    autonomy_mode: AutonomyMode,
    resource_class: ResourceClass,
    budget: RunBudgetEnvelope | dict | None,
) -> JobRequest:
    parsed_budget = (
        None if budget is None else RunBudgetEnvelope.model_validate(budget)
    )
    return JobRequest(
        job_id=card.slug,
        project_id=project_id,
        task_type="legacy-orchestra-task",
        resource_class=resource_class,
        autonomy_mode=autonomy_mode,
        intent=card.mode,
        model_tier=ModelTier(card.model or "auto"),
        executor=card.executor,
        budget=parsed_budget,
        parameters={
            "legacy_orchestra": {
                "net": card.net,
                "result_dir": card.result_dir,
                "timeout": card.timeout,
                "body": card.body,
                "depends_on": list(card.depends_on),
                "detail": card.detail,
                "json_outputs": list(card.json_outputs),
                "validation_output": card.validation_output,
                "validator": card.validator,
            }
        },
        expected_artifacts=tuple(
            ArtifactSpec(path=value) for value in card.required_outputs
        ),
    )
```

The module imports its stdlib path types and the referenced Bogda contracts explicitly. It must not import or monkeypatch the old Orchestra module.

- [x] **Step 4: Add parity fixtures for all five intents and both model tiers**

Use `pytest.mark.parametrize` with:

```python
@pytest.mark.parametrize("intent", ["execute", "explore", "decide", "audit", "brief"])
@pytest.mark.parametrize("tier", ["flash", "pro"])
def test_all_legacy_modes_and_tiers_convert(intent: str, tier: str, tmp_path: Path) -> None:
    text = CARD.replace("mode: audit", f"mode: {intent}").replace(
        "model: pro", f"model: {tier}"
    )
    path = tmp_path / f"T-{intent}-{tier}.md"
    path.write_text(text, encoding="utf-8")
    request = to_job_request(
        parse_orchestra_task(path),
        project_id="bogda-main",
        autonomy_mode=AutonomyMode.SUPERVISED,
        resource_class=ResourceClass.CPU,
        budget={
            "expected_cost": "1",
            "authorized_ceiling": "2",
            "minimum_remaining": "10",
            "requested_tier": tier,
            "fallback_tier": "flash" if tier == "pro" else None,
            "budget_source": "project",
            "pricing_version": "deepseek-cn-2026-08-28",
        },
    )
    assert request.intent is TaskIntent(intent)
    assert request.model_tier is ModelTier(tier)
```

Also cover duplicate keys, parent/absolute paths, self-dependency, undeclared JSON outputs, invalid validator coupling and empty bodies. Use the old tests as behavioral reference but keep fixtures in Bogda.

- [x] **Step 5: Run compatibility and existing Orchestra parser tests separately**

Run:

```powershell
Set-Location D:\pythonProject\bogda
uv run --python 3.11 pytest tests/compat/test_orchestra_taskfile.py -v
Set-Location D:\pythonProject\orchestra
python -m unittest broker.tests.test_taskfile -v
```

Expected: both suites pass; Bogda works without adding Orchestra to its import path.

- [x] **Step 6: Commit the task**

```powershell
Set-Location D:\pythonProject
git add bogda/src/bogda/compat bogda/tests/compat/test_orchestra_taskfile.py
git commit -m "feat(bogda): import legacy orchestra task cards"
```

---

### Task 5: Versioned Structured Run Event Schema

**Preferred implementer:** Luna；SOL 复核事件可配对性、金额精度和秘密字段边界。

**Files:**
- Create: `bogda/src/bogda/contracts/events.py`
- Modify: `bogda/src/bogda/contracts/__init__.py`
- Create: `bogda/tests/contracts/test_events.py`

**Interfaces:**
- Consumes: `TaskIntent`, `ModelTier` and Decimal money conventions.
- Produces: `RunEventType`, `RunEventV1`.
- This task defines schema only. It does not append files, publish Prefect Artifacts or call a model.
- `model_call_started|model_call_finished` require `call_id`; tier changes require requested/effective tiers; timestamps must be timezone-aware.

- [x] **Step 1: Write failing event-schema tests**

```python
from decimal import Decimal

import pytest
from pydantic import ValidationError

from bogda.contracts import RunEventType, RunEventV1


def test_tier_downgrade_event_round_trips_money_as_strings() -> None:
    event = RunEventV1(
        event="tier_downgraded",
        run_id="run-123",
        intent="explore",
        requested_tier="pro",
        effective_tier="flash",
        reason="insufficient_budget",
        balance_cny="13.42",
        reserved_cny="5.00",
        minimum_remaining_cny="10.00",
        snapshot_age_seconds=18,
        occurred_at="2026-08-28T20:10:00+08:00",
    )
    payload = event.model_dump(mode="json")
    assert event.balance_cny == Decimal("13.42")
    assert payload["balance_cny"] == "13.42"
    assert event.event is RunEventType.TIER_DOWNGRADED


def test_model_call_event_requires_call_id() -> None:
    with pytest.raises(ValidationError, match="call_id is required"):
        RunEventV1(
            event="model_call_started",
            run_id="run-123",
            occurred_at="2026-08-28T20:10:00+08:00",
        )
```

- [x] **Step 2: Run focused test and verify the event types are absent**

Run:

```powershell
Set-Location D:\pythonProject\bogda
uv run --python 3.11 pytest tests/contracts/test_events.py -v
```

Expected: collection fails because `RunEventType` and `RunEventV1` are not exported.

- [x] **Step 3: Implement the versioned event envelope**

```python
# bogda/src/bogda/contracts/events.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from bogda.contracts.tasks import ModelTier, TaskIntent


class RunEventType(StrEnum):
    BUDGET_SNAPSHOT = "budget_snapshot"
    BUDGET_RESERVED = "budget_reserved"
    BUDGET_RELEASED = "budget_released"
    ROUTE_SELECTED = "route_selected"
    TIER_UPGRADE_REQUESTED = "tier_upgrade_requested"
    TIER_DOWNGRADED = "tier_downgraded"
    MODEL_CALL_STARTED = "model_call_started"
    MODEL_CALL_FINISHED = "model_call_finished"
    BUDGET_PAUSED = "budget_paused"
    BUDGET_RESUMED = "budget_resumed"
    BUDGET_OVERRIDE_APPROVED = "budget_override_approved"


class RunEventV1(BaseModel):
    schema_version: Literal[1] = 1
    event_id: UUID = Field(default_factory=uuid4)
    event: RunEventType
    run_id: str = Field(min_length=1)
    call_id: str | None = None
    occurred_at: datetime
    intent: TaskIntent | None = None
    requested_tier: ModelTier | None = None
    effective_tier: ModelTier | None = None
    reason: str | None = None
    balance_cny: Decimal | None = Field(default=None, ge=0)
    reserved_cny: Decimal | None = Field(default=None, ge=0)
    minimum_remaining_cny: Decimal | None = Field(default=None, ge=0)
    snapshot_age_seconds: int | None = Field(default=None, ge=0)
    prompt_hash: str | None = None
    prompt_artifact: str | None = None
    usage_reference: str | None = None

    @field_validator(
        "balance_cny", "reserved_cny", "minimum_remaining_cny", mode="before"
    )
    @classmethod
    def reject_float_money(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("money values must not be floats")
        return value

    @field_serializer("balance_cny", "reserved_cny", "minimum_remaining_cny")
    def serialize_money(self, value: Decimal | None) -> str | None:
        return None if value is None else format(value, "f")

    @model_validator(mode="after")
    def validate_event(self) -> Self:
        if self.occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")
        if self.event in {
            RunEventType.MODEL_CALL_STARTED,
            RunEventType.MODEL_CALL_FINISHED,
        } and not self.call_id:
            raise ValueError("call_id is required for model call events")
        if self.event in {
            RunEventType.TIER_UPGRADE_REQUESTED,
            RunEventType.TIER_DOWNGRADED,
            RunEventType.ROUTE_SELECTED,
        } and (self.requested_tier is None or self.effective_tier is None):
            raise ValueError("tier events require requested_tier and effective_tier")
        return self
```

Export both event names through `bogda.contracts`.

- [x] **Step 4: Add pairing and secret-surface tests**

Add tests that `model_call_started` and `model_call_finished` accept the same `call_id`, and assert the schema has no `headers`, `api_key`, `authorization`, `prompt` or `response` fields. Full prompt/output belongs to referenced artifacts in a later plan.

- [x] **Step 5: Run all contract tests**

Run:

```powershell
uv run --python 3.11 pytest tests/contracts -v
```

Expected: all contract tests pass and JSON monetary fields are strings.

- [x] **Step 6: Commit the task**

```powershell
git add bogda/src/bogda/contracts/events.py bogda/src/bogda/contracts/__init__.py bogda/tests/contracts/test_events.py
git commit -m "feat(bogda): define versioned run events"
```

---

### Task 6: Contract Documentation、Full Verification 与 Phase-B Handoff

**Preferred implementer:** SOL；Luna 可运行独立测试矩阵，但不得单独宣布阶段完成。

**Files:**
- Modify: `bogda/README.md`
- Modify: `docs/superpowers/plans/2026-08-28-bogda-contract-foundation.md`
- Create: `docs/reports/2026-08-28-bogda-contract-foundation-acceptance.md`

**Interfaces:**
- Produces: 面向维护者的 schema v1 入口、旧字段映射表、测试证据和下一阶段可消费签名。
- Does not change production deployment or authorize Phase B.

- [x] **Step 1: Add a concise contract section to Bogda README**

Document these exact facts:

```markdown
## Intelligent collaboration contracts

- `autonomy_mode` controls authority.
- `intent` controls cognitive behavior.
- `model_tier` controls reasoning capacity, never permissions.
- `executor` selects the adapter.
- Paid dsh requests carry a request-bound `RunBudgetEnvelope` snapshot; money uses Decimal strings.
- Legacy Orchestra cards enter only through `bogda.compat` and become Bogda `JobRequest` objects.
```

- [x] **Step 2: Run the Bogda non-integration suite**

Run:

```powershell
Set-Location D:\pythonProject\bogda
uv run --python 3.11 pytest -m "not integration" -q
```

Expected: zero failures.

- [x] **Step 3: Run the local Prefect integration suite**

Run:

```powershell
uv run --python 3.11 pytest -m integration -v
```

Expected: zero failures; existing shell vertical slice remains operational.

- [x] **Step 4: Run compatibility and repository hygiene checks**

Run:

```powershell
Set-Location D:\pythonProject\orchestra
python -m unittest broker.tests.test_taskfile -v
Set-Location D:\pythonProject
git diff --check
git status --short
```

Expected: old parser tests pass; no whitespace errors; only intended files are modified. The user-owned untracked maintainability report must remain uncommitted unless the user separately asks to add it.

- [x] **Step 5: Write the acceptance report with exact evidence**

The report must include:

```markdown
# Bogda Contract Foundation Acceptance

- Commit SHAs for Tasks 1–6
- Focused and full test commands with pass counts
- Public contract names and schema version
- Confirmation that Bogda imports no Orchestra package
- Confirmation that all money fields serialize as Decimal strings
- Confirmation that no RK3528, production Prefect, systemd or Console writes occurred; local integration tests may use ephemeral Prefect test state
- Phase B inputs: JobRequest, RunBudgetEnvelope, SchedulePolicy, RunEventV1
```

- [x] **Step 6: Mark this plan's completed checkboxes and commit documentation**

```powershell
git add bogda/README.md docs/superpowers/plans/2026-08-28-bogda-contract-foundation.md docs/reports/2026-08-28-bogda-contract-foundation-acceptance.md
git commit -m "docs(bogda): accept contract foundation"
```

- [x] **Step 7: Stop before Phase B**

SOL reviews the acceptance report and creates a new plan for UsagePort, pricing, workload estimation, BudgetGuard and reservations from the actual merged interfaces. Do not begin DeepSeek or frontend integration in the same task.

## Review and Release Gate

Every implementation task requires: focused red/green evidence, related full tests, `git diff --check`, one isolated commit and SOL review. A Luna result is input to SOL, not completion evidence by itself.

This plan is complete only when Task 1–6 are checked, all Bogda tests pass, the Orchestra parser suite still passes, the acceptance report exists, and no production files or devices were changed. Completion authorizes planning Phase B only; it does not authorize any live usage API, dsh, Prefect write, Console write or Gate transition.
