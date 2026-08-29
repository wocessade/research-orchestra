# Bogda Owner Console Stage D Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the owner one actionable console surface for model choice, budget state, price timing, blocked decisions, run audit, and policy controls without creating a second execution truth source.

**Architecture:** Add a console-owned `ModelControlPort` boundary with a deterministic in-memory mock adapter and an explicitly unavailable real-profile adapter. Query and command services expose closed Pydantic contracts; React consumes generated OpenAPI types. The decision center is the only pending-item list, while run detail and policy/create windows link to the same snapshots and revisioned commands.

**Tech Stack:** Python 3.11, FastAPI, Pydantic 2, React 19, TypeScript 5.9, TanStack Query, Vitest, Playwright, existing Bogda Console tokens and dialog primitives.

**Spec:** `docs/superpowers/specs/2026-08-28-bogda-intelligent-collaboration-budget-design.md`

## Global Constraints

- Keep autonomy, task intent, model tier, executor, and budget orthogonal; Pro never expands tools or autonomy.
- The decision center is the only pending-item collection. Other pages may link to an item but must not maintain a second pending state.
- Real profiles never fall back to mock model/budget data. Stage D enables commands only in `mock-all`; Stage E owns real usage and runtime writers.
- Show `stale`, `insufficient`, `scheduled-off-peak`, `awaiting-approval`, and `usage-unknown` as distinct states with distinct recovery actions.
- Revision conflicts return the current authoritative resource and require explicit re-confirmation.
- Do not expose a per-run switch for stale-snapshot fail-closed, minimum reserve, high-risk silent downgrade, usage-unknown retry barrier, structured logs, archive, or secret redaction.
- Preserve the existing conifer/lake/route token system and Manrope/Plex typography. The single visual signature is a compact decision runway grouped by urgency; do not redesign unrelated pages.
- No live DeepSeek/dsh call, real usage API, production Prefect write, RK3528 mutation, 3100/3101 cutover, secret change, push, or destructive cleanup.
- Use focused TDD per task, affected backend/frontend suites per task, and one final full Console backend/frontend/browser/build verification.

---

### Task 1: Model-Control Contracts and Mock Authority

**Files:**
- Modify: `bogda-console/src/bogda_console/contracts/models.py`
- Modify: `bogda-console/src/bogda_console/contracts/ports.py`
- Create: `bogda-console/src/bogda_console/adapters/mock_model_control.py`
- Create: `bogda-console/src/bogda_console/adapters/unwired_model_control.py`
- Test: `bogda-console/tests/backend/test_model_control_adapters.py`

**Interfaces:**
- Produces immutable wire models `DecisionCenterSnapshot`, `DecisionItem`, `DecisionAction`, `ModelBudgetSnapshot`, `ModelPolicySnapshot`, `RunPreparationPreview`, and `EvidenceReference`.
- Produces `ModelControlQueryPort` (`decision_center`, `run_budget`, `model_policy`, `preview_run`) and `ModelControlCommandPort` (`resolve_decision`, `set_global_policy`, `set_project_policy`, `confirm_preparation`).
- `MockModelControlAdapter` owns one in-memory canonical decision/policy state and revision counters. `UnwiredModelControlAdapter` raises a typed unavailable error and never fabricates data.

- [ ] **Step 1: Write failing contract/adapter tests**

Cover closed camelCase JSON, Decimal money serialized as strings, timezone-aware deadlines, distinct budget states, allowed decision actions, policy inheritance/source/revision, and a stale revision returning the current resource.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `uv run --extra dev --python 3.11 pytest tests/backend/test_model_control_adapters.py -q`

Expected: collection fails because the model-control contracts and adapters do not exist.

- [ ] **Step 3: Implement the smallest authoritative mock boundary**

Use explicit enums and Pydantic validators. Store pending items once in the adapter; `run_budget` references a `decision_id` rather than cloning a pending record. Policy overrides contain source (`global` or `project`), revision, and a restore-inheritance operation. `preview_run` returns an opaque `preparation_id`; `confirm_preparation` records the same frozen mock snapshot idempotently. Keep money as `Decimal` in Python and string in wire JSON.

