import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { completedRun, envelope, renderAppAt, sourceFresh, standardRoutes, validResult } from "./helpers";
import { coerceDeploymentParameters } from "../../frontend/src/pages/InfrastructurePage";

describe("Deployment parameter schema", () => {
  it("preserves declared scalar types and rejects invalid values", () => {
    const schema = { properties: { sample: { type: "string" }, attempt: { type: "integer" }, threshold: { type: "number" }, enabled: { type: "boolean" } }, required: ["sample", "attempt"] };
    expect(coerceDeploymentParameters({ sample: "ridge", attempt: "2", threshold: "0.5", enabled: "false" }, schema)).toEqual({ sample: "ridge", attempt: 2, threshold: 0.5, enabled: false });
    expect(() => coerceDeploymentParameters({ sample: "ridge", attempt: "2.5" }, schema)).toThrow(/整数/);
  });
});

function activeRunRoutes() {
  const routes = standardRoutes();
  const run = { ...completedRun, runId: "run-active", name: "ridge calibration", state: { ...completedRun.state, type: "RUNNING", name: "Running", terminal: false }, commandVersion: "run-active-v1", scientific: { availability: "missing", artifactId: null, artifactCreatedAt: null, scientificStatus: null, reviewSummary: null, validationIssues: [] } };
  routes["/api/v1/runs/run-active"] = envelope({ run, parameters: {}, tags: [], projectContext: null });
  routes["/api/v1/runs/run-active/result"] = envelope({ availability: "missing", artifactId: null, artifactCreatedAt: null, result: null, validationIssues: [] }, { runResult: { ...sourceFresh, source: "runResult" } });
  routes["/api/v1/runs/run-active/result/versions"] = envelope({ items: [], nextCursor: null }, { runResult: { ...sourceFresh, source: "runResult" } });
  return { routes, run };
}

