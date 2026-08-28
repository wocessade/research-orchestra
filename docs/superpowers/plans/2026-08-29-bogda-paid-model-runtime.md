# Bogda Paid Model Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a provider-neutral paid-model call vertical slice that routes Flash/Pro safely, archives prompts before execution, invokes dsh through an adapter, reconciles exact usage when available, and suspends Prefect runs without holding a worker when budget admission pauses.

**Architecture:** Keep policy, persistence, execution, and orchestration separate under `bogda.model_runtime`. The coordinator consumes the existing frozen `JobRequest` and `RunBudgetEnvelope`, delegates balance/reservation work to `BudgetAdmissionService`, and emits `RunEventV1` through the existing sink. A concrete dsh subprocess adapter owns CLI/patch details; fake ports prove all paid behavior without a live call.

**Tech Stack:** Python 3.11, Pydantic 2, Prefect 3.8.3, pytest, existing Bogda budget/event contracts, dsh headless CLI.

**Spec:** `docs/superpowers/specs/2026-08-28-bogda-intelligent-collaboration-budget-design.md`

## Global Constraints

- Bogda must not import the Orchestra package, read Broker SQLite, or depend on Orchestra's task scanner.
- `autonomy_mode`, `intent`, `model_tier`, and `executor` remain orthogonal; Pro never expands tools, permissions, or autonomy.
- Every dsh request consumes a frozen `RunBudgetEnvelope`; money is `Decimal` and JSON money remains a string.
- A paid call is forbidden until prompt archival succeeds and `BudgetAdmissionService.admit(...)` returns an active reservation.
- `decide` and `audit` never silently downgrade from Pro to Flash; low-risk fallback is limited to `execute`, `brief`, and `explore` and requires an explicit frozen Flash fallback.
- Every route, call start, call finish/unknown result, pause, release, and reconciliation is represented by `RunEventV1`; ordinary logs never contain the full prompt, model output, credentials, authorization headers, or `X-Monitor-Token`.
- Missing usage after a possibly-started call is not zero usage: preserve the reservation, emit an unknown-usage result, and forbid automatic retry until reconciliation.
- Prefect waiting uses `suspend_flow_run`, not process sleep or a resident model session; deployment and production wiring remain out of scope.
- No live dsh, DeepSeek, usage-monitor, Prefect server, systemd, device, 3100/3101, or production-data mutation is authorized by this plan.
- Phase C does not implement frontend windows, durable cross-process ledgers/outboxes, a generic plugin framework, or unrelated maintainability cleanup.
- Prefer the smallest implementation that satisfies observed contracts; do not add speculative tamper, retry, or recovery mechanisms.

---

### Task 1: Runtime Contracts and Prompt Archive

**Files:**
- Create: `bogda/src/bogda/model_runtime/__init__.py`
- Create: `bogda/src/bogda/model_runtime/contracts.py`
- Create: `bogda/src/bogda/model_runtime/archive.py`
- Create: `bogda/tests/model_runtime/test_archive.py`

**Interfaces:**
- Consumes: `ModelTier` and caller-selected archive root; audited time remains `RunEventV1.occurred_at`.
- Produces: `PromptArtifactV1`, `DshTokenUsageV1`, `ModelCallOutcome`, `ModelCallRequest`, `ModelCallResult`, `ModelExecutionPort`, `UsageReceiptPort`, `PromptArchivePort`, and `FilePromptArchive.archive(run_id, call_id, prompt)`.

- [ ] **Step 1: Write failing contract and archive tests**

```python
def test_archive_writes_exact_prompt_and_returns_hash(tmp_path):
    archive = FilePromptArchive(tmp_path)
    artifact = archive.archive("run-1", "call-1", "审计这个结果")
    assert Path(artifact.path).read_text(encoding="utf-8") == "审计这个结果"
    assert artifact.sha256 == hashlib.sha256("审计这个结果".encode()).hexdigest()

def test_archive_is_idempotent_only_for_same_content(tmp_path):
    archive = FilePromptArchive(tmp_path)
    assert archive.archive("run-1", "call-1", "same") == archive.archive(
        "run-1", "call-1", "same"
    )
    with pytest.raises(PromptArchiveConflictError):
        archive.archive("run-1", "call-1", "different")

def test_usage_rejects_float_and_serializes_decimal_cost_as_string():
    with pytest.raises(ValidationError):
        DshTokenUsageV1(input_tokens=1, cache_read_tokens=0,
                        output_tokens=1, actual_cost_cny=0.1)
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `uv run --extra dev --python 3.11 pytest tests/model_runtime/test_archive.py -q`

Expected: collection fails because `bogda.model_runtime` does not exist.

- [ ] **Step 3: Implement strict, focused contracts**

```python
class ModelCallOutcome(StrEnum):
    FINISHED = "finished"
    NOT_STARTED = "not_started"
    USAGE_UNKNOWN = "usage_unknown"

