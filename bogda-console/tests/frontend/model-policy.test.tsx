import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { envelope, renderAppAt, sourceFresh, sourceStale, standardRoutes } from "./helpers";

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
  result["/api/v1/model-policy"] = envelope({
    ...policy,
    projectId: null,
    source: "global",
    inheritsGlobal: false,
    revision: 2,
  }, {
    modelControl: { ...sourceFresh, source: "modelControl" },
  });
  result[`/api/v1/model-policy?projectId=${projectId}`] = envelope({ ...policy, projectId }, {
    modelControl: { ...sourceFresh, source: "modelControl" },
  });
  result["/api/v1/usage-balance"] = envelope({
    provider: "deepseek",
    available: true,
    totalBalance: "37.1250",
    currency: "CNY",
    observedAt: "2026-08-31T00:20:00Z",
    sourceStatus: "up",
  }, {
    usageBalance: { ...sourceFresh, source: "usageBalance" },
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
    expect(within(region).getByText("账户余额")).toBeVisible();
    expect(within(region).getByText("¥37.1250")).toBeVisible();
  });

  it("lets the owner edit the backend global policy with its own revision", async () => {
    const user = userEvent.setup();
    const result = routes();
    let body: unknown;
    result["/api/v1/model-policy/global"] = ({ init }) => {
      body = JSON.parse(String(init?.body));
      return envelope({
        command: "setGlobalModelPolicy",
        resourceId: "global",
        acceptedAt: "2026-08-31T00:21:00Z",
        snapshot: {
          ...policy,
          projectId: null,
          source: "global",
          inheritsGlobal: false,
          minimumRemaining: "12.00",
          revision: 3,
        },
      });
    };
    renderAppAt("/model-policy", result);
    const region = await screen.findByRole("region", { name: "模型策略" });
    await user.click(within(region).getByRole("button", { name: "全局默认" }));
    const remaining = within(region).getByLabelText("最低剩余预算");
    await user.clear(remaining);
    await user.type(remaining, "12.00");
    await user.click(within(region).getByRole("button", { name: "保存全局默认" }));
    await user.click(screen.getByRole("button", { name: "确认保存" }));
    expect(body).toEqual({ expectedRevision: 2, patch: { minimumRemaining: "12.00" } });
  });

  it("keeps policy controls usable when balance is unavailable", async () => {
    const result = routes();
    result["/api/v1/usage-balance"] = () => new Response(JSON.stringify(envelope(null, {}, [{
      code: "USAGE_BALANCE_UNAVAILABLE",
      message: "余额来源暂不可用",
      source: "usageBalance",
      retryable: true,
    }])), { status: 503, headers: { "Content-Type": "application/json" } });
    renderAppAt("/model-policy", result);
    const region = await screen.findByRole("region", { name: "模型策略" });
    expect(await within(region).findByText("余额来源暂不可用")).toBeVisible();
    expect(within(region).getByLabelText("最低剩余预算")).toBeEnabled();
  });

  it("keeps a successful balance visible when model policy is unavailable", async () => {
    const result = routes();
    const unavailable = () => new Response(JSON.stringify(envelope(null, {}, [{
      code: "MODEL_CONTROL_UNAVAILABLE",
      message: "模型策略来源暂不可用",
      source: "modelControl",
      retryable: false,
    }])), { status: 503, headers: { "Content-Type": "application/json" } });
    result["/api/v1/model-policy"] = unavailable;
    result["/api/v1/model-policy?projectId=bogda-main"] = unavailable;

    renderAppAt("/model-policy", result);

    const region = await screen.findByRole("region", { name: "模型策略" });
    expect(await within(region).findByText("¥37.1250")).toBeVisible();
    expect(within(region).getByText("模型策略来源暂不可用")).toBeVisible();
  });

  it("can switch to an available global policy when the project policy fails", async () => {
    const user = userEvent.setup();
    const result = routes();
    result["/api/v1/model-policy?projectId=bogda-main"] = () => new Response(
      JSON.stringify(envelope(null, {}, [{
        code: "MODEL_CONTROL_UNAVAILABLE",
        message: "项目策略来源暂不可用",
        source: "modelControl",
        retryable: false,
      }])),
      { status: 503, headers: { "Content-Type": "application/json" } },
    );

    renderAppAt("/model-policy", result);

    const region = await screen.findByRole("region", { name: "模型策略" });
    expect(within(region).getByText("模型策略来源暂不可用")).toBeVisible();
    await user.click(within(region).getByRole("button", { name: "全局默认" }));
    expect(await within(region).findByRole("heading", { name: "全局默认" })).toBeVisible();
  });

  it("shows a rejected policy mutation instead of swallowing it", async () => {
    const user = userEvent.setup();
    const result = routes();
    result["/api/v1/model-policy/projects/bogda-main"] = () => new Response(
      JSON.stringify(envelope(null, {}, [{
        code: "COMMAND_REJECTED",
        message: "策略写入被服务端拒绝",
        source: "modelControl",
        retryable: false,
      }])),
      { status: 409, headers: { "Content-Type": "application/json" } },
    );
    renderAppAt("/model-policy", result);
    const region = await screen.findByRole("region", { name: "模型策略" });
    await user.clear(within(region).getByLabelText("最低剩余预算"));
    await user.type(within(region).getByLabelText("最低剩余预算"), "9.00");
    await user.click(within(region).getByRole("button", { name: "保存项目默认" }));
    await user.click(screen.getByRole("button", { name: "确认保存" }));
    expect(await within(region).findByRole("alert")).toHaveTextContent("策略写入被服务端拒绝");
  });

  it("blocks policy writes when the authoritative policy snapshot is stale", async () => {
    const result = routes();
    result["/api/v1/model-policy?projectId=bogda-main"] = envelope(policy, {
      modelControl: { ...sourceStale, source: "modelControl" },
    });
    renderAppAt("/model-policy", result);
    const region = await screen.findByRole("region", { name: "模型策略" });
    expect(await within(region).findByLabelText("最低剩余预算")).toBeDisabled();
    expect(within(region).getByText(/权威快照不是实时数据/)).toBeVisible();
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
