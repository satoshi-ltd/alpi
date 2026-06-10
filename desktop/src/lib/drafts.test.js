import { describe, it, expect, beforeEach } from "vitest";
import { clearDraft, getDraft, setDraft } from "./drafts.js";

beforeEach(() => localStorage.clear());

describe("drafts", () => {
  it("round-trips per key without bleeding", () => {
    setDraft("chat|pk-a", "hola");
    setDraft("wg|local|doc|w1", "task draft");
    expect(getDraft("chat|pk-a")).toBe("hola");
    expect(getDraft("wg|local|doc|w1")).toBe("task draft");
    expect(getDraft("chat|pk-b")).toBe("");
  });

  it("clearing and whitespace-only drafts remove the entry", () => {
    setDraft("k", "text");
    clearDraft("k");
    expect(getDraft("k")).toBe("");
    setDraft("k", "   ");
    expect(getDraft("k")).toBe("");
  });

  it("caps stored drafts at 50, evicting the oldest", () => {
    for (let i = 0; i < 55; i += 1) setDraft(`k${i}`, `d${i}`);
    const stored = JSON.parse(localStorage.getItem("alpi.drafts.v1"));
    expect(Object.keys(stored)).toHaveLength(50);
    expect(getDraft("k0")).toBe("");
    expect(getDraft("k54")).toBe("d54");
  });

  it("null key is a no-op", () => {
    setDraft(null, "x");
    expect(getDraft(null)).toBe("");
  });
});
