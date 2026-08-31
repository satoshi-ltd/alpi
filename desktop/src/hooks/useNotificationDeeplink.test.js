import { describe, it, expect, beforeEach, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { listen } from "@tauri-apps/api/event";

vi.mock("@tauri-apps/plugin-notification", () => ({
  isPermissionGranted: vi.fn(async () => true),
  requestPermission: vi.fn(async () => "granted"),
}));

import {
  connectionToSwitch,
  resolveDeeplink,
  useNotificationDeeplink,
} from "./useNotificationDeeplink.js";

beforeEach(() => {
  vi.clearAllMocks();
});

describe("resolveDeeplink", () => {
  it("opens the chat with a specific session when kind=chat carries id", () => {
    expect(resolveDeeplink({ kind: "chat", profile: "abby", id: "sess-1" })).toEqual({
      view: { kind: "profile", profile: "abby", sessionId: "sess-1" },
    });
  });

  it("opens the latest chat in the profile when kind=chat has no id", () => {
    expect(resolveDeeplink({ kind: "chat", profile: "abby" })).toEqual({
      view: { kind: "profile", profile: "abby", sessionId: null },
    });
  });

  it("opens the profile's latest chat when kind=profile", () => {
    expect(resolveDeeplink({ kind: "profile", profile: "abby" })).toEqual({
      view: { kind: "profile", profile: "abby", sessionId: null },
    });
  });

  it("opens a workgroup view when both profile and id are present", () => {
    expect(resolveDeeplink({ kind: "workgroup", profile: "vera", id: "wg-1" })).toEqual({
      view: { kind: "workgroup", profile: "vera", id: "wg-1" },
    });
  });

  it("opens the notifications modal with a target when kind=output carries profile+id", () => {
    const action = resolveDeeplink({ kind: "output", profile: "abby", id: "abc123" });
    expect(action).toEqual({ notifications: { profile: "abby", id: "abc123" } });
    expect(action.view).toBeUndefined();
  });

  it("threads connection_id into the output target so the modal loads the right daemon's notification", () => {
    const action = resolveDeeplink({ kind: "output", profile: "abby", id: "abc123", connection_id: "remote-b" });
    expect(action).toEqual({ notifications: { profile: "abby", id: "abc123", connectionId: "remote-b" } });
  });

  it("ignores kind=output with missing profile or id — the daemon's contract requires both", () => {
    expect(resolveDeeplink({ kind: "output", profile: "abby" })).toBeNull();
    expect(resolveDeeplink({ kind: "output", id: "abc123" })).toBeNull();
  });

  it("opens settings with a profile target when provided", () => {
    expect(resolveDeeplink({ kind: "settings", profile: "abby" })).toEqual({
      settingsTarget: { kind: "profile", id: "abby" },
      view: { kind: "settings" },
    });
  });

  it("opens settings without resetting the target when no profile attached — null would crash App.jsx settingsTarget.kind dereferences", () => {
    expect(resolveDeeplink({ kind: "settings" })).toEqual({
      view: { kind: "settings" },
    });
  });

  it("returns null for malformed payloads so the consumer skips dispatch", () => {
    expect(resolveDeeplink(null)).toBeNull();
    expect(resolveDeeplink(undefined)).toBeNull();
    expect(resolveDeeplink({})).toBeNull();
    expect(resolveDeeplink({ kind: "chat" })).toBeNull();
    expect(resolveDeeplink({ kind: "profile" })).toBeNull();
    expect(resolveDeeplink({ kind: "workgroup", profile: "vera" })).toBeNull();
    expect(resolveDeeplink({ kind: "unknown", profile: "abby" })).toBeNull();
  });
});

describe("connectionToSwitch", () => {
  it("switches to a background connection for a connection-scoped view (chat/profile/workgroup)", () => {
    expect(connectionToSwitch({ kind: "chat", connection_id: "remote-b" }, "local")).toBe("remote-b");
    expect(connectionToSwitch({ kind: "profile", connection_id: "remote-b" }, "local")).toBe("remote-b");
    expect(connectionToSwitch({ kind: "workgroup", connection_id: "remote-b" }, "local")).toBe("remote-b");
  });

  it("does NOT switch for settings/output deeplinks — a daemon-disconnect alert must not hijack the active connection", () => {
    expect(connectionToSwitch({ kind: "settings", connection_id: "remote-b" }, "local")).toBeNull();
    expect(connectionToSwitch({ kind: "output", connection_id: "remote-b" }, "local")).toBeNull();
  });

  it("returns null when the deeplink connection is already active", () => {
    expect(connectionToSwitch({ kind: "chat", connection_id: "local" }, "local")).toBeNull();
  });

  it("returns null for legacy notifications without a connection_id", () => {
    expect(connectionToSwitch({ kind: "chat" }, "local")).toBeNull();
    expect(connectionToSwitch({ kind: "chat", connection_id: "" }, "local")).toBeNull();
    expect(connectionToSwitch(null, "local")).toBeNull();
  });
});

describe("useNotificationDeeplink", () => {
  it("navigates only after explicit notification activation, never on delivery", async () => {
    const listeners = new Map();
    listen.mockImplementation(async (name, callback) => {
      listeners.set(name, callback);
      return () => listeners.delete(name);
    });
    const setView = vi.fn();
    const onSwitchConnection = vi.fn();

    renderHook(() => useNotificationDeeplink({
      setView,
      setSettingsTarget: vi.fn(),
      openNotifications: vi.fn(),
      onSwitchConnection,
      activeConnectionId: "local",
    }));

    await waitFor(() => expect(listeners.has("notification-activated")).toBe(true));
    expect(listeners.has("notification-fired")).toBe(false);
    expect(setView).not.toHaveBeenCalled();
    expect(onSwitchConnection).not.toHaveBeenCalled();

    await act(async () => {
      listeners.get("notification-activated")({
        payload: {
          deeplink: {
            kind: "workgroup",
            profile: "mira",
            id: "wg-1",
            connection_id: "remote-b",
          },
        },
      });
    });

    expect(onSwitchConnection).toHaveBeenCalledWith("remote-b");
    expect(setView).toHaveBeenCalledWith({
      kind: "workgroup",
      profile: "mira",
      id: "wg-1",
    });
  });
});
