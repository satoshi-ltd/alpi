import { beforeEach, describe, expect, it } from "vitest";
import {
  baseSessionTitle,
  displaySessionTitle,
  getSessionTitle,
  normalizeSessionTitle,
  purgeConnectionSessionTitles,
  removeSessionTitles,
  setSessionTitle,
} from "./session-titles.js";

describe("session-titles", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("normalizes and caps saved titles", () => {
    const title = setSessionTitle("conn-a", "doc", "s1", `  hello\n\nworld ${"x".repeat(200)}  `);

    expect(title).toHaveLength(120);
    expect(title.startsWith("hello world")).toBe(true);
    expect(getSessionTitle("conn-a", "doc", "s1")).toBe(title);
  });

  it("uses custom title before the first user preview", () => {
    const session = { id: "s1", first_user: "original prompt" };

    setSessionTitle("conn-a", "doc", "s1", "Quarterly planning");

    expect(displaySessionTitle(session, { connectionId: "conn-a", profile: "doc" })).toBe("Quarterly planning");
  });

  it("clears a title with an empty value", () => {
    const session = { id: "s1", first_user: "original prompt" };
    setSessionTitle("conn-a", "doc", "s1", "Quarterly planning");

    setSessionTitle("conn-a", "doc", "s1", "   ");

    expect(getSessionTitle("conn-a", "doc", "s1")).toBe("");
    expect(displaySessionTitle(session, { connectionId: "conn-a", profile: "doc" })).toBe("original prompt");
  });

  it("scopes titles by connection, profile and session", () => {
    const session = { id: "shared", first_user: "fallback" };
    setSessionTitle("conn-a", "doc", "shared", "A");
    setSessionTitle("conn-b", "doc", "shared", "B");
    setSessionTitle("conn-a", "ops", "shared", "C");

    expect(displaySessionTitle(session, { connectionId: "conn-a", profile: "doc" })).toBe("A");
    expect(displaySessionTitle(session, { connectionId: "conn-b", profile: "doc" })).toBe("B");
    expect(displaySessionTitle(session, { connectionId: "conn-a", profile: "ops" })).toBe("C");
  });

  it("keeps the existing empty-session fallback", () => {
    expect(baseSessionTitle({ id: "abcdef123456", first_user: "" })).toBe("(empty · abcdef)");
  });

  it("removes titles for deleted sessions only", () => {
    setSessionTitle("conn-a", "doc", "s1", "One");
    setSessionTitle("conn-a", "doc", "s2", "Two");
    setSessionTitle("conn-a", "ops", "s1", "Other profile");

    expect(removeSessionTitles("conn-a", "doc", ["s1"])).toBe(true);

    expect(getSessionTitle("conn-a", "doc", "s1")).toBe("");
    expect(getSessionTitle("conn-a", "doc", "s2")).toBe("Two");
    expect(getSessionTitle("conn-a", "ops", "s1")).toBe("Other profile");
  });

  it("purges titles for a forgotten remote connection", () => {
    setSessionTitle("gone", "doc", "s1", "Gone");
    setSessionTitle("kept", "doc", "s1", "Kept");
    setSessionTitle(null, "doc", "s1", "Local");

    expect(purgeConnectionSessionTitles("gone")).toBe(true);

    expect(getSessionTitle("gone", "doc", "s1")).toBe("");
    expect(getSessionTitle("kept", "doc", "s1")).toBe("Kept");
    expect(getSessionTitle(null, "doc", "s1")).toBe("Local");
  });
});
