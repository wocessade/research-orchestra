import { expect, test } from "@playwright/test";

import { collectUnexpectedBrowserErrors, gotoSettled, setScenario } from "./support";

test("the shadow application and every same-origin resource stay on 3101", async ({ page, request }) => {
  await setScenario(request, "normal-active");
  const requestedPorts = new Set<string>();
  page.on("request", (requestEvent) => {
    const url = new URL(requestEvent.url());
    if (url.hostname === "127.0.0.1") requestedPorts.add(url.port);
  });
  const assertNoErrors = collectUnexpectedBrowserErrors(page);
  await gotoSettled(page, "/");
  await page.getByRole("link", { name: "基础设施", exact: true }).filter({ visible: true }).click();
  await page.waitForLoadState("networkidle");
  expect(new URL(page.url()).port).toBe("3101");
  expect([...requestedPorts]).toEqual(["3101"]);
  await expect(page.getByText("3101 影子运行", { exact: true })).toHaveCount(1);
  assertNoErrors();
});