- [ ] **Step 4: Run focused and existing contract tests**

Run: `uv run --extra dev --python 3.11 pytest tests/backend/test_model_control_adapters.py tests/backend/test_contracts.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add bogda-console/src/bogda_console/contracts bogda-console/src/bogda_console/adapters bogda-console/tests/backend/test_model_control_adapters.py
git commit -m "feat(console): define owner model controls"
```

---

### Task 2: Revisioned Model-Control API

**Files:**
- Modify: `bogda-console/src/bogda_console/app.py`
- Modify: `bogda-console/src/bogda_console/config.py`
- Modify: `bogda-console/src/bogda_console/services/queries.py`
- Modify: `bogda-console/src/bogda_console/services/commands.py`
- Modify: `bogda-console/src/bogda_console/services/errors.py`
- Modify: `bogda-console/src/bogda_console/api/routes.py`
- Test: `bogda-console/tests/backend/test_model_control_api.py`
- Modify: `bogda-console/tests/backend/test_openapi.py`

**Interfaces:**
- Adds GET `/api/v1/decisions`, GET `/api/v1/runs/{run_id}/model-budget`, GET `/api/v1/model-policy`, and POST `/api/v1/run-preparations/preview`.
- Adds POST `/api/v1/decisions/{decision_id}`, POST `/api/v1/model-policy/global`, and POST `/api/v1/model-policy/projects/{project_id}` with expected revision.
- Extends `SubmitRequest` with optional `runPreparationId`. When present in `mock-all`, the command service confirms that exact preview before submitting the registered deployment; real profiles keep the capability disabled until Stage E supplies a durable writer.
- Extends `CapabilitySnapshot` with `canResolveModelDecision`, `canSetModelPolicy`, and `canPreparePaidRun`; all are false outside `mock-all` in Stage D.

- [ ] **Step 1: Write failing API and capability tests**

Assert closed request bodies, source metadata, unavailable real-profile behavior, conflict details containing `currentResource`, no mock fallback, and exact command receipts.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `uv run --extra dev --python 3.11 pytest tests/backend/test_model_control_api.py tests/backend/test_openapi.py -q`

Expected: new routes are absent.

- [ ] **Step 3: Wire the ports through the existing container/services**

Query methods produce normal `ApiEnvelope` objects. Command methods use the existing per-resource locks and translate model-control revision conflicts to `RESOURCE_CHANGED`. Real profiles receive `UnwiredModelControlAdapter`; no route may instantiate mock data as a fallback.

- [ ] **Step 4: Export and verify OpenAPI**

Run: `uv run --extra dev --python 3.11 pytest tests/backend/test_model_control_api.py tests/backend/test_openapi.py tests/backend/test_query_api.py tests/backend/test_command_api.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add bogda-console/src/bogda_console bogda-console/tests/backend/test_model_control_api.py bogda-console/tests/backend/test_openapi.py
git commit -m "feat(console): expose revisioned model controls"
```

---

### Task 3: Unified Decision Runway

**Files:**
- Create: `bogda-console/frontend/src/pages/DecisionsPage.tsx`
- Modify: `bogda-console/frontend/src/components/AppShell.tsx`
- Modify: `bogda-console/frontend/src/app/App.tsx`
- Modify: `bogda-console/frontend/src/styles/global.css`
- Modify: `bogda-console/frontend/src/api/types.ts`
- Regenerate: `bogda-console/frontend/src/api/generated.ts`
- Regenerate: `bogda-console/openapi.json`
- Test: `bogda-console/tests/frontend/decisions.test.tsx`
- Modify: `bogda-console/tests/frontend/helpers.tsx`

**Interfaces:**
- `/decisions` reads only `/api/v1/decisions` and groups one canonical list into “需要我现在处理”, “有截止时间”, and “仅供知晓”.
- A modal/drawer shows reason, fee/quality effect, evidence links, irreversible consequence, and the exact log summary. It submits one revisioned action and keeps owner rationale on conflict.

