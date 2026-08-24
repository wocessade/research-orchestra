import { expect, type APIRequestContext, type Page } from "@playwright/test";

export type Scenario =
  | "normal-active"
  | "sleep-queued"
  | "gaming-paused"
  | "degraded-stale"
  | "result-missing-invalid-conflict"
  | "mobile-dense";

export async function setScenario(request: APIRequestContext, scenario: Scenario) {
  const response = await request.post("/api/v1/test/scenario", { data: { scenario } });
  expect(response.ok()).toBeTruthy();
}

export function collectUnexpectedBrowserErrors(
  page: Page,
  expectedResponses: ReadonlySet<string> = new Set(),
) {
  const unexpected: string[] = [];
  page.on("pageerror", (error) => unexpected.push(`pageerror:${error.message}`));
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const duplicateExpectedHttpError = expectedResponses.size > 0
      && message.text().startsWith("Failed to load resource: the server responded with a status of");
    if (!duplicateExpectedHttpError) unexpected.push(`console:${message.text()}`);
  });
  page.on("response", (response) => {
    if (response.status() < 400) return;
    const key = `${response.request().method()} ${new URL(response.url()).pathname} ${response.status()}`;
    if (!expectedResponses.has(key)) unexpected.push(`http:${key}`);
  });
  return () => expect(unexpected, "unexpected browser errors").toEqual([]);
}

export async function gotoSettled(page: Page, path: string) {
  await page.goto(path);
  await page.waitForLoadState("networkidle");
}

export async function assertNoHorizontalOverflow(page: Page) {
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth))
    .toBe(true);
}