class DshTokenUsageV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    input_tokens: int = Field(ge=0)
    cache_read_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    actual_cost_cny: Decimal | None = Field(default=None, ge=0)
    reference: str = Field(min_length=1)

class ModelExecutionPort(Protocol):
    def invoke(self, request: ModelCallRequest) -> ModelCallResult: ...

class UsageReceiptPort(Protocol):
    def read(self, attempt_dir: Path) -> DshTokenUsageV1 | None: ...

class PromptArchivePort(Protocol):
    def archive(self, run_id: str, call_id: str, prompt: str) -> PromptArtifactV1: ...
```

`FilePromptArchive` stores `{root}/{run_id}/{call_id}.prompt.md`, rejects path separators in identifiers, writes UTF-8 through exclusive create, and returns the existing artifact only when its SHA-256 equals the requested prompt. It does not scan for hypothetical secret formats; callers must provide a secret-free research prompt.

- [ ] **Step 4: Run focused and contract regressions**

Run: `uv run --extra dev --python 3.11 pytest tests/model_runtime/test_archive.py tests/contracts -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add bogda/src/bogda/model_runtime bogda/tests/model_runtime/test_archive.py
git commit -m "feat(bogda): archive paid model prompts"
```

---

### Task 2: Frozen Model Routing Policy

**Files:**
- Create: `bogda/src/bogda/model_runtime/routing.py`
- Create: `bogda/tests/model_runtime/test_routing.py`
- Modify: `bogda/src/bogda/model_runtime/__init__.py`

**Interfaces:**
- Consumes: `JobRequest.intent`, `JobRequest.model_tier`, `JobRequest.budget.requested_tier`, `fallback_tier`, Pro availability, and low-risk fallback policy.
- Produces: `ModelRouter.select(request, *, pro_available, allow_low_risk_fallback) -> RouteDecision` with stable `RouteDecisionKind` values `selected`, `downgraded`, and `pro_required`.

- [ ] **Step 1: Write the routing matrix tests**

```python
@pytest.mark.parametrize("intent", [TaskIntent.DECIDE, TaskIntent.AUDIT])
def test_pro_unavailable_never_silently_downgrades_high_risk_intent(intent):
    decision = ModelRouter().select(pro_request(intent), pro_available=False,
                                    allow_low_risk_fallback=True)
    assert decision.kind is RouteDecisionKind.PRO_REQUIRED
    assert decision.effective_tier is None

@pytest.mark.parametrize("intent", [TaskIntent.EXECUTE, TaskIntent.BRIEF, TaskIntent.EXPLORE])
def test_low_risk_pro_can_use_explicit_frozen_flash_fallback(intent):
    decision = ModelRouter().select(pro_request(intent, fallback=ModelTier.FLASH),
                                    pro_available=False,
                                    allow_low_risk_fallback=True)
    assert decision.kind is RouteDecisionKind.DOWNGRADED
    assert decision.effective_tier is ModelTier.FLASH
```

Also test explicit Flash, available Pro, disabled fallback, missing budget, and that `model_tier=auto` uses the concrete tier already frozen in the envelope. For `auto` + `decide/audit`, a Flash envelope is invalid; explicit `model_tier=flash` remains a human lock and is not rewritten.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `uv run --extra dev --python 3.11 pytest tests/model_runtime/test_routing.py -q`

Expected: import failure for the new router.

- [ ] **Step 3: Implement one centralized policy table**

```python
LOW_RISK_FALLBACK_INTENTS = frozenset({
    TaskIntent.EXECUTE, TaskIntent.BRIEF, TaskIntent.EXPLORE,
})

def select(self, request: JobRequest, *, pro_available: bool,
           allow_low_risk_fallback: bool) -> RouteDecision:
    envelope = request.budget
    if envelope is None:
        raise ValueError("paid model routing requires a budget envelope")
    requested = envelope.requested_tier
    # Validate the frozen AUTO/high-risk invariant, then select or pause.
