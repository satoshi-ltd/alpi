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
