import { cleanup, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { RunBudgetPanel } from "../../frontend/src/components/RunBudgetPanel";
import type { Schemas } from "../../frontend/src/api/types";
import { envelope, installApi, renderWithClient, sourceFresh, sourceStale } from "./helpers";

const baseBudget: Schemas["ModelBudgetSnapshot"] = {
  runId: "run-budget-1",
  projectId: "bogda-main",
  state: "ready",
  requestedModelTier: "auto",
  effectiveModelTier: "flash",
  effectiveAutonomyMode: "supervised",
  intent: "execute",
  currency: "CNY",
  authorizedCeiling: "12.00",
  expectedCost: "3.20",
  usedCost: "1.10",
  reservedCost: "0.80",
  remainingCost: "10.10",
  pricePeriod: "off-peak",
  scheduledStart: "2026-08-29T10:00:00+08:00",
  pauseReason: null,
  recoveryConditions: ["余额恢复后继续"],
  decisionId: "decision-budget-1",
  revision: 4,
  events: [{ eventId: "event-1", eventType: "budget_reserved", occurredAt: "2026-08-29T09:00:00Z", summary: "预算已预留" }],
  artifacts: [
    { artifactId: "artifact-prompt-1", kind: "prompt", uri: "artifact://prompt-1" },
    { artifactId: "artifact-stdout-1", kind: "stdout", uri: "artifact://stdout-1" },
    { artifactId: "artifact-stderr-1", kind: "stderr", uri: "artifact://stderr-1" },
    { artifactId: "receipt-1", kind: "receipt", uri: "artifact://receipt-1" },
    { artifactId: "log-1", kind: "log", uri: "artifact://log-1" },
  ],
};

function renderBudget(budget = baseBudget, sources = { modelControl: sourceFresh }) {
  installApi({ "/api/v1/runs/run-budget-1/model-budget": envelope(budget, sources) });
  return renderWithClient(<MemoryRouter><RunBudgetPanel runId="run-budget-1" /></MemoryRouter>);
}

describe("RunBudgetPanel state matrix", () => {
  afterEach(() => cleanup());
  it.each([
    ["ready", "预算可用", "当前预算状态可继续"],
    ["stale", "快照已过期", "请回到决策中心重新确认"],
    ["insufficient", "余额不足", "余额恢复后再继续"],
    ["scheduled-off-peak", "已安排低峰时段", "等待计划开始"],
    ["awaiting-approval", "等待批准", "前往决策中心"],
    ["usage-unknown", "用量未知", "等待权威用量恢复"],
  ])("renders distinct recovery copy for %s", async (state, label, recovery) => {
    const budgetState = state as Schemas["BudgetState"];
    renderBudget({ ...baseBudget, state: budgetState, pauseReason: budgetState === "usage-unknown" ? "供应商未返回用量" : null, recoveryConditions: [recovery] });
    expect(await screen.findByText(label)).toBeVisible();
    expect(screen.getAllByText(recovery).length).toBeGreaterThan(0);
  });

  it("renders the exact server ledger strings, tiers, intent, mode, timing, events, and metadata-only references", async () => {
    renderBudget();
    expect(await screen.findByText("12.00 CNY")).toBeVisible();
    expect(screen.getByText("1.10 CNY")).toBeVisible();
    expect(screen.getByText("0.80 CNY")).toBeVisible();
    expect(screen.getByText("10.10 CNY")).toBeVisible();
    expect(screen.getByText("auto")).toBeVisible();
    expect(screen.getByText("flash")).toBeVisible();
    expect(screen.getByText("execute")).toBeVisible();
    expect(screen.getByText("supervised")).toBeVisible();
    expect(screen.getByText("off-peak")).toBeVisible();
    expect(screen.getByText("预算已预留")).toBeVisible();
    expect(screen.getByRole("link", { name: /artifact-prompt-1/ })).toHaveAttribute("href", "artifact://prompt-1");
    expect(screen.getByRole("link", { name: /receipt-1/ })).toHaveAttribute("href", "artifact://receipt-1");
    expect(screen.queryByText(/secret|top-secret|raw prompt|模型输出内容/)).not.toBeInTheDocument();
  });

  it("renders unknown effective tier without inventing a fallback and links only to the canonical decision", async () => {
    renderBudget({ ...baseBudget, effectiveModelTier: null, decisionId: "decision-unknown-tier" });
    expect(await screen.findByText("未知")).toBeVisible();
    expect(screen.getByRole("link", { name: /decision-unknown-tier/ })).toHaveAttribute("href", "/decisions#decision-unknown-tier");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("keeps fixed safety invariants explanatory and immutable", async () => {
    renderBudget();
    const safety = await screen.findByText("系统不变量说明");
    expect(safety).toBeVisible();
    expect(screen.getAllByText(/预算增加需批准|未知用量采用 fail-closed|结构化事件日志/).length).toBeGreaterThan(0);
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });

  it("always shows the usage-unknown safety invariant before weak server recovery conditions", async () => {
    renderBudget({ ...baseBudget, state: "usage-unknown", recoveryConditions: ["稍后查看余额"] });
    expect(await screen.findByText("用量未知")).toBeVisible();
    const recovery = await screen.findByRole("region", { name: "恢复条件" });
    expect(within(recovery).getByText("必须人工核对用量后才能恢复。")).toBeVisible();
    expect(within(recovery).getByText("同一调用不得盲目重试。")).toBeVisible();
    expect(within(recovery).getByText("稍后查看余额")).toBeVisible();
  });

  it("keeps the usage-unknown safety invariant when the server supplies no recovery conditions", async () => {
    renderBudget({ ...baseBudget, state: "usage-unknown", recoveryConditions: [] });
    const recovery = await screen.findByRole("region", { name: "恢复条件" });
    expect(within(recovery).getByText("必须人工核对用量后才能恢复。")).toBeVisible();
    expect(within(recovery).getByText("同一调用不得盲目重试。")).toBeVisible();
  });

  it("renders an accessible named loading region", async () => {
    installApi({ "/api/v1/runs/run-budget-1/model-budget": () => new Promise(() => {}) });
    renderWithClient(<MemoryRouter><RunBudgetPanel runId="run-budget-1" /></MemoryRouter>);
    expect(screen.getByRole("region", { name: "运行预算" })).toBeVisible();
    expect(screen.getByText("正在读取权威来源…")).toBeVisible();
  });

  it("renders the authoritative 404 envelope with source metadata and distinct copy", async () => {
    installApi({
      "/api/v1/runs/run-budget-1/model-budget": () => new Response(JSON.stringify(envelope(null, { modelControl: sourceFresh }, [{ code: "RUN_BUDGET_NOT_FOUND", message: "预算审计快照不存在", source: "modelControl", retryable: false }])), { status: 404 }),
    });
    renderWithClient(<MemoryRouter><RunBudgetPanel runId="run-budget-1" /></MemoryRouter>);
    expect(await screen.findByText("没有找到该运行的预算审计快照。")).toBeVisible();
    expect(screen.getByText("预算审计快照不存在")).toBeVisible();
    expect(screen.getAllByText("模型控制", { exact: false }).length).toBeGreaterThan(0);
  });

  it("renders the authoritative 503 envelope with source metadata and unavailable copy", async () => {
    installApi({
      "/api/v1/runs/run-budget-1/model-budget": () => new Response(JSON.stringify(envelope(null, { modelControl: sourceStale }, [{ code: "MODEL_CONTROL_UNAVAILABLE", message: "来源延迟", source: "modelControl", retryable: true }])), { status: 503 }),
    });
    renderWithClient(<MemoryRouter><RunBudgetPanel runId="run-budget-1" /></MemoryRouter>);
    expect(await screen.findByText("运行预算暂不可用")).toBeVisible();
    expect(screen.getByText("保留当前判断，不以空数据替代来源故障。")).toBeVisible();
    expect(screen.getByText("来源延迟")).toBeVisible();
    expect(screen.getAllByText("模型控制", { exact: false }).length).toBeGreaterThan(0);
  });

  it("keeps a successful stale-source envelope distinct from a transport error", async () => {
    renderBudget({ ...baseBudget, recoveryConditions: ["使用已观测快照"] }, { modelControl: sourceStale });
    expect(await screen.findByText("预算可用")).toBeVisible();
    expect(screen.getByText("预算来源陈旧；以下内容保留为已观测快照，不代表当前余额。")).toBeVisible();
    expect(screen.getAllByText("使用已观测快照").length).toBeGreaterThan(0);
  });
});
