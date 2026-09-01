import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { completedRun, envelope, renderAppAt, sourceFresh, standardRoutes } from "./helpers";

const awaitingBudget = {
  runId: "run-completed-unreviewed",
  projectId: "bogda-main",
  state: "awaiting-approval",
  currency: "CNY",
  expectedCost: "21.00",
  authorizedCeiling: "25.00",
  usedCost: "0.00",
  reservedCost: "0.00",
  remainingCost: "25.00",
  decisionId: null,
  revision: 1,
  intent: "execute",
  requestedModelTier: "flash",
  effectiveModelTier: "flash",
  effectiveAutonomyMode: "supervised",
  pricePeriod: "peak",
  scheduledStart: null,
  pauseReason: "owner_approval_required",
  recoveryConditions: ["签发绑定该 envelope 的凭证后再准入"],
  events: [],
  artifacts: [],
};

function detailRoutes() {
  const routes = standardRoutes();
  routes["/api/v1/runs/run-completed-unreviewed/model-budget"] = envelope(
    awaitingBudget,
    { modelControl: { ...sourceFresh, source: "modelControl" } },
  );
  routes["/api/v1/model-policy"] = envelope(
    {
      projectId: "bogda-main",
      source: "global",
      revision: 1,
      inheritsGlobal: true,
      minimumRemaining: "1.00",
      workloadSafetyMargin: "1.25",
      defaultModelTier: "auto",
      allowAutoUpgrade: false,
      allowFlashDowngrade: true,
      preferOffPeak: true,
      autoResume: false,
      criticalNotifications: true,
      usageSnapshotStaleAfterSeconds: 120,
      priceCatalog: {
        status: "ready",
        version: "deepseek-cn-2026-08-28",
        effectiveAt: "2026-08-28T00:00:00Z",
        reviewBy: "2026-09-28T00:00:00Z",
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
    },
    { modelControl: { ...sourceFresh, source: "modelControl" } },
  );
  return routes;
}

describe("owner approval mint and artifact cleanup", () => {
  it("issues a >20 CNY credential from the budget panel", async () => {
    const user = userEvent.setup();
    const routes = detailRoutes();
    let issued = false;
    routes["/api/v1/runs/run-completed-unreviewed/approvals"] = ({ init }) => {
      issued = true;
      expect(JSON.parse(String(init?.body))).toMatchObject({
        expectedCost: "21.00",
        authorizedCeiling: "25.00",
        requestedTier: "flash",
        pricingVersion: "deepseek-cn-2026-08-28",
      });
      return envelope({
        command: "issueOwnerApproval",
        resourceId: "run-completed-unreviewed",
        acceptedAt: "2026-08-24T08:30:00Z",
        snapshot: {
          credentialId: "cred-1",
          runId: "run-completed-unreviewed",
          envelopeDigest: "abc",
          pricingVersion: "deepseek-cn-2026-08-28",
          authorizedCeilingCny: "25.00",
          actorId: "local-owner",
          issuedAt: "2026-08-24T08:30:00Z",
          expiresAt: "2026-08-24T09:30:00Z",
        },
      }, {});
    };
    renderAppAt("/runs/run-completed-unreviewed", routes);
    const mintButton = await screen.findByRole("button", { name: "签发超过 20 CNY 凭证" });
    await waitFor(() => expect(mintButton).toBeEnabled());
    await user.click(mintButton);
    expect(await screen.findByText(/cred-1/)).toBeVisible();
    expect(issued).toBe(true);
  });

  it("cleans stdout/stderr only after the delete-content confirm", async () => {
    const user = userEvent.setup();
    const routes = detailRoutes();
    let cleaned = false;
    routes["/api/v1/runs/run-completed-unreviewed/artifacts/cleanup"] = ({ init }) => {
      cleaned = true;
      expect(JSON.parse(String(init?.body))).toEqual({ confirm: "delete-content" });
      return envelope({
        command: "cleanupArtifacts",
        resourceId: "run-completed-unreviewed",
        acceptedAt: "2026-08-24T08:30:00Z",
        snapshot: { runId: "run-completed-unreviewed", actorId: "local-owner", deletedKinds: ["stdout", "stderr"] },
      }, {});
    };
    renderAppAt("/runs/run-completed-unreviewed", routes);
    await user.click(await screen.findByRole("button", { name: "清理产物内容" }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText(/events 保留/)).toBeVisible();
    await user.click(within(dialog).getByRole("button", { name: "确认删除内容" }));
    expect(await screen.findByText(/已删除 stdout、stderr/)).toBeVisible();
    expect(cleaned).toBe(true);
  });

  it("hides mint and cleanup when capability flags are false", async () => {
    const routes = detailRoutes();
    routes["/api/v1/capabilities"] = envelope({
      ...(standardRoutes()["/api/v1/capabilities"] as { data: Record<string, unknown> }).data,
      canIssueOwnerApproval: false,
      canCleanupArtifacts: false,
    }, {});
    renderAppAt("/runs/run-completed-unreviewed", routes);
    await screen.findByRole("heading", { name: "模型预算审计" });
    expect(screen.queryByRole("button", { name: "签发超过 20 CNY 凭证" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "清理产物内容" })).not.toBeInTheDocument();
  });
});
