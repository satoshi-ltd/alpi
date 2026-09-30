import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useCommands } from "./useCommands.js";
import { SHORTCUTS, keyTokens } from "../lib/shortcuts.js";

function renderCommands(overrides = {}) {
  const props = {
    view: { kind: "settings" },
    profiles: [{ name: "doc" }],
    workgroups: [],
    pinned: { profiles: [], workgroups: [] },
    searchOpen: false,
    activeProfileName: "doc",
    historyKind: "sessions",
    onOpenHistory: vi.fn(),
    onToggleNotifications: vi.fn(),
    onBrowseTools: vi.fn(),
    onBrowseSkills: vi.fn(),
    onBrowseMemory: vi.fn(),
    ...overrides,
  };
  return renderHook(() => useCommands(props)).result.current;
}

describe("useCommands", () => {
  it("lists the theme switch under Preferences when the shell provides it", () => {
    const onCycleTheme = vi.fn();
    const prefs = renderCommands({ onCycleTheme }).filter((c) => c.group === "Preferences");
    expect(prefs.map((c) => c.label)).toEqual(["Switch theme"]);
    prefs[0].action();
    expect(onCycleTheme).toHaveBeenCalledTimes(1);
    expect(renderCommands().some((c) => c.group === "Preferences")).toBe(false);
  });

  it("shows profile browse commands while settings has an active profile", () => {
    const commands = renderCommands();

    expect(commands.map((cmd) => cmd.id)).toEqual(
      expect.arrayContaining(["profile:tools", "profile:skills", "profile:memory", "profile:schedule"]),
    );
    expect(commands.find((cmd) => cmd.id === "profile:schedule")).toMatchObject({
      group: "Profile",
      label: "Schedule",
      hint: "⇧⌘E",
    });
  });

  it("does not show profile browse commands without an active profile", () => {
    const commands = renderCommands({ activeProfileName: null });

    expect(commands.map((cmd) => cmd.id)).not.toEqual(
      expect.arrayContaining(["profile:tools", "profile:skills", "profile:memory"]),
    );
  });

  it("exposes the sidebar filter with ⌘S when a toggle is provided", () => {
    const onToggleSidebarSearch = vi.fn();
    const commands = renderCommands({ onToggleSidebarSearch });
    const command = commands.find((cmd) => cmd.id === "view:find");

    expect(command).toMatchObject({
      group: "General",
      label: "Filter profiles & workgroups",
      hint: "⌘S",
    });
    command.action();
    expect(onToggleSidebarSearch).toHaveBeenCalledTimes(1);
  });

  it("labels the filter as close while the sidebar search is open", () => {
    const commands = renderCommands({
      onToggleSidebarSearch: vi.fn(),
      sidebarSearchOpen: true,
    });

    expect(commands.find((cmd) => cmd.id === "view:find")?.label).toBe("Close filter");
  });

  it("omits the sidebar filter without a toggle", () => {
    const commands = renderCommands();
    expect(commands.find((cmd) => cmd.id === "view:find")).toBeUndefined();
  });

  it("shows profile sessions as a profile command", () => {
    const onOpenHistory = vi.fn();
    const commands = renderCommands({ onOpenHistory });
    const command = commands.find((cmd) => cmd.id === "profile:sessions");

    expect(command).toMatchObject({
      group: "Profile",
      label: "Sessions",
      hint: "⇧⌘H",
    });
    command.action();
    expect(onOpenHistory).toHaveBeenCalledTimes(1);
  });

  it("offers New session under ⌘N from any non-empty view", () => {
    const onNewChat = vi.fn();
    const commands = renderCommands({ view: { kind: "workgroup" }, onNewChat });
    const command = commands.find((cmd) => cmd.id === "create:chat");

    expect(command).toMatchObject({ group: "Chat", label: "New session", hint: "⌘N" });
    command.action();
    expect(onNewChat).toHaveBeenCalledTimes(1);
    expect(renderCommands({ view: { kind: "empty" }, onNewChat }).map((c) => c.id)).not.toContain("create:chat");
  });

  it("shows profile pause and refresh when available", () => {
    const onToggleProfilePause = vi.fn();
    const onRefreshThread = vi.fn();
    const onToggleReadAloud = vi.fn();
    const commands = renderCommands({
      view: { kind: "profile" },
      onToggleProfilePause,
      onRefreshThread,
      canRefreshThread: true,
      onToggleReadAloud,
      canReadAloud: true,
    });

    expect(commands).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: "profile:pause",
          group: "Profile",
          label: "Pause profile",
          hint: "⇧⌘P",
        }),
        expect.objectContaining({
          id: "chat:refresh",
          group: "Chat",
          label: "Refresh thread",
          hint: "⇧⌘R",
        }),
        expect.objectContaining({
          id: "chat:read-aloud",
          group: "Chat",
          label: "Read aloud",
          hint: "⇧⌘L",
        }),
      ]),
    );
    commands.find((cmd) => cmd.id === "profile:pause").action();
    commands.find((cmd) => cmd.id === "chat:refresh").action();
    commands.find((cmd) => cmd.id === "chat:read-aloud").action();
    expect(onToggleProfilePause).toHaveBeenCalledTimes(1);
    expect(onRefreshThread).toHaveBeenCalledTimes(1);
    expect(onToggleReadAloud).toHaveBeenCalledTimes(1);
    expect(commands.map((cmd) => cmd.id)).not.toContain("profile:settings");
  });

  it("labels the read aloud command as stop while audio is active", () => {
    const commands = renderCommands({
      view: { kind: "profile" },
      onToggleReadAloud: vi.fn(),
      canReadAloud: true,
      readAloudActive: true,
    });

    expect(commands.find((cmd) => cmd.id === "chat:read-aloud")).toMatchObject({
      label: "Stop audio",
      hint: "⇧⌘L",
    });
  });

  it("shows task history as a workgroup command", () => {
    const onOpenHistory = vi.fn();
    const commands = renderCommands({
      activeProfileName: null,
      historyKind: "tasks",
      onOpenHistory,
    });
    const command = commands.find((cmd) => cmd.id === "workgroup:tasks");

    expect(command).toMatchObject({
      group: "Workgroup",
      label: "Task history",
      hint: "⇧⌘H",
    });
    command.action();
    expect(onOpenHistory).toHaveBeenCalledTimes(1);
  });

  it("shows workgroup pause and refresh when available", () => {
    const onToggleWorkgroupPause = vi.fn();
    const onRefreshThread = vi.fn();
    const commands = renderCommands({
      view: { kind: "workgroup" },
      activeProfileName: null,
      historyKind: "tasks",
      onToggleWorkgroupPause,
      workgroupPaused: true,
      onRefreshThread,
    });

    expect(commands).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: "workgroup:pause",
          group: "Workgroup",
          label: "Resume workgroup",
          hint: "⇧⌘P",
        }),
        expect.objectContaining({
          id: "workgroup:refresh",
          group: "Workgroup",
          label: "Refresh thread",
          hint: "⇧⌘R",
        }),
      ]),
    );
    commands.find((cmd) => cmd.id === "workgroup:pause").action();
    commands.find((cmd) => cmd.id === "workgroup:refresh").action();
    expect(onToggleWorkgroupPause).toHaveBeenCalledTimes(1);
    expect(onRefreshThread).toHaveBeenCalledTimes(1);
    expect(commands.map((cmd) => cmd.id)).not.toContain("workgroup:settings");
  });

  it("includes notifications in the command palette", () => {
    const onToggleNotifications = vi.fn();
    const commands = renderCommands({ onToggleNotifications });
    const command = commands.find((cmd) => cmd.id === "view:notifications");

    expect(command).toMatchObject({
      group: "General",
      label: "Notifications",
      hint: "⌘O",
    });
    command.action();
    expect(onToggleNotifications).toHaveBeenCalledTimes(1);
  });

  it("includes generic shortcut help in the command palette", () => {
    const commands = renderCommands();

    expect(commands).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: "help:jump",
          group: "General",
          label: "Jump to profile / workgroup",
          hint: "⌘1–9",
        }),
        expect.objectContaining({
          id: "help:palette",
          group: "General",
          label: "Command palette",
          hint: "⌘K",
        }),
      ]),
    );
    expect(commands.find((cmd) => cmd.id === "help:jump")).not.toHaveProperty("action");
    expect(commands.find((cmd) => cmd.id === "help:palette")).not.toHaveProperty("action");
  });

  it("lists the shortcuts sheet and the activity panel when the app wires them", () => {
    const onOpenShortcuts = vi.fn();
    const onToggleActivity = vi.fn();
    const commands = renderCommands({ onOpenShortcuts, onToggleActivity });

    expect(commands.find((cmd) => cmd.id === "view:shortcuts")).toMatchObject({ label: "Keyboard shortcuts", hint: "⌘/" });
    expect(commands.find((cmd) => cmd.id === "view:activity")).toMatchObject({ label: "Activity", hint: "⌘J" });
    expect(renderCommands().map((cmd) => cmd.id)).not.toContain("view:activity");
  });

  it("takes every key hint from the shortcut registry", () => {
    const commands = renderCommands({
      view: { kind: "profile" },
      activeProfileName: "doc",
      historyKind: "sessions",
      onOpenHistory: vi.fn(),
      onNewChat: vi.fn(),
      onOpenShortcuts: vi.fn(),
      onToggleActivity: vi.fn(),
      onToggleSidebarSearch: vi.fn(),
      onToggleNotifications: vi.fn(),
      onNewProfile: vi.fn(),
      onNewWorkgroup: vi.fn(),
      onOpenSettings: vi.fn(),
    });
    const registry = new Set(SHORTCUTS.map((s) => s.keys));
    const keyHints = commands.map((c) => c.hint).filter((h) => keyTokens(h));
    expect(keyHints.length).toBeGreaterThan(10);
    expect(keyHints.filter((h) => !registry.has(h))).toEqual([]);
  });

  it("does not list dynamic jump targets as navigation commands", () => {
    const commands = renderCommands();

    expect(commands.map((cmd) => cmd.group)).not.toContain("Navigate");
    expect(commands.map((cmd) => cmd.group)).not.toContain("Shortcuts");
    expect(commands.some((cmd) => cmd.id.startsWith("nav:"))).toBe(false);
    expect(commands).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: "help:jump",
          label: "Jump to profile / workgroup",
          hint: "⌘1–9",
        }),
      ]),
    );
  });

  it("does not include the removed sidebar toggle", () => {
    const commands = renderCommands();

    expect(commands.map((cmd) => cmd.id)).not.toContain("view:sidebar");
    expect(commands.map((cmd) => cmd.hint)).not.toContain("⌘B");
  });
});
