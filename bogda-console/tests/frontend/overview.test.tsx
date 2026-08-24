import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderAppAt } from "./helpers";

describe("OverviewPage", () => {
  it("orders attention before active work and recent outcomes", async () => {
    renderAppAt("/");
    const attention = await screen.findByRole("heading", { name: "需要判断" });
    const active = screen.getByRole("heading", { name: "正在执行" });
    const recent = screen.getByRole("heading", { name: "最近结果" });
    expect(attention.compareDocumentPosition(active) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(active.compareDocumentPosition(recent) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByText("Prefect 决定执行事实，RunResult 承载科研判断。两者不会合并成一个‘成功’。" )).toBeVisible();
  });
});
