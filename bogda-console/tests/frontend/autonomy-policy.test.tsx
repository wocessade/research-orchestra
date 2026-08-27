import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { envelope, renderAppAt, standardRoutes } from "./helpers";

const FUTURE_RUNS_COPY = "只影响之后创建的运行；正在运行和已经创建的任务继续使用其冻结模式。";
const AUTONOMOUS_GUARD_COPY = "科研结论、对外发布、新增支出和超预算实验仍需人工批准。";

function policySnapshot(
  overrides: {
    globalDefault?: string;
    projectOverrides?: Record<string, string>;
    revision?: number;
  } = {},
) {
  return {
    globalDefault: "supervised",
    projectOverrides: {},
    revision: 0,
    ...overrides,
  };
}

function writableRoutes(
  snapshot = policySnapshot(),
  extras: Record<string, ReturnType<typeof envelope> | ((request: { url: URL; init?: RequestInit }) => unknown)> = {},
  capabilities: Record<string, unknown> = {},
) {
  const routes = standardRoutes();
  routes["/api/v1/capabilities"] = envelope({
    profile: "mock-all",
    projectId: "bogda-main",
    effectiveAutonomyMode: "supervised",
    canSubmitRegisteredDeployment: true,
    canCancelRun: true,
    canPauseSchedule: true,
    canPauseWorkQueue: true,
    canReviewScientificResult: true,
    canSetAutonomyMode: true,
    ...capabilities,
  }, {});
  routes["/api/v1/autonomy-policy"] = envelope(snapshot, {});
  return Object.assign(routes, extras);
}