- [ ] **Step 1: Generate current contracts and write failing UI tests**

Test urgency grouping, project/risk filters, empty state, unique decision IDs, high-risk action confirmation, action-specific copy, source degradation, and revision-conflict adoption without automatic replay.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `npm run test:frontend -- decisions.test.tsx`

Expected: page and route are missing.

- [ ] **Step 3: Build the decision runway with existing primitives**

Use the existing modal focus trap, action classes, source/error envelopes, spacing, and color tokens. Use urgency rails and compact evidence chips as the signature; no new font, gradient, card grid, or decorative dashboard metrics.

- [ ] **Step 4: Run focused frontend and app-shell tests**

Run: `npm run test:frontend -- decisions.test.tsx app-shell.test.tsx dialogs.test.tsx`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add bogda-console/frontend bogda-console/openapi.json bogda-console/tests/frontend
git commit -m "feat(console): add owner decision runway"
```

---

### Task 4: Run Budget and Audit Surface

**Files:**
- Create: `bogda-console/frontend/src/components/RunBudgetPanel.tsx`
- Modify: `bogda-console/frontend/src/pages/RunDetailPage.tsx`
- Modify: `bogda-console/frontend/src/styles/global.css`
- Test: `bogda-console/tests/frontend/run-budget.test.tsx`
- Modify: `bogda-console/tests/frontend/runs.test.tsx`

**Interfaces:**
- `RunBudgetPanel` consumes the run-budget endpoint and renders requested/effective tier, intent, authorized/spent/reserved/remaining CNY, current price window, planned start, pause reason, recovery condition, event rows, and prompt/stdout/stderr/receipt references.
- If a `decisionId` exists, the only action is a link to the canonical decision center item. Safety baselines render as fixed rules, never checkboxes.

- [ ] **Step 1: Write failing state-matrix tests**

Cover ready, stale snapshot, insufficient balance, off-peak scheduled, awaiting approval, and usage unknown. Assert distinct labels/actions and exact artifact/event links without prompt or secret content.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `npm run test:frontend -- run-budget.test.tsx runs.test.tsx`

Expected: panel is absent.

- [ ] **Step 3: Add the run budget panel without growing RunDetail responsibilities**

Keep fetching/rendering in the new component. `RunDetailPage` only supplies `runId` and page placement. Use a compact ledger plus one recovery callout; avoid duplicating decision action state.

- [ ] **Step 4: Run focused and checkpoint/review regressions**

Run: `npm run test:frontend -- run-budget.test.tsx runs.test.tsx checkpoints.test.tsx commands.test.tsx`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add bogda-console/frontend/src/components/RunBudgetPanel.tsx bogda-console/frontend/src/pages/RunDetailPage.tsx bogda-console/frontend/src/styles/global.css bogda-console/tests/frontend
git commit -m "feat(console): show run model budget audit"
```

---

### Task 5: Policy Controls and Guarded Run Preparation

**Files:**
- Create: `bogda-console/frontend/src/pages/ModelPolicyPage.tsx`
- Create: `bogda-console/frontend/src/components/RunPreparation.tsx`
- Modify: `bogda-console/frontend/src/pages/InfrastructurePage.tsx`
- Modify: `bogda-console/frontend/src/components/AppShell.tsx`
- Modify: `bogda-console/frontend/src/app/App.tsx`
- Modify: `bogda-console/frontend/src/styles/global.css`
- Test: `bogda-console/tests/frontend/model-policy.test.tsx`
- Test: `bogda-console/tests/frontend/run-preparation.test.tsx`
- Modify: `bogda-console/tests/frontend/commands.test.tsx`

**Interfaces:**
- `/model-policy` separates global safety facts from mutable project defaults. Mutable controls are minimum reserve, workload-derived safety margin, Auto/Flash/Pro, budget-within-package Pro upgrade, low-risk Flash fallback, off-peak preference, balance-recovery auto-continue, notification, and inherit/override.
- `RunPreparation` extends the existing allowlisted deployment dialog with intent, tier, workload estimate, deadline, and per-run allowed preferences, then requests a preview before a separate confirmation step. The confirmation shows effective autonomy, actual tier, estimate, ceiling, price period/start, and fallback, and submits the returned `runPreparationId` with the existing idempotency key. Stage D commands remain capability-disabled outside mock.

