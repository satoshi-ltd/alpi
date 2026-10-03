import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, fireEvent, screen, cleanup, waitFor } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";

import ApprovalModal from "./ApprovalModal.jsx";

const REQUEST = {
  request_id: "a1",
  profile: "doc",
  command: "rm -rf build",
  cwd: "/tmp/x",
  severity: "caution",
  deadline: Date.now() + 60_000,
};

describe("ApprovalModal", () => {
  beforeEach(() => {
    invoke.mockReset();
    invoke.mockResolvedValue({ ok: true });
  });

  afterEach(() => {
    cleanup();
  });

  it("flags the alert with the danger icon, not a profile glyph", () => {
    render(<ApprovalModal requests={[REQUEST]} onResolved={() => {}} />);
    const dialog = screen.getByRole("dialog");
    expect(dialog.querySelector('[data-icon="triangle-alert"]')).toBeTruthy();
    expect(dialog.querySelector(".ds-diamond")).toBeNull();
  });

  it("says who asks before it says danger: the asking profile's object and name, no red ALERT", () => {
    const { container } = render(
      <ApprovalModal requests={[REQUEST]} onResolved={() => {}} profiles={[{ name: REQUEST.profile, fold: "heart", accent: "#f36a8a" }]} />,
    );
    const dialog = screen.getByRole("dialog");
    expect(dialog.querySelector("[data-fold]").dataset.fold).toBe("heart");
    expect(screen.queryByText("ALERT")).toBeNull();
    expect(container.ownerDocument.body.textContent).toContain("wants to run a command");
  });

  it("keeps the auto-deny countdown on its own line so a long name never cuts it", () => {
    render(<ApprovalModal requests={[{ ...REQUEST, deadline: Date.now() + 30_000 }]} onResolved={() => {}} />);
    const deadline = screen.getByText(/^auto-deny in \d+s$/);
    expect(deadline.className).toContain("deadline");
    expect(deadline.closest("[class*='who']")).toBeNull();
  });

  it("denies on Escape and names the dialog", async () => {
    const onResolved = vi.fn();
    render(<ApprovalModal requests={[REQUEST]} onResolved={onResolved} />);
    expect(screen.getByRole("dialog", { name: "Allow this command?" })).toBeInTheDocument();
    fireEvent.keyDown(document.body, { key: "Escape" });
    await waitFor(() => expect(invoke).toHaveBeenCalledWith("approval_respond", { requestId: "a1", choice: "deny" }));
    expect(onResolved).toHaveBeenCalledWith("a1", "deny");
  });

  it("keeps Deny in the footer and disables the choices while a reply is in flight", async () => {
    let settle;
    invoke.mockImplementation(() => new Promise((resolve) => { settle = resolve; }));
    render(<ApprovalModal requests={[REQUEST]} onResolved={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /Allow once/ }));
    expect(screen.getByRole("button", { name: "Deny" })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Always allow/ })).toBeDisabled();
    settle({ ok: true });
    await waitFor(() => expect(invoke).toHaveBeenCalledWith("approval_respond", { requestId: "a1", choice: "once" }));
  });
});
