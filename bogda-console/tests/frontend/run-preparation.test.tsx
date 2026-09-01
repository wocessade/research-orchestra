import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { envelope, renderAppAt, sourceFresh, standardRoutes } from "./helpers";

const preview = {
  preparationId: "prep-42",
  projectId: "bogda-main",
  policyRevision: 4,
  intent: "execute",
  requestedModelTier: "pro",
  effectiveModelTier: "pro",
  fallbackModelTier: "flash",
  effectiveAutonomyMode: "supervised",
  deadline: "2026-08-29T14:00:00Z",
  scheduledStart: "2026-08-29T12:00:00Z",
  pricePeriod: "off-peak",
  confirmed: false,
  workload: { expectedCalls: 4, inputTokens: 100000, outputTokens: 20000, runtimeMinutes: 18 },
  allowedPreferences: {
    allowAutoUpgrade: true,
    allowFlashDowngrade: true,
    autoResume: false,
    preferOffPeak: true,
  },
  budget: {
    runId: "preview",
    projectId: "bogda-main",
    revision: 4,
    state: "ready",
    currency: "CNY",
    requestedModelTier: "pro",
    effectiveModelTier: "pro",
    effectiveAutonomyMode: "supervised",
    intent: "execute",
    authorizedCeiling: "18.00",
    expectedCost: "12.00",
    usedCost: "0.00",
    reservedCost: "0.00",
    remainingCost: "18.00",
    pricePeriod: "off-peak",
    scheduledStart: "2026-08-29T12:00:00Z",
    pauseReason: null,
    recoveryConditions: [],
    decisionId: null,
    artifacts: [],
    events: [],
  },
};

const modelControl = { ...sourceFresh, source: "modelControl" };

function writableCapabilities() {
  return {
    profile: "mock-all",
    projectId: "bogda-main",
    actorId: "local-owner",
    role: "owner",
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

function routes() {
  const result = standardRoutes();
  result["/api/v1/capabilities"] = envelope(writableCapabilities(), { modelControl });
  result["/api/v1/model-policy"] = envelope({
    projectId: "bogda-main",
    source: "global",
    revision: 4,
    inheritsGlobal: true,
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
      version: "v1",
      effectiveAt: "2026-08-28T00:00:00Z",
      reviewBy: "2026-09-04T00:00:00Z",
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
  }, { modelControl });
  result["/api/v1/deployments"] = envelope({
    items: [{
      deploymentId: "deployment-dorm",
      name: "alpine-assay",
      flowName: "alpine-assay",
      parameterSchema: {
        type: "object",
        properties: { sample: { type: "string", title: "Sample" } },
        required: ["sample"],
      },
      allowlisted: true,
      workPoolName: "dorm-x86",
      workQueueName: "cpu",
      schedules: [],
    }],
  });
  return result;
}

async function openPreparation() {
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "提交 alpine-assay" }));
  return { user, dialog: screen.getByRole("dialog", { name: "准备 alpine-assay" }) };
}

