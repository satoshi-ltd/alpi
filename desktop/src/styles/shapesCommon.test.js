import { describe, expect, it } from "vitest";
import { DEFAULT_SHAPE, TWIN_SHAPE, SHAPE_IDS, WORKGROUP_SHAPE, defaultAsTwin, profileShape, shapeOf } from "../../../common/shapes.mjs";
import * as agentMarks from "../../../common/agentMarks.mjs";

describe("shapeOf", () => {
  it("passes every shape name through, Twin and the honeycomb included", () => {
    for (const shape of SHAPE_IDS) expect(shapeOf(shape)).toBe(shape);
    expect(shapeOf(TWIN_SHAPE)).toBe(TWIN_SHAPE);
    expect(shapeOf(WORKGROUP_SHAPE)).toBe(WORKGROUP_SHAPE);
    expect(SHAPE_IDS).not.toContain(TWIN_SHAPE);
    expect(SHAPE_IDS).not.toContain(WORKGROUP_SHAPE);
    expect(SHAPE_IDS).toHaveLength(12);
  });

  it("knows no legacy fold id: each one, and the old alpaca, draws the round", () => {
    expect("LEGACY_SHAPE" in agentMarks).toBe(false);
    for (const id of ["diamond", "shield", "house", "plane", "rocket", "star", "box", "bulb", "tree", "crown", "feather", "alpaca", " Alpaca "]) {
      expect(shapeOf(id), id).toBe(DEFAULT_SHAPE);
    }
  });

  it("reads anything else as the round", () => {
    expect(shapeOf("pencil")).toBe(DEFAULT_SHAPE);
    expect(shapeOf("alpaca-low")).toBe("round");
    expect(shapeOf(null)).toBe("round");
  });

  it("reads only a profile's shape, never a fold", () => {
    expect(profileShape({ shape: "bell", fold: "heart" })).toBe("bell");
    expect(profileShape({ fold: "plane" })).toBe("round");
    expect(profileShape({ fold: "heart" })).toBe("round");
    expect(profileShape({})).toBe("round");
    expect(profileShape(null)).toBe("round");
  });
});

describe("defaultAsTwin", () => {
  it("gives the default profile Twin and leaves the others alone", () => {
    const asTwin = defaultAsTwin();
    expect(asTwin({ name: "default", shape: "round", accent: null })).toMatchObject({ shape: TWIN_SHAPE, accent: null });
    expect(defaultAsTwin("var(--accent)")({ name: "default" })).toMatchObject({ shape: TWIN_SHAPE, accent: "var(--accent)" });
    expect(asTwin({ name: "alpi", is_default: true })).toMatchObject({ shape: TWIN_SHAPE });
    const doc = { name: "doc", shape: "bell", accent: "#3899e2" };
    expect(asTwin(doc)).toBe(doc);
    const old = { name: "old", fold: "shield", accent: "#3899e2" };
    expect(asTwin(old)).toBe(old);
    expect(profileShape(asTwin(old))).toBe("round");
    expect(asTwin(undefined)).toBeUndefined();
  });
});
