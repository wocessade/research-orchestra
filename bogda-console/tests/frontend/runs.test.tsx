import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { completedRun, envelope, renderAppAt, requestLog, sourceStale, standardRoutes, validResult } from "./helpers";

describe("run surfaces", () => {
  it("shows Completed and unreviewed together without claiming science succeeded", async () => {
    renderAppAt("/runs/run-completed-unreviewed");
    expect(await screen.findByText("Completed")).toBeVisible();
    expect(screen.getByText("待评审")).toBeVisible();
    expect(screen.getByText("执行完成，且声明的必要产物存在；这不代表科研结论已被接受。" )).toBeVisible();
    expect(screen.queryByText(/研究成功|结论成立|验证通过/)).not.toBeInTheDocument();
  });

  it("sends exact execution and scientific filters", async () => {
    const user = userEvent.setup();
    renderAppAt("/runs");
    await screen.findByRole("table");
    await user.selectOptions(screen.getByLabelText("执行状态"), "COMPLETED");
    await user.selectOptions(screen.getByLabelText("科研状态"), "unreviewed");
    await waitFor(() => expect(requestLog.at(-1)).toContain("executionType=COMPLETED&scientificStatus=unreviewed"));
  });

  it("renders stale Prefect data with absolute time instead of zero runs", async () => {
    const routes = standardRoutes();
    routes["/api/v1/runs"] = envelope({ items: [{ ...completedRun, runId: "run-stale", name: "stale observation", state: { ...completedRun.state, type: "RUNNING", name: "Retrying", terminal: false } }], nextCursor: null }, { prefect: sourceStale, runResult: { ...sourceStale, source: "runResult" } });
    renderAppAt("/runs", routes);
    expect(await screen.findAllByText(/陈旧数据/)).not.toHaveLength(0);
    expect(screen.getAllByText(/2026/).length).toBeGreaterThan(0);
    expect(screen.queryByText("0 个运行")).not.toBeInTheDocument();
    expect(screen.getAllByText("Retrying").length).toBeGreaterThan(0);
  });

  it("uses a semantic table and labeled compact records for the same runs", async () => {
    renderAppAt("/runs");
    const table = await screen.findByRole("table", { name: "运行账簿" });
    expect(within(table).getByRole("columnheader", { name: "Prefect 状态" })).toBeVisible();
    const record = screen.getByRole("article", { name: "运行 alpine assay / snowline" });
    expect(within(record).getByText("Prefect 状态")).toBeVisible();
    expect(screen.getAllByText("COMPLETED").length).toBeGreaterThan(0);
  });

  it.each([
    ["SCHEDULED", "Late"],
    ["RUNNING", "Retrying"],
    ["PAUSED", "Paused"],
  ])("preserves the raw Prefect name %s / %s", async (type, name) => {
    const routes = standardRoutes();
    routes["/api/v1/runs"] = envelope({ items: [{ ...completedRun, runId: `run-${name}`, state: { ...completedRun.state, type, name, terminal: false } }], nextCursor: null });
    renderAppAt("/runs", routes);
    expect((await screen.findAllByText(name)).length).toBeGreaterThan(0);
  });

  it("keeps a missing RunResult distinct from unreviewed", async () => {
    const routes = standardRoutes();
    const missingRun = { ...completedRun, runId: "run-missing", name: "missing result", scientific: { availability: "missing", artifactId: null, artifactCreatedAt: null, scientificStatus: null, reviewSummary: null, validationIssues: [] } };
    routes["/api/v1/runs/run-missing"] = envelope({ run: missingRun, parameters: {}, tags: [], projectContext: null });
    routes["/api/v1/runs/run-missing/result"] = envelope({ availability: "missing", artifactId: null, artifactCreatedAt: null, result: null, validationIssues: [] }, { runResult: { ...sourceStale, source: "runResult" } });
    routes["/api/v1/runs/run-missing/result/versions"] = envelope({ items: [], nextCursor: null }, { runResult: { ...sourceStale, source: "runResult" } });
    renderAppAt("/runs/run-missing", routes);
    expect(await screen.findByRole("heading", { name: "RunResult 缺失" })).toBeVisible();
    expect(screen.getAllByText("RunResult 缺失").length).toBeGreaterThan(1);
    expect(screen.queryByText("待评审")).not.toBeInTheDocument();
  });

  it("treats the newest invalid RunResult as authoritative", async () => {
    const routes = standardRoutes();
    const invalidRun = { ...completedRun, runId: "run-invalid", name: "invalid result", scientific: { ...completedRun.scientific, availability: "invalid", artifactId: "artifact-invalid-newest", scientificStatus: null, validationIssues: ["scientific_status: invalid value"] } };
    routes["/api/v1/runs/run-invalid"] = envelope({ run: invalidRun, parameters: {}, tags: [], projectContext: null }, { prefect: sourceStale, runResult: { ...sourceStale, source: "runResult" } });
    routes["/api/v1/runs/run-invalid/result"] = envelope({ availability: "invalid", artifactId: "artifact-invalid-newest", artifactCreatedAt: "2026-08-24T09:20:08Z", result: null, validationIssues: ["scientific_status: invalid value"] }, { runResult: { ...sourceStale, source: "runResult" } });
    routes["/api/v1/runs/run-invalid/result/versions"] = envelope({ items: [{ artifactId: "artifact-invalid-newest", createdAt: "2026-08-24T09:20:08Z", availability: "invalid", scientificStatus: null, reviewSummary: null }, { artifactId: "artifact-valid-older", createdAt: "2026-08-24T09:20:05Z", availability: "available", scientificStatus: "unreviewed", reviewSummary: null }], nextCursor: null }, { runResult: { ...sourceStale, source: "runResult" } });
    renderAppAt("/runs/run-invalid", routes);
    expect(await screen.findByText("最新 RunResult 无效")).toBeVisible();
    expect(screen.getAllByText("artifact-invalid-newest").length).toBeGreaterThan(0);
    expect(screen.getByText("较早版本不会覆盖最新版本的权威性。" )).toBeVisible();
  });

  it("shows declared artifacts without scanning beyond the RunResult", async () => {
    const routes = standardRoutes();
    routes["/api/v1/runs/run-completed-unreviewed/result"] = envelope(validResult, { runResult: { ...sourceStale, source: "runResult" } });
    renderAppAt("/runs/run-completed-unreviewed", routes);
    expect(await screen.findByText("file:///attempt/result.json")).toBeVisible();
    expect(screen.getByText("仅显示 RunResult 声明的产物，不扫描其他目录。" )).toBeVisible();
  });
});