describe("research autonomy controls", () => {
  it("shows global default, project effective mode, source, and revision", async () => {
    renderAppAt("/", writableRoutes(policySnapshot({
      globalDefault: "manual",
      projectOverrides: { "bogda-main": "autonomous" },
      revision: 4,
    })));
    const region = await screen.findByRole("region", { name: "科研自主模式" });
    expect(within(region).getByText("全局默认")).toBeVisible();
    expect(within(region).getByText("当前项目")).toBeVisible();
    expect(within(region).getByText("bogda-main")).toBeVisible();
    expect(within(region).getByText("项目有效模式")).toBeVisible();
    expect(within(region).getByText("来源")).toBeVisible();
    expect(within(region).getByText("项目覆盖")).toBeVisible();
    expect(within(region).getByText("修订号")).toBeVisible();
    expect(within(region).getByText("4")).toBeVisible();
    expect(within(region).getAllByText("范围内自主").length).toBeGreaterThan(0);
  });

  it("uses Chinese labels for the three research modes", async () => {
    renderAppAt("/", writableRoutes());
    const region = await screen.findByRole("region", { name: "科研自主模式" });
    expect(within(region).getByRole("radio", { name: "手动" })).toBeVisible();
    expect(within(region).getByRole("radio", { name: "监督执行" })).toBeVisible();
    expect(within(region).getByRole("radio", { name: "范围内自主" })).toBeVisible();
    expect(within(region).getByRole("radio", { name: "继承全局" })).toBeVisible();
    expect(within(region).getByRole("radio", { name: "本项目覆盖" })).toBeVisible();
    expect(within(region).getByText("全局默认模式")).toBeVisible();
    expect(within(region).getByText("项目策略")).toBeVisible();
    expect(within(region).queryByRole("radiogroup", { name: "当前项目模式" })).not.toBeInTheDocument();
  });

  it("reveals the project mode band only after unlatching inheritance", async () => {
    const user = userEvent.setup();
    renderAppAt("/", writableRoutes());
    const region = await screen.findByRole("region", { name: "科研自主模式" });
    expect(within(region).queryByRole("radio", { name: "项目范围内自主" })).not.toBeInTheDocument();
    await user.click(within(region).getByRole("radio", { name: "本项目覆盖" }));
    expect(within(region).getByRole("radiogroup", { name: "当前项目模式" })).toBeVisible();
    await user.click(within(region).getByRole("radio", { name: "项目范围内自主" }));
    expect(screen.getByText(AUTONOMOUS_GUARD_COPY)).toBeVisible();
  });

  it("asks for confirmation before changing the global mode", async () => {
    const user = userEvent.setup();
    let posted = false;
    const routes = writableRoutes(policySnapshot(), {
      "/api/v1/autonomy-policy/global": () => {
        posted = true;
        return envelope({
          command: "setGlobalAutonomy",
          resourceId: "global",
          acceptedAt: "2026-08-24T08:30:00Z",
          snapshot: policySnapshot({ globalDefault: "manual", revision: 1 }),
        }, {});
      },
    });
    renderAppAt("/", routes);
    await user.click(await screen.findByRole("radio", { name: "手动" }));
    expect(posted).toBe(false);
    expect(screen.getByRole("dialog", { name: "确认切换科研自主模式" })).toBeVisible();
    expect(screen.getByText(FUTURE_RUNS_COPY)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "确认切换" }));
    expect(posted).toBe(true);
  });

  it("states that only future runs are affected", async () => {
    const user = userEvent.setup();
    renderAppAt("/", writableRoutes());
    await user.click(await screen.findByRole("radio", { name: "手动" }));
    expect(screen.getByText(FUTURE_RUNS_COPY)).toBeVisible();
  });

  it("keeps the human-approval warning when confirming autonomous mode", async () => {
    const user = userEvent.setup();
    renderAppAt("/", writableRoutes());
    await user.click(await screen.findByRole("radio", { name: "范围内自主" }));
    expect(screen.getByText(FUTURE_RUNS_COPY)).toBeVisible();
    expect(screen.getByText(AUTONOMOUS_GUARD_COPY)).toBeVisible();
  });

  it("restores project inheritance of the global default", async () => {
    const user = userEvent.setup();
    let body: Record<string, unknown> | null = null;
    const routes = writableRoutes(policySnapshot({
      globalDefault: "supervised",
      projectOverrides: { "bogda-main": "manual" },
      revision: 2,
    }), {
      "/api/v1/autonomy-policy/projects/bogda-main": ({ init }) => {
        body = JSON.parse(String(init?.body));
        return envelope({
          command: "setProjectAutonomy",
          resourceId: "bogda-main",
          acceptedAt: "2026-08-24T08:30:00Z",
          snapshot: policySnapshot({ globalDefault: "supervised", revision: 3 }),
        }, {});
      },
    });
    renderAppAt("/", routes);
    const region = await screen.findByRole("region", { name: "科研自主模式" });
    expect(within(region).getByText("项目覆盖")).toBeVisible();
    await user.click(within(region).getByRole("radio", { name: "继承全局" }));
    await user.click(screen.getByRole("button", { name: "确认切换" }));
    expect(body).toEqual({ mode: null, expectedRevision: 2 });
    expect(await within(region).findByText("3")).toBeVisible();
    expect(within(region).queryByText("项目覆盖")).not.toBeInTheDocument();
    expect(within(region).getAllByText("全局默认").length).toBeGreaterThan(1);
  });

  it("shows a conflict notice and refreshes from currentResource on 409", async () => {
    const user = userEvent.setup();
    const routes = writableRoutes(policySnapshot(), {
      "/api/v1/autonomy-policy/global": () => new Response(JSON.stringify(envelope(null, {}, [{
        code: "RESOURCE_CHANGED",
        message: "resource changed after the action was opened",
        source: "autonomyPolicy",
        retryable: false,
        details: {
          currentResource: policySnapshot({ globalDefault: "autonomous", revision: 7 }),
        },
      }])), { status: 409, headers: { "Content-Type": "application/json" } }),
    });
    renderAppAt("/", routes);
    await user.click(await screen.findByRole("radio", { name: "手动" }));
    await user.click(screen.getByRole("button", { name: "确认切换" }));
    expect(await screen.findByText("策略已被其他操作修改")).toBeVisible();
    const region = screen.getByRole("region", { name: "科研自主模式" });
    expect(within(region).getByText("7")).toBeVisible();
    expect(within(region).getAllByText("范围内自主").length).toBeGreaterThan(0);
  });

  it("disables controls on a readonly profile and names the profile", async () => {
    const routes = writableRoutes(policySnapshot(), {}, {
      profile: "real-readonly",
      canSetAutonomyMode: false,
      canSubmitRegisteredDeployment: false,
      canCancelRun: false,
      canPauseSchedule: false,
      canPauseWorkQueue: false,
      canReviewScientificResult: false,
    });
    renderAppAt("/", routes);
    const region = await screen.findByRole("region", { name: "科研自主模式" });
    expect(within(region).getByText("当前 profile 为 real-readonly，只读，不能修改科研自主模式。")).toBeVisible();
    expect(within(region).getByRole("radio", { name: "手动" })).toBeDisabled();
    expect(within(region).getByRole("radio", { name: "监督执行" })).toBeDisabled();
    expect(within(region).getByRole("radio", { name: "范围内自主" })).toBeDisabled();
    expect(within(region).getByRole("radio", { name: "继承全局" })).toBeDisabled();
    expect(within(region).getByRole("radio", { name: "本项目覆盖" })).toBeDisabled();
  });

  it("keeps the readonly panel visible when the real policy backend is unavailable", async () => {
    const routes = writableRoutes(policySnapshot(), {}, {
      profile: "real-readonly",
      effectiveAutonomyMode: null,
      canSetAutonomyMode: false,
      canSubmitRegisteredDeployment: false,
      canCancelRun: false,
      canPauseSchedule: false,
      canPauseWorkQueue: false,
      canReviewScientificResult: false,
    });
    delete routes["/api/v1/autonomy-policy"];

    renderAppAt("/", routes);

    const region = await screen.findByRole("region", { name: "科研自主模式" });
    expect(within(region).getByText("当前 profile 为 real-readonly，只读，不能修改科研自主模式。")).toBeVisible();
    expect(within(region).getByText("策略后端尚未接入")).toBeVisible();
    expect(within(region).getByRole("radio", { name: "手动" })).toBeDisabled();
  });

  it("does not offer mode-change controls on the run detail page", async () => {
    renderAppAt("/runs/run-completed-unreviewed", writableRoutes());
    await screen.findByRole("heading", { name: "alpine assay / snowline" });
    expect(screen.queryByRole("region", { name: "科研自主模式" })).not.toBeInTheDocument();
    expect(screen.queryByRole("radio", { name: "手动" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "确认切换" })).not.toBeInTheDocument();
  });

  it("wraps the three-mode control at 360px instead of overflowing horizontally", async () => {
    renderAppAt("/", writableRoutes());
    const region = await screen.findByRole("region", { name: "科研自主模式" });
    const group = within(region).getByRole("radiogroup", { name: "全局默认模式" });
    expect(group.className).toMatch(/wrap/);
  });
});
