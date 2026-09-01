import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { completedRun, envelope, renderAppAt, sourceFresh, standardRoutes } from "./helpers";

const pausedRun = {
  ...completedRun,
  runId: "run-checkpoint",
  name: "ridge experiment gate",
  state: {
    type: "PAUSED",
    name: "Paused",
    timestamp: "2026-08-24T08:21:00Z",
    terminal: false,
    message: "waiting for experiment_approval",
  },
  endedAt: null,
  scientific: {
    availability: "missing",
    artifactId: null,
    artifactCreatedAt: null,
    scientificStatus: null,
    reviewSummary: null,
    validationIssues: [],
  },
  commandVersion: "run-checkpoint-v1",
};

const openCheckpoint = {
  kind: "experiment_approval",
  stage: "done",
  verdict: null,
  rationale: null,
  decidedBy: null,
  commandVersion: "checkpoint-v1",
  impact: "批准后继续执行实验；拒绝将以 Cancelled 结束，不会记成系统失败。",
};

function checkpointRoutes() {
  const routes = standardRoutes();
  routes["/api/v1/runs"] = envelope({ items: [pausedRun, completedRun], nextCursor: null }, { prefect: sourceFresh, runResult: { ...sourceFresh, source: "runResult" } });
  routes["/api/v1/runs/run-checkpoint"] = envelope({
    run: pausedRun,
    parameters: { argv: ["python", "-V"], autonomy_mode: "supervised" },
    tags: ["cpu"],
    projectContext: { projectId: "bogda-main", effectiveAutonomyMode: "supervised", modeSource: "frozen-run-request", writable: false },
    checkpoint: openCheckpoint,
  }, { prefect: sourceFresh, runResult: { ...sourceFresh, source: "runResult" } });
  routes["/api/v1/runs/run-checkpoint/result"] = envelope({ availability: "missing", artifactId: null, artifactCreatedAt: null, result: null, validationIssues: [] }, { runResult: { ...sourceFresh, source: "runResult" } });
  routes["/api/v1/runs/run-checkpoint/result/versions"] = envelope({ items: [], nextCursor: null }, { runResult: { ...sourceFresh, source: "runResult" } });
  return routes;
}

