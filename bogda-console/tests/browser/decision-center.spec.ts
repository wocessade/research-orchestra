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

test("unknown usage recovery stays backend-driven, keyboard-safe, and narrow-screen usable", async ({ page }) => {
  const assertNoErrors = collectUnexpectedBrowserErrors(page);
  await gotoSettled(page, "/decisions");
  await assertNoHorizontalOverflow(page);

  const opener = page.getByRole("button", { name: "查看：Usage unknown" });
  await opener.click();
  let dialog = page.getByRole("dialog", { name: "Usage unknown" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("button", { name: "返回" })).toBeFocused();

  await dialog.getByRole("combobox", { name: "选择操作" }).selectOption("reconcile");
  const cost = dialog.getByRole("spinbutton", { name: "实际费用（CNY）" });
  await expect(cost).toBeVisible();
  await expect(dialog.getByRole("textbox", { name: "新的调用 ID" })).toHaveCount(0);
  await expect(dialog.getByRole("button", { name: "Reconcile" })).toBeDisabled();
  await cost.fill("0.75");
  await expect(dialog.getByRole("button", { name: "Reconcile" })).toBeDisabled();
  await dialog.getByRole("checkbox", { name: "确认不可逆后果" }).check();
  await expect(dialog.getByRole("button", { name: "Reconcile" })).toBeEnabled();
  await assertNoHorizontalOverflow(page);
  await dialog.getByRole("button", { name: "Reconcile" }).click();
  await expect(dialog).toBeHidden();

  await page.getByRole("button", { name: "查看：Usage unknown" }).click();
  dialog = page.getByRole("dialog", { name: "Usage unknown" });
  await dialog.getByRole("combobox", { name: "选择操作" }).selectOption("approve-retry");
  const newCallId = dialog.getByRole("textbox", { name: "新的调用 ID" });
  await expect(newCallId).toBeVisible();
  await expect(dialog.getByRole("spinbutton", { name: "实际费用（CNY）" })).toHaveCount(0);
  await expect(dialog.getByRole("button", { name: "Approve retry" })).toBeDisabled();
  await newCallId.fill("browser-retry-call-2");
  await dialog.getByRole("checkbox", { name: "确认不可逆后果" }).check();
  await expect(dialog.getByRole("button", { name: "Approve retry" })).toBeEnabled();

  await page.keyboard.press("Tab");
  const focusInsideDialog = await page.evaluate(() => {
    const active = document.activeElement;
    return active instanceof HTMLElement && Boolean(active.closest('[role="dialog"]'));
  });
  expect(focusInsideDialog).toBe(true);
  await assertNoHorizontalOverflow(page);
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(page.getByRole("button", { name: "查看：Usage unknown" })).toBeFocused();
  assertNoErrors();
});
