import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

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
    expect(screen.getByRole("link", { name: "查看证据" })).toHaveAttribute("href", "/runs/run-review");
  });
});
