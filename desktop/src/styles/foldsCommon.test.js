import { describe, expect, it } from "vitest";
import { TONAL_MIN_SIZE, alpacaTones, isTonalSize, tonalAlpacaPolygons } from "../../../common/alpacaTones.mjs";
import { contrastRatio } from "../../../common/crease.mjs";
import { ALPACA_ROW_SCALE, FOLD_SIZES, alpacaDrawnSize, defaultAsAlpaca, withDefaultAlpaca, ALPACA_FOLD, ALPACA_LOW_FOLD, FOLD_IDS, WORKGROUP_FOLD, foldPolygons, normaliseFold } from "../../../common/folds.mjs";

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

describe("tonal alpaca", () => {
  const GROUNDS = { light: "#ffffff", dark: "#121212" };

  it("starts at 48 px", () => {
    expect([47, 48].map(isTonalSize)).toEqual([false, true]);
    expect(TONAL_MIN_SIZE).toBe(48);
  });

  it.each(["light", "dark"])("holds three distinct %s tones of one hue, lightest first, that each read on the ground", (mode) => {
    const tones = alpacaTones(mode);
    expect(new Set(tones).size).toBe(3);
    const lightness = tones.map((hex) => contrastRatio(hex, "#000000"));
    expect([...lightness].sort((a, b) => b - a)).toEqual(lightness);
    for (const tone of tones) expect(contrastRatio(tone, GROUNDS[mode])).toBeGreaterThanOrEqual(3);
    const hue = (hex) => {
      const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
      return Math.atan2(Math.sqrt(3) * (g - b), 2 * r - g - b) * (180 / Math.PI);
    };
    const hues = tones.filter((hex) => hex !== "#ffffff").map(hue);
    expect(Math.max(...hues) - Math.min(...hues)).toBeLessThan(20);
  });

  it("gives every facet of the twelve a tone from that set", () => {
    const polygons = tonalAlpacaPolygons("light");
    expect(polygons).toHaveLength(12);
    expect(new Set(polygons.map((p) => p.fill))).toEqual(new Set(alpacaTones("light")));
  });
});

describe("alpaca drawn size in rows", () => {
  it("scales the row alpaca by 1.25 to exactly 20 and the header alpaca to 26", () => {
    expect(ALPACA_ROW_SCALE).toBe(1.25);
    expect(alpacaDrawnSize(FOLD_SIZES.row)).toBe(20);
    expect(alpacaDrawnSize(FOLD_SIZES.header)).toBe(26);
  });

  it("overflows its slot by an even number of pixels so the offset is whole", () => {
    for (const slot of [12, 14, 16, 18, 20, 22, 24, 28, 32, 40]) {
      const drawn = alpacaDrawnSize(slot);
      expect(Number.isInteger(drawn)).toBe(true);
      expect((drawn - slot) % 2).toBe(0);
    }
  });
});
