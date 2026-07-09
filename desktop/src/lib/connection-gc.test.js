import { beforeEach, describe, expect, it } from "vitest";
import { purgeConnectionStorage } from "./connection-gc.js";
import { getSessionTitle, setSessionTitle } from "./session-titles.js";
import { markProfileRead, isProfileUnread, purgeConnectionReadState } from "../hooks/useReadState.js";

beforeEach(() => {
  localStorage.clear();
});

describe("purgeConnectionStorage", () => {
  it("removes every persisted key of the forgotten connection and nothing else", () => {
    const seed = {
      "alf:profiles:v1:gone": "[]",
      "alf:workgroups:v1:gone": "[]",
      "alf:pinned:v2:gone": "[]",
      "alpi:workgroup-task-cache:v3:gone": "{}",
      "alpi.workgroup.cache.gone.doc.wg1": "[]",
      "alpi.session.cache.v1.gone.doc.s1": "{}",
      "alpi.session.cache.v1.index.gone.doc": "[]",
      "alf:profiles:v1:kept": "[]",
      "alpi.session.cache.v1.kept.doc.s1": "{}",
      "alpi.workgroup.cache.kept.doc.wg1": "[]",
      "alpi:read-state:v1": "{}",
    };
    for (const [k, v] of Object.entries(seed)) localStorage.setItem(k, v);
    setSessionTitle("gone", "doc", "s1", "Gone");
    setSessionTitle("kept", "doc", "s1", "Kept");

    purgeConnectionStorage("gone");

    for (const k of Object.keys(seed)) {
      if (k.includes("gone")) {
        expect(localStorage.getItem(k)).toBeNull();
      } else {
        expect(localStorage.getItem(k)).not.toBeNull();
      }
    }
    expect(getSessionTitle("gone", "doc", "s1")).toBe("");
    expect(getSessionTitle("kept", "doc", "s1")).toBe("Kept");
  });

  it("never touches the local connection's storage", () => {
    localStorage.setItem("alf:profiles:v1:local", "[]");
    purgeConnectionStorage("local");
    purgeConnectionStorage(null);
    expect(localStorage.getItem("alf:profiles:v1:local")).toBe("[]");
  });
});

describe("purgeConnectionReadState", () => {
  it("drops read marks for the forgotten connection only", () => {
    markProfileRead("gone", "doc", 100);
    markProfileRead("kept", "doc", 100);

    expect(isProfileUnread("gone", "doc", 50)).toBe(false);
    purgeConnectionReadState("gone");

    expect(isProfileUnread("gone", "doc", 50)).toBe(true);
    expect(isProfileUnread("kept", "doc", 50)).toBe(false);
  });
});
