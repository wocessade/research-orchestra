import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { envelope, renderAppAt, standardRoutes } from "./helpers";

const policy = {
  projectId: "bogda-main", source: "project", revision: 4, inheritsGlobal: false,
  minimumRemaining: "6.00", workloadSafetyMargin: "1.25", defaultModelTier: "auto",
  allowAutoUpgrade: true, allowFlashDowngrade: true, preferOffPeak: true, autoResume: false,
  criticalNotifications: true, usageSnapshotStaleAfterSeconds: 120,
  priceCatalog: { status: "ready", version: "deepseek-v4-0813", effectiveAt: "2026-08-28T00:00:00Z", reviewBy: "2026-09-01T00:00:00Z", source: "deepseek" },
  hardSafetyBaselines: { budgetIncreaseApprovalRequired: true, decideAuditNoSilentDowngrade: true, humanExternalActions: true, humanScientificJudgment: true, minimumRemainingEnforced: true, promptArchivingRequired: true, structuredEventLog: true, unknownUsageRecoveryGate: true, usageSnapshotFailClosed: true },
};

function routes() {
  const result = standardRoutes();
  result["/api/v1/capabilities"] = envelope({ ...(result["/api/v1/capabilities"] as any).data as object, canSetModelPolicy: true, canPreparePaidRun: true });
  result["/api/v1/model-policy"] = envelope(policy);
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

  it("restores inheritance and sends the current revision", async () => {
    const user = userEvent.setup();
    const result = routes();
    let body: unknown;
    result["/api/v1/model-policy/projects/bogda-main"] = ({ init }) => {
      body = JSON.parse(String(init?.body));
      return envelope({ command: "setProjectModelPolicy", resourceId: "bogda-main", acceptedAt: "2026-08-29T00:00:00Z", snapshot: { ...policy, source: "global", projectId: "bogda-main", inheritsGlobal: true, revision: 5 } });
    };
    renderAppAt("/model-policy", result);
    const region = await screen.findByRole("region", { name: "模型策略" });
    await user.click(within(region).getByRole("button", { name: "恢复继承全局" }));
    await user.click(screen.getByRole("button", { name: "确认恢复继承" }));
    expect(body).toEqual({ expectedRevision: 4, patch: null });
    expect(await within(region).findByText("继承全局")).toBeVisible();
  });

  it("adopts currentResource on conflict but requires explicit re-confirmation", async () => {
    const user = userEvent.setup();
    const result = routes();
    const current = { ...policy, defaultModelTier: "flash", revision: 7 };
    result["/api/v1/model-policy/projects/bogda-main"] = () => new Response(JSON.stringify(envelope(null, {}, [{ code: "RESOURCE_CHANGED", message: "changed", source: "modelControl", retryable: false, details: { currentResource: current } }])), { status: 409, headers: { "Content-Type": "application/json" } });
    renderAppAt("/model-policy", result);
    const region = await screen.findByRole("region", { name: "模型策略" });
    await user.click(within(region).getByRole("button", { name: "恢复继承全局" }));
    await user.click(screen.getByRole("button", { name: "确认恢复继承" }));
    expect(await screen.findByText("策略已被其他操作修改，请重新确认")).toBeVisible();
    expect(within(region).getByText("7")).toBeVisible();
    expect(screen.queryByRole("button", { name: "确认恢复继承" })).not.toBeInTheDocument();
  });
});