```

Do not inspect Orchestra routing JSON at runtime and do not make model tier change autonomy or tool permissions.

- [ ] **Step 4: Run focused and existing task-contract tests**

Run: `uv run --extra dev --python 3.11 pytest tests/model_runtime/test_routing.py tests/contracts/test_models.py tests/contracts/test_tasks.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add bogda/src/bogda/model_runtime/routing.py bogda/src/bogda/model_runtime/__init__.py bogda/tests/model_runtime/test_routing.py
git commit -m "feat(bogda): route frozen model tiers"
```

---

### Task 3: dsh Headless Adapter

**Files:**
- Create: `bogda/src/bogda/model_runtime/dsh.py`
- Create: `bogda/config/dsh-patches/flash.yml`
- Create: `bogda/config/dsh-patches/pro.yml`
- Create: `bogda/tests/model_runtime/test_dsh.py`
- Modify: `bogda/src/bogda/model_runtime/__init__.py`

**Interfaces:**
- Consumes: `ModelCallRequest`, explicit Flash/Pro patch paths, `dsh --profile headless`, caller-selected attempt directory, optional `UsageReceiptPort.read(attempt_dir)`.
- Produces: `DshCliAdapter.invoke(request) -> ModelCallResult` and `JsonUsageReceiptReader.read(attempt_dir) -> DshTokenUsageV1 | None` for a provider-neutral optional `usage.json` sidecar.

- [ ] **Step 1: Write argv, output, timeout, and usage tests with a fake command runner**

```python
def test_flash_invocation_uses_owned_patch_and_never_shell_string(tmp_path):
    runner = FakeRunner(returncode=0, stdout="answer", stderr="")
    adapter = adapter_for(tmp_path, runner)
    result = adapter.invoke(call_request(tmp_path, ModelTier.FLASH))
    assert runner.argv[:3] == ["dsh", "--profile", "headless"]
    assert runner.argv[3:5] == ["--patch", str(tmp_path / "flash.yml")]
    assert runner.argv[-1] == "secret-free prompt"
    assert result.outcome is ModelCallOutcome.FINISHED

def test_nonzero_after_spawn_is_usage_unknown_without_receipt(tmp_path):
    result = adapter_for(tmp_path, FakeRunner(returncode=2)).invoke(call_request(...))
    assert result.outcome is ModelCallOutcome.USAGE_UNKNOWN
```

Test missing executable as `NOT_STARTED`, timeout after spawn as `USAGE_UNKNOWN`, missing patch as validation failure before runner invocation, exact stdout artifact, bounded stderr artifact, and a structured fake receipt round-trip. Tests must not invoke real dsh.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `uv run --extra dev --python 3.11 pytest tests/model_runtime/test_dsh.py -q`

Expected: import failure.

- [ ] **Step 3: Implement the adapter without importing Orchestra**

```python
argv = [self.command, "--profile", self.profile,
        "--patch", str(self.patch_for(request.effective_tier)), request.prompt]
completed = self.runner.run(argv, cwd=request.attempt_dir,
                            timeout=request.timeout_seconds)
```

The Bogda-owned YAML overlays preserve the current abstract Flash/Pro mapping but are maintained independently. The adapter never dumps composed dsh config, environment variables, or credentials. A successful process without a receipt is still `USAGE_UNKNOWN`, not a zero-cost success; `FINISHED` requires a valid receipt.

- [ ] **Step 4: Run focused and shell-executor regressions**

Run: `uv run --extra dev --python 3.11 pytest tests/model_runtime/test_dsh.py tests/executors -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add bogda/src/bogda/model_runtime/dsh.py bogda/src/bogda/model_runtime/__init__.py bogda/config/dsh-patches bogda/tests/model_runtime/test_dsh.py
git commit -m "feat(bogda): add dsh paid call adapter"
```

---

### Task 4: Paid Call Coordinator and Usage Reconciliation

**Files:**
- Create: `bogda/src/bogda/model_runtime/service.py`
- Create: `bogda/tests/model_runtime/test_paid_call_service.py`
- Modify: `bogda/src/bogda/model_runtime/__init__.py`
- Modify: `bogda/src/bogda/contracts/events.py`
- Modify: `bogda/tests/contracts/test_events.py`

**Interfaces:**
- Consumes: `ModelRouter`, `PromptArchivePort`, `BudgetAdmissionService`, shared `RunEventSink`, `ModelExecutionPort`, `estimate_token_cost`, and the frozen `JobRequest`.
- Produces: `PaidModelCallService.execute(run_id, call_id, request, prompt, attempt_dir, *, pro_available, allow_low_risk_fallback) -> PaidCallResult`.

- [ ] **Step 1: Write event-order and failure-semantics tests**

```python
def test_finished_call_archives_then_reserves_then_reconciles():
    result = service.execute(...)
    assert archive.calls == [("run-1", "call-1", PROMPT)]
    assert result.status is PaidCallStatus.FINISHED
    assert [event.event for event in sink.events] == [
        RunEventType.ROUTE_SELECTED,
        RunEventType.BUDGET_SNAPSHOT,
        RunEventType.BUDGET_RESERVED,
        RunEventType.MODEL_CALL_STARTED,
        RunEventType.MODEL_CALL_FINISHED,
        RunEventType.BUDGET_RELEASED,
    ]

