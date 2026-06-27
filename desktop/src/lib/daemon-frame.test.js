import { describe, it, expect } from "vitest";
import {
  classifyDaemonPayload,
  fromDaemonFrame,
  isActiveWorkgroupView,
} from "./daemon-frame.js";

describe("classifyDaemonPayload", () => {
  it("drops malformed payloads", () => {
    expect(classifyDaemonPayload(null, "local")).toBe("drop");
    expect(classifyDaemonPayload(undefined, "local")).toBe("drop");
    expect(classifyDaemonPayload("nope", "local")).toBe("drop");
  });

  it("drops frames from a non-active daemon", () => {
    const payload = { connection_id: "remote-1", frame: { event: "wg.post" } };
    expect(classifyDaemonPayload(payload, "local")).toBe("drop");
  });

  it("classifies reconnect backfill frames as replay", () => {
    const payload = {
      connection_id: "local",
      replay: true,
      frame: { event: "wg.post", data: { profile: "doc", wg_id: "w1" } },
    };
    expect(classifyDaemonPayload(payload, "local")).toBe("replay");
  });

  it("classifies matching live frames as live", () => {
    const payload = { connection_id: "local", frame: { event: "wg.post" } };
    expect(classifyDaemonPayload(payload, "local")).toBe("live");
  });

  it("treats payloads without connection_id as live (legacy emitters)", () => {
    expect(classifyDaemonPayload({ frame: { event: "x" } }, "local")).toBe("live");
  });
});

describe("isActiveWorkgroupView", () => {
  const ev = { profile: "doc", wg_id: "w1" };

  it("matches when the workgroup view is open on the same profile + wg", () => {
    expect(isActiveWorkgroupView({ kind: "workgroup", profile: "doc", id: "w1" }, ev)).toBe(true);
  });

  it("rejects a different workgroup or profile", () => {
    expect(isActiveWorkgroupView({ kind: "workgroup", profile: "doc", id: "w2" }, ev)).toBe(false);
    expect(isActiveWorkgroupView({ kind: "workgroup", profile: "muse", id: "w1" }, ev)).toBe(false);
  });

  it("rejects non-workgroup views and null view", () => {
    expect(isActiveWorkgroupView({ kind: "profile", profile: "doc" }, ev)).toBe(false);
    expect(isActiveWorkgroupView(null, ev)).toBe(false);
  });
});

describe("fromDaemonFrame", () => {
  it("returns null for malformed input", () => {
    expect(fromDaemonFrame(null)).toBeNull();
    expect(fromDaemonFrame(undefined)).toBeNull();
    expect(fromDaemonFrame("string")).toBeNull();
    expect(fromDaemonFrame({})).toBeNull();
    expect(fromDaemonFrame({ event: 42 })).toBeNull();
  });

  describe("session_changed", () => {
    it("maps profile + session_id", () => {
      const out = fromDaemonFrame({
        event: "session_changed",
        data: { profile: "doc", session_id: "abc" },
      });
      expect(out).toEqual({ kind: "session", profile: "doc", session_id: "abc" });
    });

    it("accepts data.id as fallback for session_id (legacy daemons)", () => {
      const out = fromDaemonFrame({
        event: "session_changed",
        data: { profile: "doc", id: "abc" },
      });
      expect(out).toEqual({ kind: "session", profile: "doc", session_id: "abc" });
    });

    it("returns null without a profile", () => {
      expect(fromDaemonFrame({ event: "session_changed", data: {} })).toBeNull();
    });
  });

  describe("workgroup transcript triggers", () => {
    it.each(["wg.post", "wg.done", "wg.task", "wg.skip"])(
      "maps %s with profile + wg_id",
      (event) => {
        const out = fromDaemonFrame({ event, data: { profile: "doc", wg_id: "wg-1" } });
        expect(out).toEqual({ kind: "workgroup_transcript", profile: "doc", wg_id: "wg-1" });
      },
    );

    it("returns null when wg_id missing", () => {
      expect(
        fromDaemonFrame({ event: "wg.post", data: { profile: "doc" } }),
      ).toBeNull();
    });
  });

  describe("workgroup meta", () => {
    it.each(["workgroup_changed", "workgroup_meta", "workgroup_members"])(
      "%s maps to workgroup_meta",
      (event) => {
        expect(fromDaemonFrame({ event, data: {} })).toEqual({ kind: "workgroup_meta" });
      },
    );
  });

  it("peer.pairing_request and peers_changed both map to peers", () => {
    expect(fromDaemonFrame({ event: "peer.pairing_request" })).toEqual({ kind: "peers" });
    expect(fromDaemonFrame({ event: "peers_changed" })).toEqual({ kind: "peers" });
  });

  it("subscriptions_changed maps to subscriptions", () => {
    expect(fromDaemonFrame({ event: "subscriptions_changed" })).toEqual({ kind: "subscriptions" });
  });

  describe("config catch-all", () => {
    it.each([
      "schedule.done",
      "schedule.failed",
      "schedule.changed",
      "profile_changed",
      "config_changed",
      "skills_changed",
      "memory_changed",
      "email_changed",
      "budget.threshold",
    ])("%s maps to config", (event) => {
      expect(fromDaemonFrame({ event, data: {} })).toEqual({ kind: "config" });
    });
  });

  it("approval.* frames return null — App.jsx handles them via the pending queue, not applyChange", () => {
    expect(fromDaemonFrame({ event: "approval.request", data: { request_id: "x" } })).toBeNull();
    expect(fromDaemonFrame({ event: "approval.resolved", data: { request_id: "x" } })).toBeNull();
  });

  it("unknown event kinds return null (forward-compat)", () => {
    expect(fromDaemonFrame({ event: "some.future.event", data: {} })).toBeNull();
  });
});
