import { describe, expect, it } from "vitest";
import { defaultAsAlpaca, withDefaultAlpaca, ALPACA_FOLD, ALPACA_LOW_FOLD, FOLD_IDS, WORKGROUP_FOLD, foldPolygons, normaliseFold } from "../../../common/folds.mjs";

describe("reserved folds", () => {
  it("accepts the alpaca and the honeycomb but never offers them as profile objects", () => {
    expect(normaliseFold(" Alpaca ")).toBe(ALPACA_FOLD);
    expect(normaliseFold(WORKGROUP_FOLD)).toBe(WORKGROUP_FOLD);
    expect(normaliseFold("pencil")).toBe("diamond");
    expect(FOLD_IDS).not.toContain(ALPACA_FOLD);
    expect(FOLD_IDS).not.toContain(WORKGROUP_FOLD);
    expect(FOLD_IDS).toHaveLength(12);
  });

  it("draws the alpaca as twelve facets with no inset and every polygon carries its tone", () => {
    const polygons = foldPolygons(ALPACA_FOLD, "#f0b447", 72);
    expect(polygons).toHaveLength(12);
    expect(new Set(polygons.map((p) => p.tone))).toEqual(new Set([0, 1, 2]));
    const inset = foldPolygons("shield", "#f0b447", 72);
    expect(inset.every((p) => [0, 1, 2].includes(p.tone))).toBe(true);
  });
});

describe("withDefaultAlpaca", () => {
  it("makes the default profile the alpaca whatever an older daemon says and leaves the others alone", () => {
    expect(withDefaultAlpaca({ name: "default", fold: "diamond", accent: null })).toMatchObject({ fold: ALPACA_FOLD, accent: null });
    expect(defaultAsAlpaca("var(--accent)")({ name: "default" })).toMatchObject({ fold: ALPACA_FOLD, accent: "var(--accent)" });
    expect(withDefaultAlpaca({ name: "alpi", is_default: true })).toMatchObject({ fold: ALPACA_FOLD });
    const doc = { name: "doc", fold: "shield", accent: "#3899e2" };
    expect(withDefaultAlpaca(doc)).toBe(doc);
    expect(withDefaultAlpaca(undefined)).toBeUndefined();
  });
});

describe("the nine facet alpaca", () => {
  it("is drawn only when asked for, never by size: sidebar and headers keep the twelve facets", () => {
    expect(foldPolygons(ALPACA_FOLD, "#bc860e", 16)).toHaveLength(12);
    expect(foldPolygons(ALPACA_FOLD, "#bc860e", 20)).toHaveLength(12);
    expect(foldPolygons(ALPACA_LOW_FOLD, "#bc860e", 16)).toHaveLength(9);
    expect(normaliseFold(ALPACA_LOW_FOLD)).toBe("diamond");
  });
});
