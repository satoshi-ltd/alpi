import { describe, it, expect, beforeEach, vi } from "vitest";
import * as SecureStore from "expo-secure-store";
import {
  markProfileRead,
  isProfileUnread,
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

describe("a mark made before the keychain has answered", () => {
  it("is merged with the persisted marks instead of replacing them", async () => {
    vi.useFakeTimers();
    try {
      let answer;
      SecureStore.getItemAsync.mockImplementation(() => new Promise((resolve) => { answer = resolve; }));
      SecureStore.setItemAsync.mockResolvedValue(undefined);
      markProfileRead("local", "doc", 200);
      await vi.advanceTimersByTimeAsync(300);
      answer(JSON.stringify({ "local:profile:abby": 90 }));
      await vi.advanceTimersByTimeAsync(10);
      expect(SecureStore.setItemAsync).toHaveBeenCalledTimes(1);
      const written = JSON.parse(SecureStore.setItemAsync.mock.calls[0][1]);
      expect(written).toEqual({ "local:profile:abby": 90, "local:profile:doc": 200 });
      expect(isProfileUnread("local", "abby", 80)).toBe(false);
      expect(isProfileUnread("local", "doc", 150)).toBe(false);
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("marks a workgroup once kept", () => {
  it("are dropped from the keychain value on the next write, and the profile marks beside them stay", async () => {
    vi.useFakeTimers();
    try {
      SecureStore.getItemAsync.mockResolvedValue(JSON.stringify({
        "local:profile:abby": 90,
        "local:workgroup:abby/site-one": 120,
        "conn_9:workgroup:doc/roma": 300,
      }));
      SecureStore.setItemAsync.mockResolvedValue(undefined);
      markProfileRead("local", "doc", 200);
      await vi.advanceTimersByTimeAsync(300);
      const written = JSON.parse(SecureStore.setItemAsync.mock.calls[0][1]);
      expect(written).toEqual({ "local:profile:abby": 90, "local:profile:doc": 200 });
      expect(isProfileUnread("local", "abby", 80)).toBe(false);
    } finally {
      vi.useRealTimers();
    }
  });

  it("leave a profile whose own name holds the word untouched", async () => {
    vi.useFakeTimers();
    try {
      SecureStore.getItemAsync.mockResolvedValue(JSON.stringify({ "local:profile:x:workgroup:y": 90 }));
      SecureStore.setItemAsync.mockResolvedValue(undefined);
      markProfileRead("local", "doc", 200);
      await vi.advanceTimersByTimeAsync(300);
      expect(JSON.parse(SecureStore.setItemAsync.mock.calls[0][1])).toEqual({ "local:profile:x:workgroup:y": 90, "local:profile:doc": 200 });
    } finally {
      vi.useRealTimers();
    }
  });
});
