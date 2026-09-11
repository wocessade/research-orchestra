import { screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { AppShell } from "../../frontend/src/components/AppShell";
import { renderWithClient } from "./helpers";


describe("AppShell", () => {
  it("renders all primary destinations and a skip link", () => {
    renderWithClient(
      <MemoryRouter>
        <AppShell><p>content</p></AppShell>
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: "跳到主要内容" })).toHaveAttribute("href", "#main-content");
    for (const name of ["总览", "运行", "评审", "基础设施", "决策", "模型策略"]) {
      expect(screen.getAllByRole("link", { name })[0]).toBeVisible();
    }
    expect(screen.getByRole("main")).toHaveAttribute("id", "main-content");
  });

  it("labels the mountain contours as decorative", () => {
    renderWithClient(<MemoryRouter><AppShell><p>content</p></AppShell></MemoryRouter>);
    expect(screen.getByTestId("bogda-contours")).toHaveAttribute("aria-hidden", "true");
  });

  it("does not claim the console is a shadow of the retired 3100", () => {
    renderWithClient(<MemoryRouter><AppShell><p>content</p></AppShell></MemoryRouter>);
    expect(screen.queryByText(/影子/)).toBeNull();
    expect(screen.queryByText(/3100/)).toBeNull();
  });
});
