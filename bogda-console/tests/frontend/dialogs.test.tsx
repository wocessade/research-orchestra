import { useState } from "react";
import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ConfirmDialog } from "../../frontend/src/components/Dialogs";
import { renderWithClient } from "./helpers";

function Harness() {
  const [open, setOpen] = useState(false);
  return <><button onClick={() => setOpen(true)}>打开操作</button><ConfirmDialog open={open} title="确认测试" confirmLabel="确认" onClose={() => setOpen(false)} onConfirm={vi.fn()}>不可撤销</ConfirmDialog></>;
}

describe("ConfirmDialog", () => {
  it("focuses the safe action, closes on Escape, and restores opener focus", async () => {
    const user = userEvent.setup();
    renderWithClient(<Harness />);
    const opener = screen.getByRole("button", { name: "打开操作" });
    await user.click(opener);
    expect(screen.getByRole("dialog", { name: "确认测试" })).toBeVisible();
    expect(screen.getByRole("button", { name: "返回" })).toHaveFocus();
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
  });

  it("keeps Tab navigation inside the dialog", async () => {
    const user = userEvent.setup();
    renderWithClient(<Harness />);
    await user.click(screen.getByRole("button", { name: "打开操作" }));
    const back = screen.getByRole("button", { name: "返回" });
    const confirm = screen.getByRole("button", { name: "确认" });
    confirm.focus();
    await user.tab();
    expect(back).toHaveFocus();
  });
});
