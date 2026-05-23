import { describe, it, expect } from "vitest";

import { mergeProfileDraft } from "./profile-draft.js";

describe("mergeProfileDraft", () => {
  const fields = ["bio", "workspace", "model", "accent"];
  const blank = Object.fromEntries(fields.map((f) => [f, ""]));

  it("full reset on profile identity change", () => {
    const draft = { ...blank, workspace: "/typed/by/user" };
    const baseline = { ...blank, workspace: "/from/new/profile" };
    const next = mergeProfileDraft({
      draft,
      baseline,
      prevBaseline: { ...blank, workspace: "/from/old/profile" },
      profileKey: "abby|local",
      prevProfileKey: "doc|local",
    });
    expect(next.workspace).toBe("/from/new/profile");
  });

  it("full reset on connection change for the same profile", () => {
    const draft = { ...blank, workspace: "/typed" };
    const baseline = { ...blank, workspace: "/from/remote" };
    const next = mergeProfileDraft({
      draft,
      baseline,
      prevBaseline: { ...blank, workspace: "/from/local" },
      profileKey: "abby|remote",
      prevProfileKey: "abby|local",
    });
    expect(next.workspace).toBe("/from/remote");
  });

  it("hydrates fields the user has not touched when detail arrives async", () => {
    const draft = { ...blank };
    const prevBaseline = { ...blank };
    const baseline = { ...blank, workspace: "/Users/javi/Documents/Obsidian" };
    const next = mergeProfileDraft({
      draft,
      baseline,
      prevBaseline,
      profileKey: "doc|local",
      prevProfileKey: "doc|local",
    });
    expect(next.workspace).toBe("/Users/javi/Documents/Obsidian");
  });

  it("keeps the user's in-flight edit when baseline updates from a config_changed event", () => {
    const draft = { ...blank, workspace: "/typed/by/user" };
    const prevBaseline = { ...blank, workspace: "" };
    const baseline = { ...blank, workspace: "/persisted/from/elsewhere" };
    const next = mergeProfileDraft({
      draft,
      baseline,
      prevBaseline,
      profileKey: "doc|local",
      prevProfileKey: "doc|local",
    });
    expect(next.workspace).toBe("/typed/by/user");
  });

  it("untouched fields update even when another field is dirty", () => {
    const draft = { ...blank, workspace: "/typed", model: "" };
    const prevBaseline = { ...blank, workspace: "", model: "" };
    const baseline = { ...blank, workspace: "/external", model: "anthropic/claude-haiku-4-5" };
    const next = mergeProfileDraft({
      draft,
      baseline,
      prevBaseline,
      profileKey: "doc|local",
      prevProfileKey: "doc|local",
    });
    expect(next.workspace).toBe("/typed");
    expect(next.model).toBe("anthropic/claude-haiku-4-5");
  });

  it("after the user's save lands in baseline, future external updates flow through", () => {
    const userSavedValue = "/Users/javi/Documents/Obsidian";
    const draft = { ...blank, workspace: userSavedValue };
    const prevBaseline = { ...blank, workspace: userSavedValue };
    const baseline = { ...blank, workspace: "/changed/elsewhere" };
    const next = mergeProfileDraft({
      draft,
      baseline,
      prevBaseline,
      profileKey: "doc|local",
      prevProfileKey: "doc|local",
    });
    expect(next.workspace).toBe("/changed/elsewhere");
  });
});
