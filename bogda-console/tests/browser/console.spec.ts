import { expect, test } from "@playwright/test";

import {
  assertNoHorizontalOverflow,
  collectUnexpectedBrowserErrors,
  gotoSettled,
  setScenario,
} from "./support";

test.beforeEach(async ({ request }) => {
  await setScenario(request, "normal-active");
});

test("four-page workflow keeps execution and science separate", async ({ page }, testInfo) => {
  const assertNoErrors = collectUnexpectedBrowserErrors(page);
  await gotoSettled(page, "/");
  await expect(page.getByRole("heading", { name: "今天需要你判断的研究" })).toBeVisible();
  await expect(page.getByText("Prefect 决定执行事实", { exact: false })).toBeVisible();
  if (testInfo.project.name === "desktop-1440") {
    await page.screenshot({ path: "docs/acceptance/overview-desktop.png", fullPage: true });
  }

  await page.getByRole("link", { name: "运行", exact: true }).filter({ visible: true }).click();
  await expect(page.getByRole("heading", { name: "运行账簿" })).toBeVisible();
  await page.getByRole("link", { name: "alpine assay", exact: true }).first().click();
  await expect(page.getByText("Prefect 执行状态")).toBeVisible();
  await expect(page.getByText("科研判断状态")).toBeVisible();
  await expect(page.locator(".status-mark.execution").filter({ hasText: "Completed" })).toBeVisible();
  await expect(page.getByText("待评审", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("这不代表科研结论已被接受", { exact: false })).toBeVisible();
  if (testInfo.project.name === "desktop-1440") {
    await page.screenshot({ path: "docs/acceptance/run-detail-desktop.png", fullPage: true });
  }
  await assertNoHorizontalOverflow(page);
  assertNoErrors();
});

test("allowlisted Deployment submit and exact Prefect controls wait for receipts", async ({ page }) => {
  const assertNoErrors = collectUnexpectedBrowserErrors(page);
  await gotoSettled(page, "/infrastructure");

  await page.getByRole("button", { name: "提交 alpine-assay" }).click();
  await expect(page.getByRole("dialog", { name: "准备 alpine-assay" })).toBeVisible();
  await page.getByRole("textbox", { name: "sample" }).fill("ridge-browser");
  await page.getByRole("button", { name: "生成服务端预览" }).click();
  await expect(page.getByRole("heading", { name: "服务端预览" })).toBeVisible();
  await page.getByRole("button", { name: "确认并提交运行" }).click();
  await expect(page.getByRole("status")).toContainText("已提交");

  await page.getByRole("button", { name: "暂停队列 cpu" }).click();
  await page.getByRole("button", { name: "确认暂停" }).click();
  await expect(page.getByRole("status")).toContainText("队列 cpu 已暂停");
  await page.getByRole("button", { name: "恢复队列 cpu" }).click();
  await page.getByRole("button", { name: "确认恢复" }).click();
  await expect(page.getByRole("status")).toContainText("队列 cpu 已恢复");

  await page.getByRole("button", { name: "暂停日程 manual window" }).click();
  await page.getByRole("button", { name: "确认暂停" }).click();
  await expect(page.getByRole("status")).toContainText("日程 manual window 已暂停");
  await page.getByRole("button", { name: "恢复日程 manual window" }).click();
  await page.getByRole("button", { name: "确认恢复" }).click();
  await expect(page.getByRole("status")).toContainText("日程 manual window 已恢复");
  assertNoErrors();
});

test("cancel and append-only scientific review update only after authority replies", async ({ page }, testInfo) => {
  const assertNoErrors = collectUnexpectedBrowserErrors(page);
  await gotoSettled(page, "/runs/run-active");
  await page.getByRole("button", { name: "取消运行" }).click();
  await page.getByRole("button", { name: "确认取消" }).click();
  await expect(page.locator(".status-mark.execution").filter({ hasText: "Cancelling" })).toBeVisible();

  await gotoSettled(page, "/runs/run-completed");
  await page.getByLabel("科研判断").selectOption("accepted");
  await page.getByLabel("评审说明").fill("浏览器验收：只检查声明产物");
  if (testInfo.project.name === "phone-390") {
    await page.locator(".review-control").scrollIntoViewIfNeeded();
    await page.screenshot({ path: "docs/acceptance/scientific-review-phone.png" });
  }
  await page.getByRole("button", { name: "提交评审" }).click();
  await expect(page.locator(".status-mark.science--accepted")).toContainText("已接受");
  await expect(page.getByText("artifact-run-completed-2", { exact: true }).first()).toBeVisible();
  assertNoErrors();
});

test("review conflict preserves the operator form", async ({ page }) => {
  const expected = new Set(["POST /api/v1/runs/run-completed/reviews 409"]);
  const assertNoErrors = collectUnexpectedBrowserErrors(page, expected);
  let reviewCalls = 0;
  await page.route("**/api/v1/runs/run-completed/reviews", async (route) => {
    reviewCalls += 1;
    const body = route.request().postDataJSON();
    if (reviewCalls > 1) {
      expect(body.baseArtifactId).toBe("artifact-concurrent");
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 409,
      contentType: "application/json",
      body: JSON.stringify({
        data: null,
        sources: {},
        errors: [{
          code: "REVIEW_CONFLICT",
          message: "RunResult changed after the review form opened",
          source: "runResult",
          retryable: false,
          details: {
            currentResource: {
              availability: "available",
              artifactId: "artifact-concurrent",
              artifactCreatedAt: "2026-08-24T08:31:00Z",
              result: null,
              validationIssues: [],
            },
          },
        }],
      }),
    });
  });
  await gotoSettled(page, "/runs/run-completed");
  await page.getByLabel("评审说明").fill("这段文字必须保留");
  await page.getByRole("button", { name: "提交评审" }).click();
  await expect(page.getByRole("alert")).toContainText("结果已被其他评审更新");
  await expect(page.getByLabel("评审说明")).toHaveValue("这段文字必须保留");
  await expect(page.getByText("artifact-concurrent", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "确认采用最新版本" }).click();
  await expect(page.getByRole("status")).toContainText("artifact-concurrent");
  await expect(page.getByLabel("评审说明")).toHaveValue("这段文字必须保留");
  await page.getByRole("button", { name: "提交评审" }).click();
  await expect.poll(() => reviewCalls).toBe(2);
  assertNoErrors();
});

