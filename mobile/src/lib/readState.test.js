import { describe, it, expect, beforeEach, vi } from "vitest";
import * as SecureStore from "expo-secure-store";
import {
  markProfileRead,
  isProfileUnread,
  markWorkgroupRead,
  isWorkgroupUnread,
  resetReadState,
} from "./readState.js";

beforeEach(() => {
  resetReadState();
  vi.resetAllMocks();
  SecureStore.getItemAsync.mockResolvedValue(null);
});

describe("isProfileUnread", () => {
  it("falsy key parts → not unread (defensive)", async () => {
    // Trigger lazy load.
    expect(isProfileUnread("local", "", 100)).toBe(false);
    expect(isProfileUnread("local", "doc", 0)).toBe(false);
    expect(isProfileUnread("local", null, 100)).toBe(false);
  });

  it("after markProfileRead, an older session timestamp is NOT unread", () => {
    markProfileRead("local", "doc", 200);
    expect(isProfileUnread("local", "doc", 200)).toBe(false);
    expect(isProfileUnread("local", "doc", 199)).toBe(false);
  });

  it("a newer session timestamp IS unread", () => {
    markProfileRead("local", "doc", 200);
    expect(isProfileUnread("local", "doc", 250)).toBe(true);
  });

  it("scopes per (connId, name) — sibling daemons don't share read state", () => {
    markProfileRead("conn-a", "doc", 200);
    expect(isProfileUnread("conn-a", "doc", 200)).toBe(false);
    expect(isProfileUnread("conn-b", "doc", 200)).toBe(true);  // never marked on conn-b
  });
});

describe("isWorkgroupUnread", () => {
  it("scopes per (connId, profile, id)", () => {
    markWorkgroupRead("conn-a", "doc", "wg-1", 100);
    expect(isWorkgroupUnread("conn-a", "doc", "wg-1", 100)).toBe(false);
    expect(isWorkgroupUnread("conn-a", "doc", "wg-1", 150)).toBe(true);
    expect(isWorkgroupUnread("conn-a", "doc", "wg-2", 100)).toBe(true);   // different wg
    expect(isWorkgroupUnread("conn-b", "doc", "wg-1", 100)).toBe(true);   // different conn
  });

  it("missing parts → false", () => {
    expect(isWorkgroupUnread("conn-a", "", "wg-1", 100)).toBe(false);
    expect(isWorkgroupUnread("conn-a", "doc", "", 100)).toBe(false);
  });
});

describe("resetReadState", () => {
  it("drops marks: a previously-read profile is unread again after reset", () => {
    // 250 > 200 was unread; mark catches up; after reset there's no mark again so the same ts surfaces as unread.
    markProfileRead("local", "doc", 200);
    markProfileRead("local", "doc", 250);
    expect(isProfileUnread("local", "doc", 250)).toBe(false);
    resetReadState();
    SecureStore.getItemAsync.mockResolvedValueOnce(null);
    expect(isProfileUnread("local", "doc", 250)).toBe(true);
  });
});