describe("research checkpoints", () => {
  it("shows evidence, impact, and approve/reject only on the run detail page", async () => {
    const routes = checkpointRoutes();
    renderAppAt("/runs/run-checkpoint", routes);
    const region = await screen.findByRole("region", { name: "人工检查点" });
    expect(within(region).getByText("experiment_approval")).toBeVisible();
    expect(within(region).getByText(/批准后继续执行实验/)).toBeVisible();
    expect(within(region).getByRole("button", { name: "批准" })).toBeEnabled();
    expect(within(region).getByRole("button", { name: "拒绝" })).toBeEnabled();
    expect(screen.getByRole("heading", { name: "项目上下文" })).toBeVisible();
    expect(screen.getByText("冻结模式")).toBeVisible();
  });

  it("does not offer one-click approve or reject on the run list", async () => {
    renderAppAt("/runs", checkpointRoutes());
    expect((await screen.findAllByText("ridge experiment gate")).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "批准" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "拒绝" })).not.toBeInTheDocument();
  });

  it("keeps the rationale and shows the current version on conflict", async () => {
    const user = userEvent.setup();
    const routes = checkpointRoutes();
    let calls = 0;
    routes["/api/v1/runs/run-checkpoint/checkpoints"] = ({ init }) => {
      calls += 1;
      const body = JSON.parse(String(init?.body));
      expect(body.expectedCommandVersion).toBe(calls === 1 ? "checkpoint-v1" : "checkpoint-v2");
      expect(body.verdict).toBe("approved");
      expect(body.rationale).toBe("可以做");
      if (calls === 1) {
        return new Response(JSON.stringify(envelope(null, {}, [{
          code: "RESOURCE_CHANGED",
          message: "resource changed after the action was opened",
          source: "prefect",
          retryable: false,
          details: {
            currentResource: { ...openCheckpoint, commandVersion: "checkpoint-v2" },
            fields: [],
            expected: null,
            observed: null,
          },
        }])), { status: 409, headers: { "Content-Type": "application/json" } });
      }
      return envelope({
        command: "decideCheckpoint",
        resourceId: "run-checkpoint",
        acceptedAt: "2026-08-24T08:30:00Z",
        snapshot: {
          run: { ...pausedRun, state: { ...pausedRun.state, type: "RUNNING", name: "Running" } },
          parameters: {},
          tags: [],
          projectContext: null,
          checkpoint: { ...openCheckpoint, stage: "accepted", verdict: "approved", rationale: "可以做", commandVersion: "checkpoint-v3" },
        },
      }, {});
    };
    renderAppAt("/runs/run-checkpoint", routes);
    await user.type(await screen.findByLabelText("判断说明"), "可以做");
    await user.click(screen.getByRole("button", { name: "批准" }));
    expect(await screen.findByText(/检查点已被更新/)).toBeVisible();
    expect(screen.getByLabelText("判断说明")).toHaveValue("可以做");
    await user.click(screen.getByRole("button", { name: "采用当前版本" }));
    await user.click(screen.getByRole("button", { name: "批准" }));
    expect(await screen.findByText("Running")).toBeVisible();
  });

  it("disables checkpoint buttons when the profile is read-only", async () => {
    const routes = checkpointRoutes();
    routes["/api/v1/capabilities"] = envelope({
      profile: "real-readonly",
      projectId: "bogda-main",
      actorId: "local-owner",
      role: "observer",
      effectiveAutonomyMode: "supervised",
      canSubmitRegisteredDeployment: false,
      canCancelRun: false,
      canPauseSchedule: false,
      canPauseWorkQueue: false,
      canDecideCheckpoint: false,
      canReviewScientificResult: false,
      canSetAutonomyMode: false,
      allowedDeploymentIds: [],
      allowedScheduleIds: [],
      allowedQueueIds: [],
      allowedWorkPoolNames: [],
    }, {});
    renderAppAt("/runs/run-checkpoint", routes);
    expect(await screen.findByRole("button", { name: "批准" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "拒绝" })).toBeDisabled();
    expect(screen.getByText("当前 profile 为 real-readonly，只读，不能决定人工检查点。")).toBeVisible();
  });

  it("uses checkpoint capability instead of scientific review capability", async () => {
    const routes = checkpointRoutes();
    routes["/api/v1/capabilities"] = envelope({
      profile: "allowlisted-test",
      projectId: "bogda-main",
      effectiveAutonomyMode: "supervised",
      canSubmitRegisteredDeployment: true,
      canCancelRun: true,
      canPauseSchedule: true,
      canPauseWorkQueue: true,
      canDecideCheckpoint: false,
      canReviewScientificResult: true,
      canSetAutonomyMode: false,
      allowedDeploymentIds: ["deployment-dorm"],
      allowedScheduleIds: ["schedule-dorm"],
      allowedQueueIds: ["queue-cpu"],
      allowedWorkPoolNames: ["dorm-x86"],
    }, {});
    renderAppAt("/runs/run-checkpoint", routes);
    expect(await screen.findByRole("button", { name: "批准" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "拒绝" })).toBeDisabled();
  });

  it("keeps checkpoint controls disabled when the run deployment is outside scope", async () => {
    const routes = checkpointRoutes();
    routes["/api/v1/capabilities"] = envelope({
      profile: "allowlisted-test",
      projectId: "bogda-main",
      effectiveAutonomyMode: "supervised",
      canSubmitRegisteredDeployment: true,
      canCancelRun: true,
      canPauseSchedule: true,
      canPauseWorkQueue: true,
      canDecideCheckpoint: true,
      canReviewScientificResult: true,
      canSetAutonomyMode: false,
      allowedDeploymentIds: ["another-deployment"],
      allowedScheduleIds: [],
      allowedQueueIds: [],
      allowedWorkPoolNames: [],
    }, {});
    renderAppAt("/runs/run-checkpoint", routes);
    expect(await screen.findByRole("button", { name: "批准" })).toBeDisabled();
    expect(screen.getAllByText("不在测试白名单").length).toBeGreaterThan(0);
  });
});
