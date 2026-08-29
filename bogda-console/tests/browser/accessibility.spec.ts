import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import {
  assertNoHorizontalOverflow,
  collectUnexpectedBrowserErrors,
  gotoSettled,
  setScenario,
} from "./support";

test.beforeEach(async ({ page, request }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await setScenario(request, "normal-active");
});

test("all product surfaces have no serious axe violations", async ({ page }) => {
  const assertNoErrors = collectUnexpectedBrowserErrors(page);
  for (const path of ["/", "/runs", "/reviews", "/runs/run-completed", "/infrastructure", "/decisions", "/model-policy"]) {
    await gotoSettled(page, path);
    const results = await new AxeBuilder({ page }).analyze();
    const blocking = results.violations.filter((violation) =>
      violation.impact === "serious" || violation.impact === "critical"
    );
    expect(blocking, `axe violations at ${path}`).toEqual([]);
  }
  assertNoErrors();
});

test("viewport and 200 percent equivalent reflow do not overflow", async ({ page }) => {
  const assertNoErrors = collectUnexpectedBrowserErrors(page);
  await setScenario(page.request, "mobile-dense");
  await gotoSettled(page, "/runs");
  await assertNoHorizontalOverflow(page);

  const viewport = page.viewportSize();
  expect(viewport).not.toBeNull();
  if (viewport) {
    await page.setViewportSize({
      width: Math.max(320, Math.floor(viewport.width / 2)),
      height: viewport.height,
    });
  }
  await assertNoHorizontalOverflow(page);
  assertNoErrors();
});

test("skip link and dialog keyboard behavior keep focus deterministic", async ({ page }) => {
  const assertNoErrors = collectUnexpectedBrowserErrors(page);
  await gotoSettled(page, "/");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "跳到主要内容" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main-content")).toBeFocused();

  await gotoSettled(page, "/infrastructure");
  const opener = page.getByRole("button", { name: "提交 alpine-assay" });
  await opener.click();
  const dialog = page.getByRole("dialog", { name: "准备 alpine-assay" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("button", { name: "返回" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(dialog.getByRole("button", { name: "生成服务端预览" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(dialog.getByRole("textbox", { name: "sample" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(opener).toBeFocused();
  assertNoErrors();
});

test("degraded state is accessible", async ({ page, request }) => {
  await setScenario(request, "degraded-stale");
  const expected = new Set(["GET /api/v1/runs 503"]);
  const assertNoErrors = collectUnexpectedBrowserErrors(page, expected);
  await gotoSettled(page, "/runs");
  await expect(page.getByRole("alert")).toContainText("Prefect 运行数据暂不可用");
  const results = await new AxeBuilder({ page }).analyze();
  const blocking = results.violations.filter((violation) =>
    violation.impact === "serious" || violation.impact === "critical"
  );
  expect(blocking).toEqual([]);
  assertNoErrors();
});
