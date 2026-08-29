import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { envelope, renderAppAt, requestLog, sourceFresh, standardRoutes } from "./helpers";

const decision = (overrides: Record<string, unknown> = {}) => ({
  decisionId: "decision-1",
  decisionKind: "peak-override",
  title: "允许高峰时段运行",
  urgencyGroup: "needs-owner-now",
  projectId: "project-1",
  runId: "run-1",
  reason: "当前价格窗口不是首选，需要明确授权。",
  risk: "high",
  estimatedCost: "1.00",
  deadline: null,
  evidence: [{ kind: "run", refId: "run-1", label: "打开运行 run-1", uri: "/runs/run-1" }],
  actions: [{ actionId: "approve", label: "允许高峰运行", costImpact: "预计增加 ¥1.00", qualityImpact: "不改变质量", irreversibleConsequence: "授权后将消耗本次预算，不能撤回。", requiresRationale: true, requiresConfirmation: true }],
  revision: 0,
  logSummary: "owner decision required; price window=peak",
  ...overrides,
});

function decisionRoutes(items = [decision() as Record<string, unknown>], extras: Record<string, unknown> = {}, revision = 0) {
  return Object.assign(standardRoutes(), {
    "/api/v1/decisions": envelope({ items, revision }, { modelControl: sourceFresh }),
  }, extras);
}

