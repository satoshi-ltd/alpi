import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";

import { InlineApproval, InlineClarification } from "./InlineRequest.jsx";

beforeEach(() => {
  invoke.mockReset();
  invoke.mockImplementation(async () => ({ ok: true }));
});

const approval = { request_id: "r1", profile: "doc", command: "rm -rf dist", severity: "caution", deadline: Date.now() + 42_000 };

describe("InlineApproval", () => {
  it("offers the four choices with a countdown and answers through the same command as the modal", async () => {
    const onResolved = vi.fn();
    render(<InlineApproval request={approval} onResolved={onResolved} />);
    expect(screen.getByText("rm -rf dist")).toBeTruthy();
    expect(screen.getByText(/auto-deny in 4\ds/)).toBeTruthy();
    for (const label of ["Deny", "Allow once", "Allow this session", "Always allow"]) {
      expect(screen.getByRole("button", { name: label })).toBeTruthy();
    }
    fireEvent.click(screen.getByRole("button", { name: "Allow this session" }));
    await waitFor(() => expect(onResolved).toHaveBeenCalledWith("r1", "session"));
    expect(invoke).toHaveBeenCalledWith("approval_respond", { requestId: "r1", choice: "session" });
  });

  it("denies on Escape while focus is inside it", async () => {
    const onResolved = vi.fn();
    render(<InlineApproval request={approval} onResolved={onResolved} />);
    const once = screen.getByRole("button", { name: "Allow once" });
    once.focus();
    fireEvent.keyDown(once, { key: "Escape" });
    await waitFor(() => expect(invoke).toHaveBeenCalledWith("approval_respond", { requestId: "r1", choice: "deny" }));
  });
});

describe("InlineClarification", () => {
  it("answers a single-choice question with the picked label", async () => {
    const onResolved = vi.fn();
    render(
      <InlineClarification
        request={{ request_id: "q1", profile: "doc", question: "Which env?", choices: [{ label: "prod" }, { label: "staging" }, { label: "dev" }], allow_other: false, multi: false }}
        onResolved={onResolved}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "staging" }));
    await waitFor(() => expect(onResolved).toHaveBeenCalledWith("q1", "staging"));
    expect(invoke).toHaveBeenCalledWith("clarification_respond", { requestId: "q1", choice: "staging" });
  });

  it("cancels on Escape", async () => {
    render(
      <InlineClarification
        request={{ request_id: "q2", profile: "doc", question: "Go?", choices: [{ label: "Yes" }, { label: "No" }], allow_other: false, multi: false }}
      />,
    );
    const yes = screen.getByRole("button", { name: "Yes" });
    fireEvent.keyDown(yes, { key: "Escape" });
    await waitFor(() => expect(invoke).toHaveBeenCalledWith("clarification_respond", { requestId: "q2", choice: "User cancelled clarification." }));
  });
});
