import { describe, it, expect } from "vitest";
import { parseTaskOpen, findLatestTask } from "./workgroup-tasks.js";

describe("parseTaskOpen", () => {
  it("returns null on bodies without a #task marker", () => {
    expect(parseTaskOpen("plain message")).toBeNull();
    expect(parseTaskOpen("")).toBeNull();
    expect(parseTaskOpen(null)).toBeNull();
  });

  it("extracts title-only when there is no body", () => {
    expect(parseTaskOpen("#task Ship ADR")).toEqual({
      title: "Ship ADR",
      body: "",
    });
  });

  it("extracts title and trims the multi-line body", () => {
    const post = "#task Ship ADR\n\nContext: signing-key custody.\n\nDeliverable: ADR merged.";
    expect(parseTaskOpen(post)).toEqual({
      title: "Ship ADR",
      body: "Context: signing-key custody.\n\nDeliverable: ADR merged.",
    });
  });

  it("allows @mentions before the #task marker", () => {
    const post = "@forge @sentinel #task Audit pipeline\n\nBody here.";
    expect(parseTaskOpen(post)).toEqual({
      title: "Audit pipeline",
      body: "Body here.",
    });
  });
});

describe("findLatestTask", () => {
  it("returns null on empty input", () => {
    expect(findLatestTask([])).toBeNull();
    expect(findLatestTask(null)).toBeNull();
  });

  it("returns the latest #task and folds in a later #done", () => {
    const msgs = [
      { seq: 1, body: "#task First", from_pubkey: "HUB" },
      { seq: 2, body: "noise", from_pubkey: "M" },
      { seq: 3, body: "#done shipped", from_pubkey: "HUB" },
    ];
    expect(findLatestTask(msgs, "HUB")).toEqual({
      state: "done",
      text: "First",
      seq: 1,
      result: "shipped",
    });
  });
});
