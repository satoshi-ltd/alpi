import { describe, expect, it } from "vitest";
import { isDefaultProfile, splitDefaultProfile, withoutDefaultPin } from "../../../common/rosterOrder.mjs";

describe("splitDefaultProfile", () => {
  it("takes the default profile out of the list wherever it sits and keeps the rest in order", () => {
    const list = [{ name: "doc" }, { name: "default", is_default: true }, { name: "abby" }];
    const { front, rest } = splitDefaultProfile(list);
    expect(front).toBe(list[1]);
    expect(rest.map((p) => p.name)).toEqual(["doc", "abby"]);
  });

  it("recognises the default by is_default or by its reserved name", () => {
    expect(isDefaultProfile({ name: "default" })).toBe(true);
    expect(isDefaultProfile({ name: "host", is_default: true })).toBe(true);
    expect(isDefaultProfile({ name: "alpi" })).toBe(false);
    expect(isDefaultProfile(null)).toBe(false);
  });

  it("has no front when the connection does not serve the default profile", () => {
    const list = [{ name: "sentinel" }, { name: "curator" }];
    expect(splitDefaultProfile(list)).toEqual({ front: null, rest: list });
    expect(splitDefaultProfile(undefined)).toEqual({ front: null, rest: [] });
  });

  it("reads the profile through an accessor so a workgroup named default never takes the front", () => {
    const wg = { kind: "workgroup", name: "default" };
    const row = { kind: "profile", name: "default", raw: { name: "default", is_default: true } };
    const profileOf = (item) => (item.kind === "profile" ? item.raw : null);
    const { front, rest } = splitDefaultProfile([wg, row], profileOf);
    expect(front).toBe(row);
    expect(rest).toEqual([wg]);
  });
});

describe("withoutDefaultPin", () => {
  it("drops a stale default pin and keeps every other pin in order", () => {
    expect(withoutDefaultPin(["doc", "default", "abby"])).toEqual(["doc", "abby"]);
    expect(withoutDefaultPin(undefined)).toEqual([]);
  });
});
