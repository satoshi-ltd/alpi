import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CommandPalette, { SESSION_CACHE_TTL_MS, _resetSessionCache, loadRecentSessions } from "./CommandPalette.jsx";

describe("CommandPalette", () => {
  it("keeps shortcut help rows informational", () => {
    const onClose = vi.fn();
    render(
      <CommandPalette
        open
        onClose={onClose}
        commands={[
          {
            id: "help:jump",
            group: "General",
            label: "Jump to profile / workgroup",
            hint: "⌘1–9",
          },
        ]}
      />,
    );

    fireEvent.click(screen.getByText("Jump to profile / workgroup"));

    expect(onClose).not.toHaveBeenCalled();
  });

  it("runs command rows and closes the palette", () => {
    const onClose = vi.fn();
    const action = vi.fn();
    render(
      <CommandPalette
        open
        onClose={onClose}
        commands={[
          {
            id: "view:notifications",
            group: "View",
            label: "Notifications",
            hint: "⌘O",
            action,
          },
        ]}
      />,
    );

    fireEvent.click(screen.getByText("Notifications"));

    expect(action).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});

beforeEach(() => {
  _resetSessionCache();
  invoke.mockReset();
});

describe("CommandPalette search", () => {
  const profiles = [{ name: "alpi", accent: "#f0b447" }, { name: "builder" }];
  const workgroups = [{ id: "launch-crew", name: "launch-crew", profile: "alpi" }];

  it("lists only commands until the user types, then profiles, workgroups and sessions too", async () => {
    invoke.mockResolvedValue([
      { id: "s1", profile: "alpi", kind: "chat", first_user: "Summarize yesterday's deploys", updated_at: 10 },
      { id: "s2", profile: "doc", kind: "workgroup", first_user: "[workgroup] x", updated_at: 11 },
    ]);
    const onOpenProfile = vi.fn();
    const onOpenSession = vi.fn();
    render(
      <CommandPalette
        open
        onClose={vi.fn()}
        commands={[{ id: "create:chat", group: "Chat", label: "New session", hint: "⌘N", action: vi.fn() }]}
        profiles={profiles}
        workgroups={workgroups}
        jumpHints={{ "profile:alpi": 1 }}
        onOpenProfile={onOpenProfile}
        onOpenSession={onOpenSession}
      />,
    );
    expect(screen.queryByText("Profiles")).toBeNull();
    const input = screen.getByRole("combobox");
    await waitFor(() => expect(invoke).toHaveBeenCalledWith("sessions", expect.objectContaining({ profile: "alpi", limit: 12 })));
    expect(invoke).toHaveBeenCalledWith("sessions", expect.objectContaining({ profile: "builder" }));

    fireEvent.change(input, { target: { value: "dep" } });
    await waitFor(() => expect(screen.getByText("Sessions")).toBeInTheDocument());
    const option = screen.getAllByRole("option").find((o) => o.textContent.includes("deploys"));
    expect(option.querySelector("mark").textContent).toBe("dep");
    expect(screen.queryByText("[workgroup] x")).toBeNull();

    fireEvent.change(input, { target: { value: "alp" } });
    const first = screen.getAllByRole("option")[0];
    expect(first.textContent).toContain("alpi");
    expect(first.getAttribute("aria-selected")).toBe("true");
    expect(input.getAttribute("aria-activedescendant")).toBe(first.id);
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onOpenProfile).toHaveBeenCalledWith(profiles[0]);
  });

  it("renders key hints as one chip per token and prose hints as text", () => {
    render(
      <CommandPalette
        open
        onClose={vi.fn()}
        commands={[
          { id: "help:jump", group: "General", label: "Jump", hint: "⌘1–9" },
          { id: "pref:theme", group: "Preferences", label: "Switch theme", hint: "light · dark · system", action: vi.fn() },
        ]}
      />,
    );
    const jump = screen.getAllByRole("option").find((o) => o.textContent.startsWith("Jump"));
    expect(Array.from(jump.querySelectorAll("[data-keys] [aria-hidden]")).map((n) => n.textContent)).toEqual(["⌘", "1–9"]);
    const theme = screen.getAllByRole("option").find((o) => o.textContent.includes("Switch theme"));
    expect(theme.querySelectorAll("[data-keys]")).toHaveLength(0);
    expect(theme.textContent).toContain("light · dark · system");
  });

  it("scrolls the highlighted row into view while arrowing", () => {
    const spy = vi.fn();
    Element.prototype.scrollIntoView = spy;
    render(
      <CommandPalette
        open
        onClose={vi.fn()}
        commands={[
          { id: "a", group: "G", label: "Alpha", action: vi.fn() },
          { id: "b", group: "G", label: "Beta", action: vi.fn() },
        ]}
      />,
    );
    spy.mockClear();
    fireEvent.keyDown(screen.getByRole("combobox"), { key: "ArrowDown" });
    expect(spy).toHaveBeenCalledWith({ block: "nearest" });
    delete Element.prototype.scrollIntoView;
  });
});

describe("palette session source", () => {
  it("fetches profiles in parallel, bounded, and caches per connection with a TTL", async () => {
    let inFlight = 0;
    let peak = 0;
    invoke.mockImplementation(async (_cmd, { profile }) => {
      inFlight += 1;
      peak = Math.max(peak, inFlight);
      await new Promise((r) => setTimeout(r, 5));
      inFlight -= 1;
      return [{ id: `s-${profile}`, profile, kind: "chat", first_user: "hi", updated_at: profile.length }];
    });
    const names = ["a", "bb", "ccc", "dddd", "eeeee", "ffffff"];
    const rows = await loadRecentSessions("local", names, 1000);
    expect(invoke).toHaveBeenCalledTimes(6);
    expect(peak).toBeGreaterThan(1);
    expect(peak).toBeLessThanOrEqual(4);
    expect(rows[0].profile).toBe("ffffff");
    await loadRecentSessions("local", names, 1000 + SESSION_CACHE_TTL_MS - 1);
    expect(invoke).toHaveBeenCalledTimes(6);
    await loadRecentSessions("remote", names, 1000);
    expect(invoke).toHaveBeenCalledTimes(12);
    await loadRecentSessions("local", names, 1000 + SESSION_CACHE_TTL_MS + 1);
    expect(invoke).toHaveBeenCalledTimes(18);
  });

  it("never shows the previous connection's sessions after a switch", async () => {
    invoke.mockImplementation(async (_cmd, { connectionId, profile }) =>
      connectionId === "local"
        ? [{ id: "old", profile, kind: "chat", first_user: "old deploy", updated_at: 1 }]
        : new Promise(() => {}),
    );
    const props = { open: true, onClose: vi.fn(), commands: [], profiles: [{ name: "alpi" }], onOpenSession: vi.fn() };
    const { rerender } = render(<CommandPalette {...props} connectionId="local" />);
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "deploy" } });
    await waitFor(() => expect(screen.getByText("deploy", { exact: false })).toBeInTheDocument());
    rerender(<CommandPalette {...props} connectionId="remote" />);
    expect(screen.queryByText("old", { exact: false })).toBeNull();
  });

  it("keeps the highlighted row when results arrive while typing", async () => {
    let release;
    invoke.mockImplementation(() => new Promise((r) => { release = r; }));
    const first = vi.fn();
    const second = vi.fn();
    render(
      <CommandPalette
        open
        onClose={vi.fn()}
        profiles={[{ name: "alpha" }]}
        commands={[
          { id: "x1", group: "Actions", label: "Alpha run", action: first },
          { id: "x2", group: "Actions", label: "Alpha stop", action: second },
        ]}
      />,
    );
    const input = screen.getByRole("combobox");
    fireEvent.change(input, { target: { value: "alpha" } });
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "ArrowDown" });
    const selected = () => screen.getAllByRole("option").find((o) => o.getAttribute("aria-selected") === "true");
    expect(selected().textContent).toContain("Alpha stop");
    await act(async () => { release([{ id: "s", profile: "alpha", kind: "chat", first_user: "alpha notes", updated_at: 1 }]); });
    await waitFor(() => expect(screen.getByText("Sessions")).toBeInTheDocument());
    expect(selected().textContent).toContain("Alpha stop");
    fireEvent.keyDown(input, { key: "Enter" });
    expect(second).toHaveBeenCalledTimes(1);
  });
});