def test_unknown_usage_keeps_reservation_and_forbids_retry():
    first = service.execute(...unknown_executor...)
    assert first.status is PaidCallStatus.USAGE_UNKNOWN
    assert ledger.active_total > 0
    second = service.execute(...same_call...)
    assert second.status is PaidCallStatus.RECONCILIATION_REQUIRED
    assert executor.calls == 1
```

Also test archive failure before admission, route pause before admission, budget denial before executor, model-start event failure compensation, `NOT_STARTED` release, exact receipt cost reconciliation, event payload prompt hash/path without prompt text, and secret-free exception representations.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `uv run --extra dev --python 3.11 pytest tests/model_runtime/test_paid_call_service.py tests/contracts/test_events.py -q`

Expected: missing service/types and any new event invariant failures.

- [ ] **Step 3: Implement one explicit state machine**

```text
route -> archive -> admit -> model_call_started -> invoke
  NOT_STARTED   -> release -> failed_not_started
  USAGE_UNKNOWN -> keep reservation -> reconciliation_required
  FINISHED      -> compute/accept exact CNY -> model_call_finished -> reconcile
```

`RunEventV1` changes are additive and v1-compatible: model-call events require `call_id`; a finished event with accounting facts requires `usage_reference` and `actual_cost_cny`; an unknown result is represented by `reason="usage_unknown"` without fabricated cost. The service must not retain full prompt/output in events or exception text.

The service also exposes `record_budget_resume(run_id, call_id, request)` to append one `BUDGET_RESUMED` event after Prefect returns from a real suspension and before the same frozen request is re-evaluated.

- [ ] **Step 4: Run model-runtime, budget, event, and contract regressions**

Run: `uv run --extra dev --python 3.11 pytest tests/model_runtime tests/budget tests/events tests/contracts -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add bogda/src/bogda/model_runtime/service.py bogda/src/bogda/model_runtime/__init__.py bogda/src/bogda/contracts/events.py bogda/tests/model_runtime/test_paid_call_service.py bogda/tests/contracts/test_events.py
git commit -m "feat(bogda): coordinate paid model calls"
```

---

### Task 5: Prefect Suspension and Resume Boundary

**Files:**
- Create: `bogda/src/bogda/flows/paid_model_call.py`
- Create: `bogda/tests/flows/test_paid_model_call.py`
- Modify: `bogda/src/bogda/flows/__init__.py`

**Interfaces:**
- Consumes: `PaidModelCallService`, serialized `JobRequest`, prompt, call id, attempt directory, and `prefect.flow_runs.suspend_flow_run`.
- Produces: `run_paid_model_call(...)` with `persist_result=True` and an injectable `BudgetSuspender` for deterministic tests.

- [ ] **Step 1: Write suspend/resume tests**

```python
def test_budget_pause_suspends_without_sleep_then_rechecks_same_request():
    service = ScriptedService([paused_result(), finished_result()])
    suspender = RecordingSuspender()
    result = run_paid_model_call.fn(PAYLOAD, PROMPT, service, suspender)
    assert suspender.keys == ["budget:run-1:call-1:1"]
    assert service.resume_events == [("run-1", "call-1")]
    assert service.requests[0].budget == service.requests[1].budget
    assert result["status"] == "finished"

def test_unknown_usage_returns_reconciliation_required_without_suspend_or_retry():
    ...