test("research autonomy controls wrap at 360px", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "phone-360", "360px wrap check");
  const assertNoErrors = collectUnexpectedBrowserErrors(page);
  await gotoSettled(page, "/");
  await expect(page.getByRole("region", { name: "科研自主模式" })).toBeVisible();
  await assertNoHorizontalOverflow(page);
  assertNoErrors();
});

test("decision center keeps keyboard conflict handling and canonical hash targets", async ({ page }) => {
  const expected = new Set(["POST /api/v1/decisions/decision-1 409"]);
  const assertNoErrors = collectUnexpectedBrowserErrors(page, expected);
  await gotoSettled(page, "/decisions#decision-1");
  const item = page.locator("#decision-1");
  await expect(item).toBeVisible();
  await expect.poll(() => item.evaluate((node) => document.activeElement === node)).toBe(true);

  await page.getByRole("button", { name: "查看：Peak run" }).click();
  const dialog = page.getByRole("dialog", { name: "Peak run" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("combobox", { name: "选择操作" })).toBeVisible();
  await dialog.getByRole("combobox", { name: "选择操作" }).selectOption("approve");
  await dialog.getByLabel("操作理由").fill("浏览器验收：批准高峰覆盖");
  await dialog.getByLabel("确认不可逆后果").check();

  let posts = 0;
  const snapshot = await (await page.request.get("/api/v1/decisions")).json();
  await page.route("**/api/v1/decisions/decision-1", async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    posts += 1;
    if (posts === 1) {
      await route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({
          data: null,
          sources: {},
          errors: [{
            code: "RESOURCE_CHANGED",
            message: "decision revision moved",
            source: "modelControl",
            retryable: false,
            details: { currentResource: snapshot.data },
          }],
        }),
      });
      return;
    }
    await route.continue();
  });

  await dialog.getByRole("button", { name: "Approve" }).click();
  await expect(dialog.getByRole("alert")).toContainText("决策已被其他操作修改");
  await dialog.getByLabel("我已重新检查当前修订和操作").check();
  await dialog.getByLabel("确认不可逆后果").check();
  await dialog.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByRole("dialog", { name: "Peak run" })).toHaveCount(0);
  assertNoErrors();
});

