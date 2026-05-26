import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, fireEvent, screen, cleanup } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";
import ManageSessionsModal from "./ManageSessionsModal.jsx";

const NOW = Date.now() / 1000;
const DAY = 86_400;

const SESSIONS = [
  { id: "live",  kind: "chat", first_user: "active chat",      updated_at: NOW,                  started_at: NOW,           turn_count: 8,  size_bytes: 4_700 },
  { id: "old",   kind: "chat", first_user: "old chat",         updated_at: NOW - 95 * DAY,       started_at: NOW - 100 * DAY, turn_count: 18, size_bytes: 215_000 },
  { id: "stub",  kind: "chat", first_user: "stub",             updated_at: NOW - 2 * DAY,        started_at: NOW - 2 * DAY,  turn_count: 1,  size_bytes: 4_000 },
];

describe("ManageSessionsModal", () => {
  beforeEach(() => {
    invoke.mockReset();
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "sessions") return SESSIONS;
      if (cmd === "sessions_delete") return { deleted: [], errors: [] };
      return null;
    });
  });

  afterEach(() => {
    cleanup();
  });

  it("clears selection when the filter changes so Delete-N matches what will be deleted", async () => {
    render(
      <ManageSessionsModal
        open
        profile="doc"
        currentSessionId="live"
        onClose={() => {}}
      />,
    );

    await screen.findByText("stub");

    const stubRow = screen.getByText("stub").closest("tr");
    const oldRow = screen.getByText("old chat").closest("tr");
    fireEvent.click(stubRow.querySelector('input[type="checkbox"]'));
    fireEvent.click(oldRow.querySelector('input[type="checkbox"]'));

    expect(screen.getByRole("button", { name: /Delete 2/ })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /< 3 turns/ }));

    expect(screen.queryByRole("button", { name: /Delete \d/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Close" })).toBeInTheDocument();
  });

  it("delete sends exactly the visible-selected ids, never hidden ones", async () => {
    render(
      <ManageSessionsModal
        open
        profile="doc"
        currentSessionId="live"
        onClose={() => {}}
      />,
    );

    await screen.findByText("stub");
    const stubRow = screen.getByText("stub").closest("tr");
    fireEvent.click(stubRow.querySelector('input[type="checkbox"]'));
    expect(screen.getByRole("button", { name: /Delete 1/ })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Delete 1/ }));
    const typedInput = await screen.findByRole("textbox");
    fireEvent.change(typedInput, { target: { value: "DELETE" } });
    const confirmBtn = screen.getByRole("button", { name: "Delete 1 session" });
    fireEvent.click(confirmBtn);

    const call = invoke.mock.calls.find(([cmd]) => cmd === "sessions_delete");
    expect(call).toBeDefined();
    expect(call[1]).toEqual({ profile: "doc", ids: ["stub"] });
  });

  it("locks the active session — its checkbox is disabled", async () => {
    render(
      <ManageSessionsModal
        open
        profile="doc"
        currentSessionId="live"
        onClose={() => {}}
      />,
    );

    await screen.findByText("active chat");
    const liveRow = screen.getByText("active chat").closest("tr");
    expect(liveRow.querySelector('input[type="checkbox"]')).toBeDisabled();
    expect(screen.getByText("current session")).toBeInTheDocument();
  });
});