```

Also assert scheduled/Pro-required/budget-paused statuses remain distinct and no `time.sleep` or polling loop exists.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `uv run --extra dev --python 3.11 pytest tests/flows/test_paid_model_call.py -q`

Expected: module missing.

- [ ] **Step 3: Implement a thin Prefect adapter**

```python
class PrefectBudgetSuspender:
    def suspend(self, key: str) -> None:
        suspend_flow_run(key=key, timeout=None)

@flow(name="bogda-paid-model-call", persist_result=True)
def run_paid_model_call(...):
    # Execute once; on a recoverable budget pause suspend, then re-evaluate
    # the same frozen request. Unknown usage returns immediately.
```

Use deterministic numbered keys per in-flow suspension round. This phase proves the resumable boundary with fakes; it does not register or deploy the flow.

- [ ] **Step 4: Run flow and runtime regressions**

Run: `uv run --extra dev --python 3.11 pytest tests/flows tests/model_runtime -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add bogda/src/bogda/flows/paid_model_call.py bogda/src/bogda/flows/__init__.py bogda/tests/flows/test_paid_model_call.py
git commit -m "feat(bogda): suspend paid calls on budget gates"
```

---

### Task 6: Phase C Integration Acceptance and Maintainer Handoff

**Files:**
- Create: `bogda/tests/integration/test_paid_model_runtime.py`
- Modify: `bogda/README.md`
- Create: `docs/reports/2026-08-29-bogda-paid-model-runtime-acceptance.md`
- Modify: `docs/superpowers/plans/2026-08-29-bogda-paid-model-runtime.md`

**Interfaces:**
- Consumes: all Phase C public ports and existing Phase B budget/event kernel.
- Produces: fake-provider acceptance evidence and the exact Phase D/frontend handoff boundary.

- [ ] **Step 1: Add end-to-end fake scenarios**

```text
1. Auto/Flash call: prompt archive -> route -> reserve -> fake dsh -> exact usage -> reconcile.
2. Auto/audit resolves Pro; unavailable Pro pauses without Flash downgrade.
3. Low-risk explicit fallback downgrades once and records requested/effective tiers.
4. Missing usage leaves one active reservation and blocks retry pending reconciliation.
5. Insufficient balance suspends; restored fake balance resumes against the identical envelope.
6. Prompt archive failure produces no reservation and no executor call.
```

- [ ] **Step 2: Run focused acceptance**

Run: `uv run --extra dev --python 3.11 pytest tests/integration/test_paid_model_runtime.py -q`

Expected: all six scenarios PASS without network or real dsh.

- [ ] **Step 3: Document ownership and operational limits**

README/report must state concrete ports, event order, patch ownership, exact unknown-usage recovery rule, Prefect suspend deployment prerequisites, local recovery commands, and these exclusions: no live call, no deployment, no frontend, no production writer, no cross-process exactly-once.

- [ ] **Step 4: Run full compatibility verification**

Run:

```powershell
Set-Location D:\pythonProject\bogda
uv run --extra dev --python 3.11 pytest -q
Set-Location D:\pythonProject\orchestra\broker
D:\pythonProject\bogda\.venv\Scripts\python.exe -m unittest tests.test_taskfile -q
Set-Location D:\pythonProject
rg -n -i '(^|\s)(from|import)\s+(orchestra|usage[_-]?monitor)(\.|\s|$)' bogda/src
git diff --check
git status --short --branch
```

Expected: Bogda and Orchestra suites pass; no forbidden runtime imports; diff check clean; only authorized Phase C files differ from the fork point.

- [ ] **Step 5: Commit**

```powershell
git add bogda/tests/integration/test_paid_model_runtime.py bogda/README.md docs/reports/2026-08-29-bogda-paid-model-runtime-acceptance.md docs/superpowers/plans/2026-08-29-bogda-paid-model-runtime.md
git commit -m "docs(bogda): accept paid model runtime phase"
```

## Review and Stop Gate

Each task requires a fresh Luna implementer, red/green evidence, an isolated commit, and SOL review before the next task. Review findings are fixed by the same implementer for up to three rounds, then a fresh implementer if needed. Phase C completes only after a whole-branch review and fresh full-suite verification.

Stop before live dsh/DeepSeek smoke, deployment, frontend Phase D, push, or production integration. Present the owner with local merge / push-PR / preserve-worktree options.