- [ ] **Step 1: Write failing policy and preparation tests**

Cover source/revision display, restore inheritance, conflict re-confirmation, non-disableable safety rules, progressive advanced fields, price-window estimate, no preselected risky peak override, and final confirmation before submit.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `npm run test:frontend -- model-policy.test.tsx run-preparation.test.tsx commands.test.tsx`

Expected: policy page and preparation flow are absent.

- [ ] **Step 3: Implement separated policy and preparation components**

Do not add model controls to `AutonomyPolicyPanel`. Use server previews and capability flags; do not reproduce pricing/routing conditionals in TypeScript. Keep the existing deployment parameter coercion and authoritative Prefect receipt semantics.

- [ ] **Step 4: Run affected frontend and backend contract checks**

Run: `npm run test:frontend -- model-policy.test.tsx run-preparation.test.tsx commands.test.tsx autonomy-policy.test.tsx infrastructure.test.tsx`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add bogda-console/frontend bogda-console/tests/frontend
git commit -m "feat(console): add model policy and run preparation"
```

---

### Task 6: Stage D Browser Acceptance and Handoff

**Files:**
- Modify: `bogda-console/tests/browser/console.spec.ts`
- Modify: `bogda-console/tests/browser/accessibility.spec.ts`
- Modify: `bogda-console/tests/browser/degradation.spec.ts`
- Create: `docs/reports/2026-08-29-bogda-owner-console-acceptance.md`
- Modify: `docs/reports/2026-08-29-bogda-deferred-work-register.md`
- Modify: `docs/superpowers/plans/2026-08-29-bogda-owner-console.md`

**Interfaces:**
- Produces desktop and 320/360 px interaction evidence for the decision center, run budget, policy, and guarded preparation flows.
- Closes Stage D-only deferred items and keeps real usage, scheduler execution, durable stores/outbox, live smoke, Prefect deployment, artifact lifecycle, and production operations open for Stage E.

- [x] **Step 1: Add browser acceptance scenarios**

Exercise keyboard/focus flow, decision conflict, state-specific recovery copy, project inheritance restore, guarded run confirmation, real-profile unavailable behavior, and axe checks at desktop/mobile widths.

- [x] **Step 2: Run the focused browser scenarios**

Run: `npm run test:browser -- console.spec.ts accessibility.spec.ts degradation.spec.ts`

Expected: PASS with no unexpected console errors or requests.

- [x] **Step 3: Perform visual QA and remove one unnecessary visual element**

Inspect decision center, run detail, and model policy at desktop and 320/360 px. Preserve visible focus, reduced-motion compatibility, no horizontal clipping, and the existing shell identity. Record the removed excess element in the acceptance report.

- [x] **Step 4: Run one final Stage D verification**

Run:

```powershell
uv run --extra dev --python 3.11 pytest -q
npm run test:frontend
npm run build
npm run test:browser
git diff --check
```

Expected: all backend, frontend, build/contract, and browser checks pass once at the phase gate.

- [ ] **Step 5: Commit**

```powershell
git add bogda-console docs/reports/2026-08-29-bogda-owner-console-acceptance.md docs/reports/2026-08-29-bogda-deferred-work-register.md docs/superpowers/plans/2026-08-29-bogda-owner-console.md
git commit -m "docs(bogda): accept owner console stage"
```

## Review and Integration Gate

Each task receives focused TDD evidence and scoped independent review before the next dependent task. Run affected broad tests after each task, but run the full backend/frontend/browser/build matrix only once in Task 6 unless a cross-cutting Critical finding requires another full pass. Local fast-forward merge is owner-authorized after the whole-branch review; push, live provider spend, production changes, and worktree/branch cleanup remain unauthorized.
