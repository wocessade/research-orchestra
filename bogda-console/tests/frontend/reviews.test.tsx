import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { completedRun, envelope, renderAppAt, requestLog, standardRoutes } from "./helpers";

describe("ReviewsPage", () => {
  it("loads only authoritative unreviewed results", async () => {
    renderAppAt("/reviews");
    expect(await screen.findByRole("heading", { name: "科研结果评审" })).toBeVisible();
    expect(await screen.findByText("待评审")).toBeVisible();
    expect(requestLog).toContain("/api/v1/runs?scientificStatus=unreviewed");
  });

  it("keeps a terminal execution warning beside reviewable evidence", async () => {
    const routes = standardRoutes();
    const crashed = { ...completedRun, runId: "run-review", name: "partial evidence", state: { ...completedRun.state, type: "CRASHED", name: "Crashed" } };
    routes["/api/v1/runs"] = envelope({ items: [crashed], nextCursor: null });
    renderAppAt("/reviews", routes);
    expect(await screen.findByText("Crashed")).toBeVisible();
    expect(screen.getByText("执行未正常完成，但存在可评审的 RunResult。" )).toBeVisible();
    expect(screen.getByRole("link", { name: "查看证据并判断" })).toHaveAttribute("href", "/runs/run-review#scientific-review");
    expect(screen.queryByRole("button", { name: "提交评审" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /接受|拒绝/ })).not.toBeInTheDocument();
  });
});

describe("scientific review entry", () => {
  it("exposes a hash target with judgment, notes, and submit controls", async () => {
    renderAppAt("/runs/run-completed-unreviewed#scientific-review");
    const region = await screen.findByRole("region", { name: "追加科研评审" });
    expect(region).toHaveAttribute("id", "scientific-review");
    expect(within(region).getByLabelText("科研判断")).toBeVisible();
    expect(within(region).getByRole("option", { name: "accepted / 接受" })).toBeInTheDocument();
    expect(within(region).getByRole("option", { name: "rejected / 拒绝" })).toBeInTheDocument();
    expect(within(region).getByRole("option", { name: "inconclusive / 无定论" })).toBeInTheDocument();
    expect(within(region).getByLabelText("评审说明")).toBeVisible();
    expect(within(region).getByRole("button", { name: "提交评审" })).toBeEnabled();
  });

  it("scrolls the scientific review region into view from the hash", async () => {
    const scrollIntoView = vi.fn();
    HTMLElement.prototype.scrollIntoView = scrollIntoView;
    renderAppAt("/runs/run-completed-unreviewed#scientific-review");
    await screen.findByRole("region", { name: "追加科研评审" });
    await waitFor(() => expect(scrollIntoView).toHaveBeenCalled());
  });

  it("explains why the current profile cannot submit a review", async () => {
    const routes = standardRoutes();
    routes["/api/v1/capabilities"] = envelope({
      profile: "real-readonly",
      projectId: "bogda-main",
      effectiveAutonomyMode: "supervised",
      canSubmitRegisteredDeployment: false,
      canCancelRun: false,
      canPauseSchedule: false,
      canPauseWorkQueue: false,
      canReviewScientificResult: false,
      canSetAutonomyMode: false,
    }, {});
    renderAppAt("/runs/run-completed-unreviewed", routes);
    expect(await screen.findByText("当前 profile 为 real-readonly，只读，不能提交科研评审。")).toBeVisible();
    expect(screen.getByRole("button", { name: "提交评审" })).toBeDisabled();
    expect(screen.getByLabelText("科研判断")).toBeDisabled();
    expect(screen.getByLabelText("评审说明")).toBeDisabled();
  });
});