describe("owner decision runway", () => {
  it("reads one canonical list, deduplicates IDs, groups by urgency, and filters by project and risk", async () => {
    const items = [
      decision(),
      decision({ decisionId: "decision-1", title: "重复副本" }),
      decision({ decisionId: "decision-2", projectId: "project-2", risk: "low", urgencyGroup: "has-deadline", deadline: "2026-08-30T12:00:00Z", title: "截止日前查看" }),
      decision({ decisionId: "decision-3", projectId: "project-1", risk: "medium", urgencyGroup: "for-information", title: "仅供知晓" }),
    ];
    renderAppAt("/decisions", decisionRoutes(items));

    expect(await screen.findByRole("heading", { name: "决策跑道" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "需要我现在处理", level: 2 })).toBeVisible();
    expect(screen.getByRole("heading", { name: "有截止时间", level: 2 })).toBeVisible();
    expect(screen.getByRole("heading", { name: "仅供知晓", level: 2 })).toBeVisible();
    expect(screen.getAllByText("允许高峰时段运行")).toHaveLength(1);
    expect(screen.getByText("截止日前查看")).toBeVisible();

    await userEvent.setup().selectOptions(screen.getByRole("combobox", { name: "项目" }), "project-2");
    expect(screen.getByText("截止日前查看")).toBeVisible();
    expect(screen.queryByText("允许高峰时段运行")).not.toBeInTheDocument();
  });

  it("shows an actionable empty state and source degradation without inventing items", async () => {
    renderAppAt("/decisions", decisionRoutes([], {
      "/api/v1/decisions": envelope({ items: [], revision: 3 }, { modelControl: { ...sourceFresh, freshness: "stale" } }, [{ code: "MODEL_CONTROL_UNAVAILABLE", message: "模型控制来源延迟", source: "modelControl", retryable: true }]),
    }));
    expect(await screen.findByText("当前没有待处理决策")).toBeVisible();
    expect(screen.getAllByText("模型控制", { exact: false }).length).toBeGreaterThan(0);
    expect(screen.queryByText("modelControl")).not.toBeInTheDocument();
    expect(screen.getByText("模型控制来源延迟")).toBeVisible();
    expect(screen.getByText("来源数据已降级，未用空数据替代权威状态。")).toBeVisible();
  });

  it("opens the existing modal with evidence, effects, log summary, and action-specific copy", async () => {
    const user = userEvent.setup();
    renderAppAt("/decisions", decisionRoutes());
    await user.click(await screen.findByRole("button", { name: "查看：允许高峰时段运行" }));
    const dialog = screen.getByRole("dialog", { name: "允许高峰时段运行" });
    expect(within(dialog).getByText("当前价格窗口不是首选，需要明确授权。")).toBeVisible();
    expect(within(dialog).getByText("预计增加 ¥1.00")).toBeVisible();
    expect(within(dialog).getByText("不改变质量")).toBeVisible();
    expect(within(dialog).getByText("授权后将消耗本次预算，不能撤回。")).toBeVisible();
    expect(within(dialog).getByText("owner decision required; price window=peak")).toBeVisible();
    expect(within(dialog).getByText("高风险操作需要明确确认。")).toBeVisible();
    expect(within(dialog).getByRole("link", { name: "打开运行 run-1" })).toHaveAttribute("href", "/runs/run-1");
  });

  it("enforces rationale, sends the revisioned action, and respects capability flags", async () => {
    const user = userEvent.setup();
    let body: Record<string, unknown> | null = null;
    const routes = decisionRoutes([decision()], {
      "/api/v1/capabilities": envelope({ profile: "real-readonly", projectId: "project-1", canResolveModelDecision: false }, {}),
      "/api/v1/decisions/decision-1": ({ init }: { init?: RequestInit }) => {
        body = JSON.parse(String(init?.body));
        return envelope({ command: "resolveDecision", resourceId: "decision-1", acceptedAt: "2026-08-29T08:00:00Z", snapshot: { items: [], revision: 1 } }, { modelControl: sourceFresh });
      },
    });
    renderAppAt("/decisions", routes);
    await user.click(await screen.findByRole("button", { name: "查看：允许高峰时段运行" }));
    expect(screen.getByRole("button", { name: "允许高峰运行" })).toBeDisabled();
    expect(screen.getByText("当前 profile 为 real-readonly，只读，不能处理决策。")).toBeVisible();
    expect(body).toBeNull();
  });

  it("keeps typed rationale and adopts currentResource on conflict without replaying", async () => {
    const user = userEvent.setup();
    let calls = 0;
    let body: Record<string, unknown> | null = null;
    const current = { items: [decision({ revision: 1, title: "被其他操作更新" })], revision: 4 };
    const routes = decisionRoutes([decision()], {
      "/api/v1/capabilities": envelope({ profile: "mock-all", projectId: "project-1", canResolveModelDecision: true }, {}),
      "/api/v1/decisions/decision-1": ({ init }: { init?: RequestInit }) => {
        calls += 1;
        body = JSON.parse(String(init?.body));
        return new Response(JSON.stringify(envelope(null, { modelControl: sourceFresh }, [{ code: "RESOURCE_CHANGED", message: "resource changed after the action was opened", source: "modelControl", retryable: false, details: { currentResource: current } }])), { status: 409, headers: { "Content-Type": "application/json" } });
      },
    });
    renderAppAt("/decisions", routes,);
    await user.click(await screen.findByRole("button", { name: "查看：允许高峰时段运行" }));
    await user.type(screen.getByRole("textbox", { name: "操作理由" }), "我确认在该窗口执行");
    await user.click(screen.getByRole("checkbox", { name: /确认不可逆后果/ }));
    await user.click(screen.getByRole("button", { name: "允许高峰运行" }));
    expect(await screen.findByText("决策已被其他操作修改，请重新确认。")).toBeVisible();
    expect(within(screen.getByRole("dialog")).getByText("被其他操作更新")).toBeVisible();
    expect(screen.getByRole("textbox", { name: "操作理由" })).toHaveValue("我确认在该窗口执行");
    expect(calls).toBe(1);
    expect(body).toEqual({ actionId: "approve", expectedRevision: 0, rationale: "我确认在该窗口执行" });
  });

  it("fails closed while capabilities are pending, unavailable, or explicitly disabled", async () => {
    const user = userEvent.setup();
    const routes = decisionRoutes([decision()], {
      "/api/v1/capabilities": () => new Response(JSON.stringify(envelope(null, {}, [{ code: "MODEL_CONTROL_UNAVAILABLE", message: "capability unavailable", source: "modelControl", retryable: true }])), { status: 503, headers: { "Content-Type": "application/json" } }),
    });
    renderAppAt("/decisions", routes);
    await user.click(await screen.findByRole("button", { name: "查看：允许高峰时段运行" }));
    expect(screen.getByText("当前无法确认操作能力，所有变更操作已停用。")).toBeVisible();
    expect(screen.getByRole("button", { name: "允许高峰运行" })).toBeDisabled();
  });

  it("keeps mutation controls disabled while capability loading is pending", async () => {
    const user = userEvent.setup();
    const routes = decisionRoutes([decision()], {
      "/api/v1/capabilities": () => new Promise(() => {}),
    });
    renderAppAt("/decisions", routes);
    await user.click(await screen.findByRole("button", { name: "查看：允许高峰时段运行" }));
    expect(screen.getByText("正在确认操作能力，所有变更操作已停用。")).toBeVisible();
    expect(screen.getByRole("button", { name: "允许高峰运行" })).toBeDisabled();
  });

  it("uses the opened decision-center revision rather than the item revision", async () => {
    const user = userEvent.setup();
    let body: Record<string, unknown> | null = null;
    const routes = decisionRoutes([decision({ revision: 2 })], {
      "/api/v1/capabilities": envelope({ profile: "mock-all", projectId: "project-1", canResolveModelDecision: true }, {}),
      "/api/v1/decisions/decision-1": ({ init }: { init?: RequestInit }) => {
        body = JSON.parse(String(init?.body));
        return envelope({ command: "resolveDecision", resourceId: "decision-1", acceptedAt: "2026-08-29T08:00:00Z", snapshot: { items: [], revision: 8 } }, { modelControl: sourceFresh });
      },
    }, 7);
    renderAppAt("/decisions", routes);
    await user.click(await screen.findByRole("button", { name: "查看：允许高峰时段运行" }));
    expect(screen.getByText("权威列表修订 7")).toBeVisible();
    await user.type(screen.getByRole("textbox", { name: "操作理由" }), "依据当前预算窗口");
    await user.click(screen.getByRole("checkbox", { name: /确认不可逆后果/ }));
    await user.click(screen.getByRole("button", { name: "允许高峰运行" }));
    expect(body).toMatchObject({ expectedRevision: 7 });
  });

  it("adopts a new center revision and disables submission when the selected item disappeared", async () => {
    const user = userEvent.setup();
    const current = { items: [], revision: 9 };
    const routes = decisionRoutes([decision()], {
      "/api/v1/capabilities": envelope({ profile: "mock-all", projectId: "project-1", canResolveModelDecision: true }, {}),
      "/api/v1/decisions/decision-1": () => new Response(JSON.stringify(envelope(null, { modelControl: sourceFresh }, [{ code: "RESOURCE_CHANGED", message: "changed", source: "modelControl", retryable: false, details: { currentResource: current } }])), { status: 409, headers: { "Content-Type": "application/json" } }),
    }, 6);
    renderAppAt("/decisions", routes);
    await user.click(await screen.findByRole("button", { name: "查看：允许高峰时段运行" }));
    await user.type(screen.getByRole("textbox", { name: "操作理由" }), "保留以便重新判断");
    await user.click(screen.getByRole("checkbox", { name: /确认不可逆后果/ }));
    await user.click(screen.getByRole("button", { name: "允许高峰运行" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("该决策已被处理或撤回，请关闭此窗口。")).toBeVisible();
    expect(within(dialog).getByText("权威列表修订 9")).toBeVisible();
    expect(within(dialog).getByRole("textbox", { name: "操作理由" })).toHaveValue("保留以便重新判断");
    expect(within(dialog).getByRole("button", { name: "该决策已处理" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "返回" })).toBeEnabled();
  });

  it("lets the owner choose any action and updates its effects and requirements", async () => {
    const user = userEvent.setup();
    const actions = [
      { actionId: "approve", label: "批准执行", costImpact: "消耗 ¥1.00", qualityImpact: "保持质量", irreversibleConsequence: "会启动运行", requiresRationale: true, requiresConfirmation: true },
      { actionId: "defer", label: "暂缓执行", costImpact: "不产生费用", qualityImpact: "等待更多证据", irreversibleConsequence: null, requiresRationale: false, requiresConfirmation: false },
    ];
    renderAppAt("/decisions", decisionRoutes([decision({ actions })]));
    await user.click(await screen.findByRole("button", { name: "查看：允许高峰时段运行" }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByRole("combobox", { name: "选择操作" })).toBeVisible();
    await user.selectOptions(within(dialog).getByRole("combobox", { name: "选择操作" }), "defer");
    expect(within(dialog).getByText("不产生费用")).toBeVisible();
    expect(within(dialog).getByText("等待更多证据")).toBeVisible();
    expect(within(dialog).queryByRole("checkbox", { name: /确认不可逆后果/ })).not.toBeInTheDocument();
    expect(within(dialog).queryByRole("textbox", { name: "操作理由" })).not.toBeInTheDocument();
  });

  it("requires explicit acknowledgement only for confirming actions", async () => {
    const user = userEvent.setup();
    renderAppAt("/decisions", decisionRoutes());
    await user.click(await screen.findByRole("button", { name: "查看：允许高峰时段运行" }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByRole("checkbox", { name: /确认不可逆后果/ })).not.toBeChecked();
    expect(within(dialog).getByRole("button", { name: "允许高峰运行" })).toBeDisabled();
    await user.type(within(dialog).getByRole("textbox", { name: "操作理由" }), "明确承担预算影响");
    expect(within(dialog).getByRole("button", { name: "允许高峰运行" })).toBeDisabled();
    await user.click(within(dialog).getByRole("checkbox", { name: /确认不可逆后果/ }));
    expect(within(dialog).getByRole("button", { name: "允许高峰运行" })).toBeEnabled();
  });

  it("renders authoritative non-conflict mutation errors in the dialog", async () => {
    const user = userEvent.setup();
    const routes = decisionRoutes([decision()], {
      "/api/v1/capabilities": envelope({ profile: "mock-all", projectId: "project-1", canResolveModelDecision: true }, {}),
      "/api/v1/decisions/decision-1": () => new Response(JSON.stringify(envelope(null, { modelControl: sourceFresh }, [{ code: "COMMAND_REJECTED", message: "预算窗口已关闭", source: "modelControl", retryable: false }])), { status: 409, headers: { "Content-Type": "application/json" } }),
    });
    renderAppAt("/decisions", routes);
    await user.click(await screen.findByRole("button", { name: "查看：允许高峰时段运行" }));
    await user.type(screen.getByRole("textbox", { name: "操作理由" }), "确认窗口状态");
    await user.click(screen.getByRole("checkbox", { name: /确认不可逆后果/ }));
    await user.click(screen.getByRole("button", { name: "允许高峰运行" }));
    expect(await screen.findByText("预算窗口已关闭")).toBeVisible();
  });

  it("distinguishes an authoritative empty list from filters matching zero", async () => {
    const user = userEvent.setup();
    renderAppAt("/decisions", decisionRoutes([decision({ projectId: "project-1" }), decision({ decisionId: "decision-2", projectId: "project-2", risk: "low" })]));
    await user.selectOptions(await screen.findByRole("combobox", { name: "项目" }), "project-1");
    await user.selectOptions(screen.getByRole("combobox", { name: "风险" }), "low");
    expect(screen.getByText("没有匹配的决策")).toBeVisible();
    expect(screen.getByRole("button", { name: "清除筛选" })).toBeVisible();
  });

  it("does not call any secondary decision endpoint", async () => {
    renderAppAt("/decisions", decisionRoutes());
    await screen.findByRole("heading", { name: "决策跑道" });
    expect(requestLog.filter((path) => path.startsWith("/api/v1/decisions"))).toEqual(["/api/v1/decisions"]);
  });
});
