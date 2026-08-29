import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { envelope, renderAppAt, sourceFresh, standardRoutes } from "./helpers";

const policy = {
  projectId: "bogda-main",
  source: "project",
  revision: 4,
  inheritsGlobal: false,
  minimumRemaining: "6.00",
  workloadSafetyMargin: "1.25",
  defaultModelTier: "auto",
  allowAutoUpgrade: true,
  allowFlashDowngrade: true,
  preferOffPeak: true,
  autoResume: false,
  criticalNotifications: true,
  usageSnapshotStaleAfterSeconds: 120,
  priceCatalog: {
    status: "ready",
    version: "deepseek-v4-0813",
    effectiveAt: "2026-08-28T00:00:00Z",
    reviewBy: "2026-09-01T00:00:00Z",
    source: "deepseek",
  },
  hardSafetyBaselines: {
    budgetIncreaseApprovalRequired: true,
    decideAuditNoSilentDowngrade: true,
    humanExternalActions: true,
    humanScientificJudgment: true,
    minimumRemainingEnforced: true,
    promptArchivingRequired: true,
    structuredEventLog: true,
    unknownUsageRecoveryGate: true,
    usageSnapshotFailClosed: true,
  },
};

function writableCapabilities(projectId = "bogda-main") {
  return {
    profile: "mock-all",
    projectId,
    effectiveAutonomyMode: "supervised",
    canSubmitRegisteredDeployment: true,
    canCancelRun: true,
    canPauseSchedule: true,
    canPauseWorkQueue: true,
    canReviewScientificResult: true,
    canSetAutonomyMode: false,
    canResolveModelDecision: true,
    canSetModelPolicy: true,
    canPreparePaidRun: true,
  };
}

function routes(projectId = "bogda-main") {
  const result = standardRoutes();
  result["/api/v1/capabilities"] = envelope(writableCapabilities(projectId), {
    modelControl: { ...sourceFresh, source: "modelControl" },
  });
  result["/api/v1/model-policy"] = envelope({ ...policy, projectId }, {
    modelControl: { ...sourceFresh, source: "modelControl" },
  });
  return result;
}

describe("ModelPolicyPage", () => {
  it("separates immutable safety facts from editable project defaults", async () => {
    renderAppAt("/model-policy", routes());
    const region = await screen.findByRole("region", { name: "模型策略" });
    expect(within(region).getByText("系统安全基线")).toBeVisible();
    expect(within(region).getByText("仅观察，不可关闭")).toBeVisible();
    expect(within(region).getByText("本项目覆盖全局默认")).toBeVisible();
    expect(within(region).getByText(/模型策略不属于科研自主模式/)).toBeVisible();
    expect(within(region).getByText("修订号")).toBeVisible();
    expect(within(region).getByText("4")).toBeVisible();
  });

  it("restores inheritance against the capability projectId", async () => {
    const user = userEvent.setup();
    const result = routes("ridge-lab");
    let path = "";
    let body: unknown;
    result["/api/v1/model-policy/projects/ridge-lab"] = ({ init }) => {
      path = "/api/v1/model-policy/projects/ridge-lab";
      body = JSON.parse(String(init?.body));
      return envelope({
        command: "setProjectModelPolicy",
        resourceId: "ridge-lab",
        acceptedAt: "2026-08-29T00:00:00Z",
        snapshot: {
          ...policy,
          source: "global",
          projectId: "ridge-lab",
          inheritsGlobal: true,
          revision: 5,
        },
      });
    };
    renderAppAt("/model-policy", result);
    const region = await screen.findByRole("region", { name: "模型策略" });
    await user.click(within(region).getByRole("button", { name: "恢复继承全局" }));
    await user.click(screen.getByRole("button", { name: "确认恢复继承" }));
    expect(path).toBe("/api/v1/model-policy/projects/ridge-lab");
    expect(body).toEqual({ expectedRevision: 4, patch: null });
    expect(await within(region).findByText("继承全局")).toBeVisible();
  });

  it("keeps owner draft and inherit intent after conflict until explicit reconfirm", async () => {
    const user = userEvent.setup();
    const result = routes("ridge-lab");
    const current = { ...policy, projectId: "ridge-lab", defaultModelTier: "flash", revision: 7 };
    let calls = 0;
    const bodies: unknown[] = [];
    result["/api/v1/model-policy/projects/ridge-lab"] = ({ init }) => {
      calls += 1;
      const body = JSON.parse(String(init?.body));
      bodies.push(body);
      if (calls === 1) {
        return new Response(
          JSON.stringify(envelope(null, {}, [{
            code: "RESOURCE_CHANGED",
            message: "changed",
            source: "modelControl",
            retryable: false,
            details: { currentResource: current },
          }])),
          { status: 409, headers: { "Content-Type": "application/json" } },
        );
      }
      return envelope({
        command: "setProjectModelPolicy",
        resourceId: "ridge-lab",
        acceptedAt: "2026-08-29T00:00:00Z",
        snapshot: { ...current, minimumRemaining: "9.50", revision: 8, inheritsGlobal: false },
      });
    };
    renderAppAt("/model-policy", result);
    const region = await screen.findByRole("region", { name: "模型策略" });
    const remaining = within(region).getByLabelText("最低剩余预算");
    await user.clear(remaining);
    await user.type(remaining, "9.50");
    await user.click(within(region).getByRole("button", { name: "保存项目默认" }));
    await user.click(screen.getByRole("button", { name: "确认保存" }));
    expect(await screen.findByText("审阅最新值后重新确认")).toBeVisible();
    expect(screen.queryByRole("button", { name: "确认保存" })).not.toBeInTheDocument();
    expect(within(region).getByText("7")).toBeVisible();
    expect(within(region).getByLabelText("最低剩余预算")).toHaveValue("9.50");
    await user.click(within(region).getByRole("button", { name: "保存项目默认" }));
    await user.click(screen.getByRole("button", { name: "确认保存" }));
    expect(bodies[1]).toEqual({
      expectedRevision: 7,
      patch: { minimumRemaining: "9.50" },
    });
  });

  it("disables mutations when capability envelope has errors even if canSet is true", async () => {
    const result = routes();
    result["/api/v1/capabilities"] = envelope(writableCapabilities(), {
      modelControl: { ...sourceFresh, source: "modelControl" },
    }, [{
      code: "MODEL_CONTROL_DEGRADED",
      message: "policy source incomplete",
      source: "modelControl",
      retryable: true,
    }]);
    renderAppAt("/model-policy", result);
    const region = await screen.findByRole("region", { name: "模型策略" });
    expect(await screen.findByText("policy source incomplete")).toBeVisible();
    expect(within(region).getByRole("button", { name: "保存项目默认" })).toBeDisabled();
    expect(within(region).getByRole("button", { name: "恢复继承全局" })).toBeDisabled();
    expect(within(region).getByLabelText("最低剩余预算")).toBeDisabled();
  });
});
