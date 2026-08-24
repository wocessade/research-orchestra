import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { envelope, renderAppAt, sourceFresh, standardRoutes } from "./helpers";

describe("InfrastructurePage", () => {
  it("shows one dorm capacity rather than two queue capacities", async () => {
    renderAppAt("/infrastructure");
    expect(await screen.findByRole("heading", { name: "dorm-x86" })).toBeVisible();
    expect(screen.getByText("共享并发 1 / 1")).toBeVisible();
    expect(screen.getByText("cpu")).toBeVisible();
    expect(screen.getByText("gpu")).toBeVisible();
    expect(screen.queryByText("CPU 1/1")).not.toBeInTheDocument();
    expect(screen.queryByText("GPU 0/1")).not.toBeInTheDocument();
  });

  it("keeps Worker OFFLINE separate from sleep and API unavailable", async () => {
    const routes = standardRoutes();
    routes["/api/v1/infrastructure"] = envelope({ pools: [{ name: "dorm-x86", status: "NOT_READY", isPaused: false, concurrencyLimit: 1, activeSlots: 0, queues: [{ queueId: "queue-cpu", name: "cpu", status: "NOT_READY", isPaused: false, concurrencyLimit: null, commandVersion: "queue-v1" }], workers: [{ workerId: "worker-dorm", name: "dorm-x86", status: "OFFLINE", lastHeartbeatTime: "2026-08-24T22:41:00Z" }] }], dormPower: { host: "dorm-x86", mode: "sleep", agentReachable: true, sleepInhibited: false, lastTransitionAt: "2026-08-24T22:45:00Z" } }, { prefect: sourceFresh, power: { ...sourceFresh, source: "power", sourceMode: "mock" } });
    renderAppAt("/infrastructure", routes);
    expect(await screen.findByText("OFFLINE")).toBeVisible();
    expect(screen.getByText("sleep")).toBeVisible();
    expect(screen.getAllByText("模拟数据").length).toBeGreaterThan(0);
    expect(screen.queryByText(/OFFLINE.*sleep/)).not.toBeInTheDocument();
  });

  it("reports a broken dorm capacity contract directly", async () => {
    const routes = standardRoutes();
    routes["/api/v1/infrastructure"] = envelope({ pools: [{ name: "dorm-x86", status: "READY", isPaused: false, concurrencyLimit: 2, activeSlots: 0, queues: [], workers: [] }], dormPower: null }, { prefect: sourceFresh, power: { ...sourceFresh, source: "power", freshness: "unavailable" } });
    renderAppAt("/infrastructure", routes);
    expect(await screen.findByText("宿舍机共享并发配置不符合约束")).toBeVisible();
    expect(screen.getByText("期望 1，Prefect 当前报告 2。" )).toBeVisible();
  });

  it("does not turn an unavailable API into empty infrastructure", async () => {
    const routes = standardRoutes();
    routes["/api/v1/infrastructure"] = () => new Response(JSON.stringify(envelope(null, { prefect: { ...sourceFresh, freshness: "unavailable" } }, [{ code: "PREFECT_UNAVAILABLE", message: "connection refused", source: "prefect", retryable: true }])), { status: 503, headers: { "Content-Type": "application/json" } });
    renderAppAt("/infrastructure", routes);
    expect(await screen.findByRole("alert")).toHaveTextContent("基础设施来源暂不可用");
    expect(screen.queryByText("0 个工作池")).not.toBeInTheDocument();
  });
});
