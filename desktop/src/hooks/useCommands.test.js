import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useCommands } from "./useCommands.js";

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
  it("shows profile browse commands while settings has an active profile", () => {
    const commands = renderCommands();

    expect(commands.map((cmd) => cmd.id)).toEqual(
      expect.arrayContaining(["profile:tools", "profile:skills", "profile:memory"]),
    );
  });

  it("does not show profile browse commands without an active profile", () => {
    const commands = renderCommands({ activeProfileName: null });

    expect(commands.map((cmd) => cmd.id)).not.toEqual(
      expect.arrayContaining(["profile:tools", "profile:skills", "profile:memory"]),
    );
  });

  it("shows profile session history as a chat command", () => {
    const onOpenHistory = vi.fn();
    const commands = renderCommands({ onOpenHistory });
    const command = commands.find((cmd) => cmd.id === "chat:sessions");

    expect(command).toMatchObject({
      group: "Chat",
      label: "Switch @doc sessions",
      hint: "⇧⌘H",
    });
    command.action();
    expect(onOpenHistory).toHaveBeenCalledTimes(1);
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

  it("includes notifications in the command palette", () => {
    const onToggleNotifications = vi.fn();
    const commands = renderCommands({ onToggleNotifications });
    const command = commands.find((cmd) => cmd.id === "view:notifications");

    expect(command).toMatchObject({
      group: "View",
      label: "Notifications",
      hint: "⌘O",
    });
    command.action();
    expect(onToggleNotifications).toHaveBeenCalledTimes(1);
  });

  it("does not include the removed sidebar toggle", () => {
    const commands = renderCommands();

    expect(commands.map((cmd) => cmd.id)).not.toContain("view:sidebar");
    expect(commands.map((cmd) => cmd.hint)).not.toContain("⌘B");
  });
});
