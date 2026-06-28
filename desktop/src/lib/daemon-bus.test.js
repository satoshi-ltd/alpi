import { beforeEach, describe, expect, it, vi } from "vitest";
import { listen } from "@tauri-apps/api/event";

import { _resetDaemonBus, subscribe, subscribeDaemonEvent } from "./daemon-bus.js";

const captured = new Map();
let unlistenCalls;

beforeEach(() => {
  _resetDaemonBus();
  captured.clear();
  unlistenCalls = 0;
  listen.mockReset?.();
  listen.mockImplementation(async (name, cb) => {
    captured.set(name, cb);
    return () => { unlistenCalls += 1; };
  });
});

function fire(name, payload) {
  captured.get(name)?.({ payload });
}

describe("daemon-bus", () => {
  it("installs ONE Tauri listener for N subscribers of the same event", async () => {
    subscribeDaemonEvent(() => {});
    subscribeDaemonEvent(() => {});
    subscribeDaemonEvent(() => {});
    await Promise.resolve();
    const daemonCalls = listen.mock.calls.filter((c) => c[0] === "daemon-event");
    expect(daemonCalls).toHaveLength(1);
  });

  it("fans a single frame out to every subscriber", async () => {
    const a = vi.fn();
    const b = vi.fn();
    subscribeDaemonEvent(a);
    subscribeDaemonEvent(b);
    await Promise.resolve();
    fire("daemon-event", { frame: { event: "config_changed" } });
    expect(a).toHaveBeenCalledTimes(1);
    expect(b).toHaveBeenCalledTimes(1);
    expect(a.mock.calls[0][0].payload.frame.event).toBe("config_changed");
  });

  it("isolates a throwing subscriber from its siblings", async () => {
    const boom = vi.fn(() => { throw new Error("boom"); });
    const ok = vi.fn();
    subscribeDaemonEvent(boom);
    subscribeDaemonEvent(ok);
    await Promise.resolve();
    fire("daemon-event", {});
    expect(ok).toHaveBeenCalledTimes(1);
  });

  it("stops delivering after unsubscribe and tears down when the last leaves", async () => {
    const a = vi.fn();
    const unsubA = subscribeDaemonEvent(a);
    await Promise.resolve();
    unsubA();
    expect(unlistenCalls).toBe(1);
    fire("daemon-event", {});
    expect(a).not.toHaveBeenCalled();
  });

  it("keeps the listener alive while any subscriber remains", async () => {
    const a = vi.fn();
    const b = vi.fn();
    const unsubA = subscribeDaemonEvent(a);
    subscribeDaemonEvent(b);
    await Promise.resolve();
    unsubA();
    expect(unlistenCalls).toBe(0);
    fire("daemon-event", {});
    expect(b).toHaveBeenCalledTimes(1);
  });

  it("keeps separate listeners per event name", async () => {
    subscribeDaemonEvent(() => {});
    subscribe("connection-status", () => {});
    await Promise.resolve();
    expect(captured.has("daemon-event")).toBe(true);
    expect(captured.has("connection-status")).toBe(true);
  });

  it("re-arms a failed install while subscribers remain", async () => {
    let attempts = 0;
    listen.mockImplementation(async (name, cb) => {
      attempts += 1;
      if (attempts === 1) throw new Error("tauri ipc unavailable");
      captured.set(name, cb);
      return () => { unlistenCalls += 1; };
    });
    vi.useFakeTimers();
    try {
      const handler = vi.fn();
      subscribeDaemonEvent(handler);
      await vi.advanceTimersByTimeAsync(0);
      expect(attempts).toBe(1);
      await vi.advanceTimersByTimeAsync(2000);
      expect(attempts).toBe(2);
      fire("daemon-event", { ok: 1 });
      expect(handler).toHaveBeenCalledTimes(1);
    } finally {
      vi.useRealTimers();
    }
  });

  it("cancels the re-arm when the last subscriber leaves before it fires", async () => {
    listen.mockImplementation(async () => { throw new Error("down"); });
    vi.useFakeTimers();
    try {
      const unsub = subscribeDaemonEvent(() => {});
      await vi.advanceTimersByTimeAsync(0);
      const attemptsBefore = listen.mock.calls.length;
      unsub();
      await vi.advanceTimersByTimeAsync(5000);
      expect(listen.mock.calls.length).toBe(attemptsBefore);
    } finally {
      vi.useRealTimers();
    }
  });
});
