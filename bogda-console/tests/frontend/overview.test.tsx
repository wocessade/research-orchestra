import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { envelope, renderAppAt, standardRoutes } from "./helpers";

describe("OverviewPage", () => {
  it("orders attention before active work and recent outcomes", async () => {
    renderAppAt("/");
    const attention = await screen.findByRole("heading", { name: "需要判断" });
    const active = screen.getByRole("heading", { name: "正在执行" });
    const recent = screen.getByRole("heading", { name: "最近结果" });
    expect(attention.compareDocumentPosition(active) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(active.compareDocumentPosition(recent) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByText("Prefect 决定执行事实，科研结论另判。")).toBeVisible();
  });

  it("offers a review entry in the waiting-review block without one-click judgment", async () => {
    renderAppAt("/");
    const heading = await screen.findByRole("heading", { name: "等待评审" });
    const block = heading.closest("section");
    expect(block).not.toBeNull();
    const reviewLinks = within(block!).getAllByRole("link", { name: "查看证据并判断" });
    expect(reviewLinks.length).toBeGreaterThan(0);
    for (const reviewLink of reviewLinks) {
      expect(reviewLink).toHaveAttribute("href", "/runs/run-completed-unreviewed#scientific-review");
    }
    expect(within(block!).queryByRole("button", { name: "提交评审" })).not.toBeInTheDocument();
    expect(within(block!).queryByRole("button", { name: /接受|拒绝/ })).not.toBeInTheDocument();
  });

  it("distinguishes unavailable overview sources from genuinely empty data", async () => {
    renderAppAt("/", {
      ...standardRoutes(),
      "/api/v1/overview": envelope({
        execution: null,
        science: null,
        infrastructure: null,
        power: null,
      }, {}, []),
    });

    expect(await screen.findAllByText("运行来源暂不可用")).toHaveLength(2);
    expect(screen.getAllByText("科研结果来源暂不可用")).toHaveLength(2);
    expect(screen.getByText("基础设施来源暂不可用")).toBeVisible();
    expect(screen.queryByText("当前没有活动运行")).not.toBeInTheDocument();
    expect(screen.queryByText("当前没有需要人工判断的结果")).not.toBeInTheDocument();
    expect(screen.queryByText(/宿舍机未接入/)).not.toBeInTheDocument();
  });

  it("keeps an available power snapshot visible when pool capacity is unavailable", async () => {
    renderAppAt("/", {
      ...standardRoutes(),
      "/api/v1/overview": envelope({
        execution: { countsByPrefectType: {}, recentRuns: [] },
        science: { countsByScientificStatus: {}, attentionRuns: [] },
        infrastructure: null,
        power: { host: "dorm-x86", mode: "compute", agentReachable: true, sleepInhibited: true, lastTransitionAt: "2026-08-24T08:19:30Z" },
      }),
    });

    expect(await screen.findByText("Prefect pool 暂不可读取")).toBeVisible();
    expect(screen.getByText("compute")).toBeVisible();
    expect(screen.getByText("Agent 可达")).toBeVisible();
  });
});