describe("guarded commands", () => {
  it("waits for the authoritative cancel receipt", async () => {
    const user = userEvent.setup();
    const { routes, run } = activeRunRoutes();
    let release!: () => void;
    const gate = new Promise<void>((resolve) => { release = resolve; });
    routes["/api/v1/runs/run-active/cancel"] = async ({ init }) => {
      expect(JSON.parse(String(init?.body))).toEqual({ expectedCommandVersion: "run-active-v1" });
      await gate;
      return envelope({ command: "cancel", resourceId: "run-active", acceptedAt: "2026-08-24T08:30:00Z", snapshot: { ...run, state: { ...run.state, type: "CANCELLED", name: "Cancelling" } } }, {});
    };
    renderAppAt("/runs/run-active", routes);
    await user.click(await screen.findByRole("button", { name: "取消运行" }));
    const confirm = screen.getByRole("button", { name: "确认取消" });
    await user.click(confirm);
    expect(confirm).toBeDisabled();
    expect(screen.queryByText("Cancelling")).not.toBeInTheDocument();
    release();
    expect(await screen.findByText("Cancelling")).toBeVisible();
  });

  it("keeps review text and shows the newest artifact on conflict", async () => {
    const user = userEvent.setup();
    const routes = standardRoutes();
    const run = { ...completedRun, runId: "run-review", name: "review conflict", state: { ...completedRun.state, type: "CRASHED", name: "Crashed" } };
    const result = { ...validResult, artifactId: "artifact-old", result: { ...validResult.result!, run_id: "run-review", execution_status: "Crashed" } };
    routes["/api/v1/runs/run-review"] = envelope({ run, parameters: {}, tags: [], projectContext: null });
    routes["/api/v1/runs/run-review/result"] = envelope(result, { runResult: { ...sourceFresh, source: "runResult" } });
    routes["/api/v1/runs/run-review/result/versions"] = envelope({ items: [], nextCursor: null }, { runResult: { ...sourceFresh, source: "runResult" } });
    let reviewCalls = 0;
    routes["/api/v1/runs/run-review/reviews"] = ({ init }) => {
      reviewCalls += 1;
      const body = JSON.parse(String(init?.body));
      if (reviewCalls === 1) {
        expect(body.baseArtifactId).toBe("artifact-old");
        return new Response(JSON.stringify(envelope(null, {}, [{ code: "REVIEW_CONFLICT", message: "changed", source: "runResult", retryable: false, details: { currentResource: { availability: "available", artifactId: "artifact-newest", artifactCreatedAt: "2026-08-24T09:50:00Z", result: { ...result.result, scientific_status: "inconclusive", review_summary: "needs another assay" }, validationIssues: [] }, fields: [], expected: null, observed: null } }])), { status: 409, headers: { "Content-Type": "application/json" } });
      }
      expect(body.baseArtifactId).toBe("artifact-newest");
      return envelope({ command: "review", resourceId: "run-review", acceptedAt: "2026-08-24T09:55:00Z", snapshot: { ...result, artifactId: "artifact-reviewed", result: { ...result.result!, scientific_status: "accepted", review_summary: "证据链不完整" } } }, {});
    };
    renderAppAt("/runs/run-review", routes);
    await user.type(await screen.findByLabelText("评审说明"), "证据链不完整");
    await user.click(screen.getByRole("button", { name: "提交评审" }));
    expect(await screen.findByText(/结果已被其他评审更新/)).toBeVisible();
    expect(screen.getByLabelText("评审说明")).toHaveValue("证据链不完整");
    expect(screen.getByText("artifact-newest")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "确认采用最新版本" }));
    expect(screen.getByRole("status")).toHaveTextContent("artifact-newest");
    expect(screen.getByLabelText("评审说明")).toHaveValue("证据链不完整");
    await user.click(screen.getByRole("button", { name: "提交评审" }));
    expect(await screen.findByText("已接受")).toBeVisible();
  });

  it("appends a review version and waits for the RunResult receipt", async () => {
    const user = userEvent.setup();
    const routes = standardRoutes();
    routes["/api/v1/runs/run-completed-unreviewed/reviews"] = ({ init }) => {
      expect(JSON.parse(String(init?.body))).toEqual({ baseArtifactId: "artifact-completed-1", scientificStatus: "accepted", reviewSummary: "证据充分" });
      return envelope({ command: "review", resourceId: "run-completed-unreviewed", acceptedAt: "2026-08-24T08:30:00Z", snapshot: { ...validResult, artifactId: "artifact-reviewed", result: { ...validResult.result!, scientific_status: "accepted", review_summary: "证据充分" } } }, {});
    };
    renderAppAt("/runs/run-completed-unreviewed", routes);
    await user.type(await screen.findByLabelText("评审说明"), "证据充分");
    await user.click(screen.getByRole("button", { name: "提交评审" }));
    expect(await screen.findByText("已接受")).toBeVisible();
    expect(screen.getAllByText("artifact-reviewed").length).toBeGreaterThan(0);
  });

  it("submits only the selected registered Deployment", async () => {
    const user = userEvent.setup();
    const routes = standardRoutes();
    const idempotencyKeys: string[] = [];
    let submitCalls = 0;
    routes["/api/v1/deployments/deployment-dorm/runs"] = ({ init }) => {
      submitCalls += 1;
      const body = JSON.parse(String(init?.body));
      expect(body.parameters).toEqual({ sample: "ridge-a" });
      idempotencyKeys.push(body.idempotencyKey);
      if (submitCalls === 1) return new Response(JSON.stringify(envelope(null, {}, [{ code: "COMMAND_OUTCOME_UNKNOWN", message: "unknown", source: "prefect", retryable: true, details: { fields: [], expected: null, observed: null } }])), { status: 503, headers: { "Content-Type": "application/json" } });
      return envelope({ command: "submit", resourceId: "mock-submitted-1", acceptedAt: "2026-08-24T08:30:00Z", snapshot: { ...completedRun, runId: "mock-submitted-1", name: "alpine-assay · 1", state: { ...completedRun.state, type: "SCHEDULED", name: "Scheduled", terminal: false } } }, {});
    };
    renderAppAt("/infrastructure", routes);
    await user.click(await screen.findByRole("button", { name: "提交 alpine-assay" }));
    await user.type(screen.getByLabelText("Sample"), "ridge-a");
    await user.click(screen.getByRole("button", { name: "提交运行" }));
    expect(await screen.findByRole("alert")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "提交运行" }));
    expect(await screen.findByText("已提交：alpine-assay · 1")).toBeVisible();
    expect(idempotencyKeys[0]).toBe(idempotencyKeys[1]);
  });

  it("uses the server command version for queue and schedule actions", async () => {
    const user = userEvent.setup();
    const routes = standardRoutes();
    routes["/api/v1/work-queues/queue-cpu/pause"] = ({ init }) => {
      expect(JSON.parse(String(init?.body))).toEqual({ expectedCommandVersion: "queue-cpu-v1" });
      return envelope({ command: "pauseQueue", resourceId: "queue-cpu", acceptedAt: "2026-08-24T08:30:00Z", snapshot: { queueId: "queue-cpu", name: "cpu", status: "PAUSED", isPaused: true, concurrencyLimit: null, commandVersion: "queue-cpu-v2" } }, {});
    };
    routes["/api/v1/deployments/deployment-dorm/schedules/schedule-dorm/pause"] = ({ init }) => {
      expect(JSON.parse(String(init?.body))).toEqual({ expectedCommandVersion: "schedule-v1" });
      return envelope({ command: "pauseSchedule", resourceId: "schedule-dorm", acceptedAt: "2026-08-24T08:30:00Z", snapshot: { deploymentId: "deployment-dorm", name: "alpine-assay", flowName: "alpine-assay", parameterSchema: {}, allowlisted: true, schedules: [{ scheduleId: "schedule-dorm", label: "manual window", active: false, commandVersion: "schedule-v2" }] } }, {});
    };
    renderAppAt("/infrastructure", routes);
    await user.click(await screen.findByRole("button", { name: "暂停队列 cpu" }));
    await user.click(screen.getByRole("button", { name: "确认暂停" }));
    expect(await screen.findByText("队列 cpu 已暂停")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "暂停日程 manual window" }));
    await user.click(screen.getByRole("button", { name: "确认暂停" }));
    expect(await screen.findByText("日程 manual window 已暂停")).toBeVisible();
  });

  it("resumes paused queues and schedules through their explicit endpoints", async () => {
    const user = userEvent.setup();
    const routes = standardRoutes();
    routes["/api/v1/infrastructure"] = envelope({ pools: [{ name: "dorm-x86", status: "PAUSED", isPaused: false, concurrencyLimit: 1, activeSlots: 0, queues: [{ queueId: "queue-cpu", name: "cpu", status: "PAUSED", isPaused: true, concurrencyLimit: null, commandVersion: "queue-paused-v1" }], workers: [] }], dormPower: { host: "dorm-x86", mode: "gaming", agentReachable: true, sleepInhibited: true, lastTransitionAt: "2026-08-24T13:00:00Z" } }, { prefect: sourceFresh, power: { ...sourceFresh, source: "power", sourceMode: "mock" } });
    routes["/api/v1/deployments"] = envelope({ items: [{ deploymentId: "deployment-dorm", name: "alpine-assay", flowName: "alpine-assay", parameterSchema: {}, allowlisted: true, schedules: [{ scheduleId: "schedule-dorm", label: "evening", active: false, commandVersion: "schedule-paused-v1" }] }], nextCursor: null });
    routes["/api/v1/work-queues/queue-cpu/resume"] = envelope({ command: "resumeQueue", resourceId: "queue-cpu", acceptedAt: "2026-08-24T13:20:00Z", snapshot: { queueId: "queue-cpu", name: "cpu", status: "READY", isPaused: false, commandVersion: "queue-v2" } }, {});
    routes["/api/v1/deployments/deployment-dorm/schedules/schedule-dorm/resume"] = envelope({ command: "resumeSchedule", resourceId: "schedule-dorm", acceptedAt: "2026-08-24T13:20:00Z", snapshot: { deploymentId: "deployment-dorm", name: "alpine-assay", flowName: "alpine-assay", parameterSchema: {}, allowlisted: true, schedules: [] } }, {});
    renderAppAt("/infrastructure", routes);
    await user.click(await screen.findByRole("button", { name: "恢复队列 cpu" }));
    await user.click(screen.getByRole("button", { name: "确认恢复" }));
    expect(await screen.findByText("队列 cpu 已恢复")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "恢复日程 evening" }));
    await user.click(screen.getByRole("button", { name: "确认恢复" }));
    expect(await screen.findByText("日程 evening 已恢复")).toBeVisible();
  });

  it("disables write controls in real-readonly", async () => {
    const routes = standardRoutes();
    routes["/api/v1/capabilities"] = envelope({ profile: "real-readonly", projectId: "bogda-main", effectiveAutonomyMode: "supervised", canSubmitRegisteredDeployment: false, canCancelRun: false, canPauseSchedule: false, canPauseWorkQueue: false, canReviewScientificResult: false, canSetAutonomyMode: false }, {});
    renderAppAt("/infrastructure", routes);
    expect(await screen.findByRole("button", { name: "提交 alpine-assay" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "暂停队列 cpu" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "暂停日程 manual window" })).toBeDisabled();
  });
});