describe("RunPreparation", () => {
  it("keeps advanced fields progressive and does not preselect peak or Pro risk", async () => {
    renderAppAt("/infrastructure", routes());
    const { dialog, user } = await openPreparation();
    expect(within(dialog).getByRole("combobox", { name: "模型层级" })).toHaveValue("auto");
    expect(within(dialog).queryByLabelText("输入 tokens")).not.toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "展开工作量与截止时间" }));
    expect(within(dialog).getByLabelText("输入 tokens")).toBeVisible();
    expect(within(dialog).getByLabelText("截止时间")).toBeVisible();
    expect(within(dialog).getByRole("checkbox", { name: "偏好低峰时段" })).toBeChecked();
    expect(within(dialog).getByRole("checkbox", { name: "包内自动升级 Pro" })).not.toBeChecked();
  });

  it("previews on the server, invalidates on input change, then confirms separately before submit", async () => {
    const result = routes();
    const calls: { path: string; body: any }[] = [];
    result["/api/v1/run-preparations/preview"] = ({ init }) => {
      calls.push({ path: "preview", body: JSON.parse(String(init?.body)) });
      return envelope(preview, { modelControl });
    };
    result["/api/v1/deployments/deployment-dorm/runs"] = ({ init }) => {
      calls.push({ path: "submit", body: JSON.parse(String(init?.body)) });
      return envelope({
        command: "submitRun",
        resourceId: "run-1",
        acceptedAt: "2026-08-29T00:00:00Z",
        snapshot: {
          runId: "run-1",
          name: "alpine",
          state: { type: "SCHEDULED", name: "Scheduled", terminal: false, timestamp: "2026-08-29T00:00:00Z" },
          commandVersion: "v1",
        },
      });
    };
    renderAppAt("/infrastructure", result);
    const { dialog, user } = await openPreparation();
    await user.type(within(dialog).getByRole("textbox", { name: "Sample" }), "ridge");
    await user.click(within(dialog).getByRole("button", { name: "生成服务端预览" }));
    expect(await within(dialog).findByText("服务端预览")).toBeVisible();
    expect(within(dialog).getByText("PRO")).toBeVisible();
    expect(within(dialog).getByRole("button", { name: "确认并提交运行" })).toBeVisible();
    expect(calls).toHaveLength(1);
    await user.click(within(dialog).getByRole("button", { name: "确认并提交运行" }));
    expect(calls[1].path).toBe("submit");
    expect(calls[1].body).toMatchObject({ runPreparationId: "prep-42", parameters: { sample: "ridge" } });
    expect(calls[1].body.idempotencyKey).toMatch(/^bogda-console-deployment-dorm-/);
  });

  it("collects deadline and all allowed preferences in the preview request", async () => {
    const result = routes();
    let body: any;
    result["/api/v1/run-preparations/preview"] = ({ init }) => {
      body = JSON.parse(String(init?.body));
      return envelope(preview, { modelControl });
    };
    renderAppAt("/infrastructure", result);
    const { dialog, user } = await openPreparation();
    await user.click(within(dialog).getByRole("button", { name: "展开工作量与截止时间" }));
    await user.type(within(dialog).getByLabelText("截止时间"), "2026-08-29T14:00");
    await user.click(within(dialog).getByRole("checkbox", { name: "包内自动升级 Pro" }));
    await user.click(within(dialog).getByRole("checkbox", { name: "余额恢复后自动继续" }));
    await user.click(within(dialog).getByRole("button", { name: "生成服务端预览" }));
    await within(dialog).findByText("服务端预览");
    expect(body.deadline).toMatch(/^2026-08-29T14:00/);
    expect(body.allowedPreferences).toEqual({
      allowAutoUpgrade: true,
      allowFlashDowngrade: true,
      autoResume: true,
      preferOffPeak: true,
    });
  });

  it("returns to draft from preview review and requires a new preview", async () => {
    const result = routes();
    let previewCalls = 0;
    result["/api/v1/run-preparations/preview"] = () => {
      previewCalls += 1;
      return envelope(preview, { modelControl });
    };
    renderAppAt("/infrastructure", result);
    const { dialog, user } = await openPreparation();
    await user.click(within(dialog).getByRole("button", { name: "生成服务端预览" }));
    expect(await within(dialog).findByText("服务端预览")).toBeVisible();
    await user.click(within(dialog).getByRole("button", { name: "修改准备信息" }));
    expect(within(dialog).queryByText("服务端预览")).not.toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "生成服务端预览" })).toBeVisible();
    expect(within(dialog).queryByRole("button", { name: "确认并提交运行" })).not.toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "生成服务端预览" }));
    expect(await within(dialog).findByText("服务端预览")).toBeVisible();
    expect(previewCalls).toBe(2);
  });

  it("shows preview sources, errors, and price catalog without swallowing the envelope", async () => {
    const result = routes();
    result["/api/v1/run-preparations/preview"] = envelope(preview, { modelControl }, [{
      code: "USAGE_STALE",
      message: "usage snapshot is stale",
      source: "modelControl",
      retryable: true,
    }]);
    renderAppAt("/infrastructure", result);
    const { dialog, user } = await openPreparation();
    expect(within(dialog).getByText("v1")).toBeVisible();
    expect(within(dialog).getByText("ready")).toBeVisible();
    await user.click(within(dialog).getByRole("button", { name: "生成服务端预览" }));
    expect(await within(dialog).findByText("usage snapshot is stale")).toBeVisible();
    expect(within(dialog).getByRole("button", { name: "确认并提交运行" })).toBeDisabled();
  });

  it("fail-closes paid actions when capability envelope has errors", async () => {
    const result = routes();
    result["/api/v1/capabilities"] = envelope(writableCapabilities(), { modelControl }, [{
      code: "CAPABILITY_PARTIAL",
      message: "paid flags incomplete",
      source: "modelControl",
      retryable: true,
    }]);
    renderAppAt("/infrastructure", result);
    expect(await screen.findByText("paid flags incomplete")).toBeVisible();
    expect(screen.getByRole("button", { name: "提交 alpine-assay" })).toBeDisabled();
  });

  it("shows local coercion errors instead of a missing receipt", async () => {
    const result = routes();
    result["/api/v1/run-preparations/preview"] = envelope(preview, { modelControl });
    renderAppAt("/infrastructure", result);
    const { dialog, user } = await openPreparation();
    await user.click(within(dialog).getByRole("button", { name: "生成服务端预览" }));
    await within(dialog).findByText("服务端预览");
    await user.click(within(dialog).getByRole("button", { name: "确认并提交运行" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Sample 为必填项");
    expect(within(dialog).queryByText(/未获得权威回执/)).not.toBeInTheDocument();
  });

  it("blocks close while submit is waiting for the authoritative receipt", async () => {
    const result = routes();
    let release!: () => void;
    const gate = new Promise<void>((resolve) => { release = resolve; });
    result["/api/v1/run-preparations/preview"] = envelope(preview, { modelControl });
    result["/api/v1/deployments/deployment-dorm/runs"] = async () => {
      await gate;
      return envelope({
        command: "submitRun",
        resourceId: "run-busy",
        acceptedAt: "2026-08-29T00:00:00Z",
        snapshot: {
          runId: "run-busy",
          name: "alpine",
          state: { type: "SCHEDULED", name: "Scheduled", terminal: false, timestamp: "2026-08-29T00:00:00Z" },
          commandVersion: "v1",
        },
      });
    };
    renderAppAt("/infrastructure", result);
    const { dialog, user } = await openPreparation();
    await user.type(within(dialog).getByRole("textbox", { name: "Sample" }), "ridge");
    await user.click(within(dialog).getByRole("button", { name: "生成服务端预览" }));
    await within(dialog).findByText("服务端预览");
    await user.click(within(dialog).getByRole("button", { name: "确认并提交运行" }));
    expect(within(dialog).getByRole("button", { name: "返回" })).toBeDisabled();
    await user.keyboard("{Escape}");
    expect(screen.getByRole("dialog", { name: "准备 alpine-assay" })).toBeVisible();
    release();
    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "准备 alpine-assay" })).not.toBeInTheDocument();
    });
  });
});
