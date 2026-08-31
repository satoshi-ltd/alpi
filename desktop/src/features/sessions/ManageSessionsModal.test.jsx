import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, fireEvent, screen, cleanup, waitFor } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";
import ManageSessionsModal from "./ManageSessionsModal.jsx";
import { getSessionTitle, setSessionTitle } from "../../lib/session-titles.js";

const NOW = Date.now() / 1000;
const DAY = 86_400;

const SESSIONS = [
  { id: "live",  kind: "chat", first_user: "active chat",      updated_at: NOW,                  started_at: NOW,           turn_count: 8,  size_bytes: 4_700 },
  { id: "old",   kind: "chat", first_user: "old chat",         updated_at: NOW - 95 * DAY,       started_at: NOW - 100 * DAY, turn_count: 18, size_bytes: 215_000 },
  { id: "stub",  kind: "chat", first_user: "stub",             updated_at: NOW - 2 * DAY,        started_at: NOW - 2 * DAY,  turn_count: 1,  size_bytes: 4_000 },
];

describe("ManageSessionsModal", () => {
  beforeEach(() => {
    localStorage.clear();
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

  it("defaults to activity sorting before size, turns and created", async () => {
    render(
      <ManageSessionsModal
        open
        profile="doc"
        currentSessionId="live"
        onClose={() => {}}
      />,
    );

    await screen.findByText("active chat");

    expect(screen.getByRole("button", { name: "Activity" })).toBeInTheDocument();
    const previews = screen.getAllByText(/^(active chat|stub|old chat)$/).map((node) => node.textContent);
    expect(previews).toEqual(["active chat", "stub", "old chat"]);

    fireEvent.click(screen.getByRole("button", { name: "Activity" }));
    const labels = screen
      .getAllByText(/^(Activity|Size|Turns|Created)$/)
      .map((node) => node.textContent);
    expect(labels).toEqual(["Activity", "Activity", "Size", "Turns", "Created"]);
  });

  it("names the thread a session in the dialog, heading and count", async () => {
    render(
      <ManageSessionsModal
        open
        profile="doc"
        currentSessionId="live"
        onClose={() => {}}
      />,
    );

    await screen.findByText("active chat");

    expect(screen.getByRole("dialog", { name: "Manage sessions" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Sessions" })).toBeInTheDocument();
    expect(screen.getByText(/3 sessions/)).toBeInTheDocument();
    expect(screen.getByText("SESSION")).toBeInTheDocument();
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
    expect(call[1]).toEqual({ profile: "doc", ids: ["stub"], connectionId: null });
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

  it("shows and edits local session titles without breaking selection", async () => {
    setSessionTitle("conn-a", "doc", "stub", "Short stub");
    render(
      <ManageSessionsModal
        open
        profile="doc"
        connectionId="conn-a"
        currentSessionId="live"
        onClose={() => {}}
      />,
    );

    await screen.findByText("Short stub");
    expect(screen.queryByText("stub")).not.toBeInTheDocument();

    fireEvent.doubleClick(screen.getByText("Short stub"));
    const input = screen.getByRole("textbox", { name: "Session title" });
    fireEvent.change(input, { target: { value: "  Better stub title  " } });
    fireEvent.blur(input);
    expect(getSessionTitle("conn-a", "doc", "stub")).toBe("Better stub title");

    const row = await screen.findByText("Better stub title");
    fireEvent.click(row.closest("tr").querySelector('input[type="checkbox"]'));
    expect(screen.getByRole("button", { name: /Delete 1/ })).toBeInTheDocument();
  });

  it("cancels title editing with Escape", async () => {
    setSessionTitle("conn-a", "doc", "stub", "Short stub");
    render(
      <ManageSessionsModal
        open
        profile="doc"
        connectionId="conn-a"
        currentSessionId="live"
        onClose={() => {}}
      />,
    );

    await screen.findByText("Short stub");
    fireEvent.doubleClick(screen.getByText("Short stub"));
    const input = screen.getByRole("textbox", { name: "Session title" });
    fireEvent.change(input, { target: { value: "Discarded title" } });
    fireEvent.keyDown(input, { key: "Escape" });

    expect(getSessionTitle("conn-a", "doc", "stub")).toBe("Short stub");
    expect(await screen.findByText("Short stub")).toBeInTheDocument();
  });

  it("clears local titles for deleted sessions", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "sessions") return SESSIONS;
      if (cmd === "sessions_delete") return { deleted: ["stub"], errors: [] };
      return null;
    });
    setSessionTitle("conn-a", "doc", "stub", "Short stub");
    render(
      <ManageSessionsModal
        open
        profile="doc"
        connectionId="conn-a"
        currentSessionId="live"
        onClose={() => {}}
      />,
    );

    await screen.findByText("Short stub");
    const row = screen.getByText("Short stub").closest("tr");
    fireEvent.click(row.querySelector('input[type="checkbox"]'));
    fireEvent.click(screen.getByRole("button", { name: /Delete 1/ }));
    const typedInput = await screen.findByRole("textbox");
    fireEvent.change(typedInput, { target: { value: "DELETE" } });
    fireEvent.click(screen.getByRole("button", { name: "Delete 1 session" }));

    await waitFor(() => expect(getSessionTitle("conn-a", "doc", "stub")).toBe(""));
  });
});