test("run budget copy stays state-specific and usage-unknown forbids blind retry", async ({ page }) => {
  const assertNoErrors = collectUnexpectedBrowserErrors(page);
  await gotoSettled(page, "/runs/run-completed");
  await expect(page.getByRole("region", { name: "运行预算" })).toContainText("预算可用");
  await expect(page.getByRole("region", { name: "运行预算" })).toContainText("4.00 CNY");

  await gotoSettled(page, "/runs/run-active");
  const budget = page.getByRole("region", { name: "运行预算" });
  await expect(budget).toContainText("用量未知");
  await expect(budget).toContainText("必须人工核对用量后才能恢复");
  await expect(budget).toContainText("同一调用不得盲目重试");
  await expect(budget.getByRole("link", { name: /decision-usage-unknown/ })).toHaveAttribute("href", "/decisions#decision-usage-unknown");
  assertNoErrors();
});

test("model policy keeps immutable facts and restores inheritance after conflict reconfirm", async ({ page }) => {
  const expected = new Set(["POST /api/v1/model-policy/projects/bogda-main 409"]);
  const assertNoErrors = collectUnexpectedBrowserErrors(page, expected);
  await gotoSettled(page, "/model-policy");
  await assertNoHorizontalOverflow(page);
  const region = page.getByRole("region", { name: "模型策略" });
  await expect(region.getByText("仅观察，不可关闭")).toBeVisible();
  await expect(region.getByText("修订号")).toBeVisible();

  const remaining = region.getByLabel("最低剩余预算");
  await remaining.fill("12.00");
  const save = region.getByRole("button", { name: "保存项目默认" });
  await save.scrollIntoViewIfNeeded();
  await save.click({ force: true });
  await page.getByRole("button", { name: "确认保存" }).click();
  await expect(region.getByText("本项目覆盖全局默认")).toBeVisible();

  let posts = 0;
  const current = await (await page.request.get("/api/v1/model-policy?projectId=bogda-main")).json();
  await page.route("**/api/v1/model-policy/projects/bogda-main", async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    posts += 1;
    if (posts === 1) {
      await route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({
          data: null,
          sources: {},
          errors: [{
            code: "RESOURCE_CHANGED",
            message: "policy revision moved",
            source: "modelControl",
            retryable: false,
            details: { currentResource: { ...current.data, revision: current.data.revision + 1 } },
          }],
        }),
      });
      return;
    }
    await route.continue();
  });

  await region.getByRole("button", { name: "恢复继承全局" }).click();
  await page.getByRole("button", { name: "确认恢复继承" }).click();
  await expect(page.getByRole("status")).toContainText("审阅最新值后重新确认");
  await region.getByRole("button", { name: "恢复继承全局" }).click();
  await page.getByRole("button", { name: "确认恢复继承" }).click();
  await expect(region.getByText("继承全局")).toBeVisible();
  assertNoErrors();
});

test("real-readonly capabilities keep policy and paid preparation closed", async ({ page }) => {
  await page.route("**/api/v1/capabilities", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.data = {
      ...body.data,
      profile: "real-readonly",
      canPreparePaidRun: false,
      canSetModelPolicy: false,
      canResolveModelDecision: false,
      canSubmitRegisteredDeployment: false,
    };
    await route.fulfill({ response, json: body });
  });
  const assertNoErrors = collectUnexpectedBrowserErrors(page);
  await gotoSettled(page, "/model-policy");
  await expect(page.getByRole("button", { name: "保存项目默认" })).toBeDisabled();
  await gotoSettled(page, "/infrastructure");
  await expect(page.getByRole("button", { name: "提交 alpine-assay" })).toBeDisabled();
  assertNoErrors();
});
