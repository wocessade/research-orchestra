import { expect, test } from "@playwright/test";

import {
  collectUnexpectedBrowserErrors,
  gotoSettled,
  setScenario,
  type Scenario,
} from "./support";

test("Prefect unavailable without last-good renders an explicit failure", async ({ page, request }, testInfo) => {
  await setScenario(request, "degraded-stale");
  const expected = new Set(["GET /api/v1/infrastructure 503", "GET /api/v1/deployments 503"]);
  const assertNoErrors = collectUnexpectedBrowserErrors(page, expected);
  await gotoSettled(page, "/infrastructure");
  await expect(page.getByRole("alert")).toContainText("基础设施来源暂不可用");
  if (testInfo.project.name === "phone-390") {
    await page.screenshot({
      path: "docs/acceptance/infrastructure-degraded-phone.png",
      fullPage: true,
    });
  }
  assertNoErrors();
});

test("last-good projections remain visibly stale instead of becoming empty", async ({ page, request }) => {
  await setScenario(request, "normal-active");
  const response = await request.get("/api/v1/runs");
  const envelope = await response.json();
  envelope.sources.prefect.freshness = "stale";
  envelope.sources.prefect.observedAt = "2026-08-24T08:20:00Z";
  envelope.errors.push({
    code: "PREFECT_UNAVAILABLE",
    message: "mock Prefect unavailable",
    source: "prefect",
    retryable: true,
  });
  await page.route("**/api/v1/runs", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(envelope) });
  });
  const assertNoErrors = collectUnexpectedBrowserErrors(page);
  await gotoSettled(page, "/runs");
  await expect(page.getByText("Prefect · 陈旧数据", { exact: true })).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: "Prefect 暂不可用" })).toBeVisible();
  await expect(page.getByRole("link", { name: "alpine assay", exact: true }).first()).toBeVisible();
  assertNoErrors();
});

test("offline Worker and every mock Power mode stay source-separated", async ({ page, request }) => {
  const assertNoErrors = collectUnexpectedBrowserErrors(page);
  const modes: Array<[Scenario, string]> = [
    ["sleep-queued", "sleep"],
    ["normal-active", "compute"],
    ["gaming-paused", "gaming"],
    ["result-missing-invalid-conflict", "maintenance"],
  ];
  for (const [scenario, mode] of modes) {
    await setScenario(request, scenario);
    await gotoSettled(page, "/infrastructure");
    await expect(page.locator(".power-facts").getByText(mode, { exact: true })).toBeVisible();
    await expect(page.getByLabel("宿舍机电源状态").getByText("模拟数据", { exact: true })).toBeVisible();
    await expect(page.getByText("共享并发", { exact: false })).toBeVisible();
    if (scenario === "sleep-queued") {
      await expect(page.getByText("OFFLINE", { exact: true })).toBeVisible();
    }
  }
  assertNoErrors();
});

test("missing and newest-invalid RunResult are explicit", async ({ page, request }) => {
  await setScenario(request, "result-missing-invalid-conflict");
  const assertNoErrors = collectUnexpectedBrowserErrors(page);
  await gotoSettled(page, "/runs/run-missing");
  await expect(page.getByRole("heading", { name: "RunResult 缺失" })).toBeVisible();
  await expect(page.getByText("科研状态不可用", { exact: false })).toBeVisible();

  await gotoSettled(page, "/runs/run-invalid");
  await expect(page.getByRole("heading", { name: "最新 RunResult 无效" })).toBeVisible();
  await expect(page.getByText("较早版本不会覆盖最新版本的权威性")).toBeVisible();
  await expect(page.getByText("artifact-invalid-newest", { exact: true }).first()).toBeVisible();
  assertNoErrors();
});

test("stale Power stays labeled mock and does not infer Worker state", async ({ page, request }) => {
  await setScenario(request, "normal-active");
  const response = await request.get("/api/v1/infrastructure");
  const envelope = await response.json();
  envelope.sources.power.freshness = "stale";
  envelope.sources.power.observedAt = "2026-08-24T08:10:00Z";
  envelope.errors.push({
    code: "POWER_UNAVAILABLE",
    message: "mock Power source unavailable",
    source: "power",
    retryable: true,
  });
  await page.route("**/api/v1/infrastructure", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(envelope) });
  });
  const assertNoErrors = collectUnexpectedBrowserErrors(page);
  await gotoSettled(page, "/infrastructure");
  await expect(page.getByText("Power Agent · 陈旧数据", { exact: true })).toBeVisible();
  await expect(page.getByLabel("宿舍机电源状态").getByText("模拟数据", { exact: true })).toBeVisible();
  await expect(page.getByText("ONLINE", { exact: true }).first()).toBeVisible();
  assertNoErrors();
});
