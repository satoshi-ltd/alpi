import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { contrastRatio } from "../../../common/crease.mjs";
import { palettes } from "../../../common/tokens.mjs";

const NEUTRAL_KEYS = ["bg", "bgPane", "bgSide", "bgElev", "bgInput", "ink", "ink2", "ink3", "ink4", "line", "line2", "hover", "selected"];
const SLATE = /11, ?17, ?23|230, ?237, ?243|#0b1117|#3d4955|#626e7d|#b1bac4|#eef0f2|#f5f6f8|#f1f3f5|#0a0d11|#0c1014|#11151a|#161b22|#e6edf3|#828b97|#484f58|#1c242c/i;
const channels = (value) => (value.startsWith("#") ? [1, 3, 5].map((i) => parseInt(value.slice(i, i + 2), 16)) : value.match(/\d+(?:\.\d+)?/g).slice(0, 3).map(Number));

describe("neutral greys", () => {
  it.each(["light", "dark"])("gives every %s neutral equal red, green and blue so only profiles carry colour", (mode) => {
    for (const key of NEUTRAL_KEYS) {
      const [r, g, b] = channels(palettes[mode][key]);
      expect(r === g && g === b, `${mode}.${key} ${palettes[mode][key]}`).toBe(true);
    }
  });

  it.each(["light", "dark"])("keeps every %s text step at 4.5:1 on each surface", (mode) => {
    const p = palettes[mode];
    for (const ground of [p.bg, p.bgPane, p.bgSide, p.bgElev]) {
      for (const ink of [p.ink, p.ink2, p.ink3]) expect(contrastRatio(ink, ground), `${ink} on ${ground}`).toBeGreaterThanOrEqual(4.5);
    }
  });

  it.each(["styles/tokens.css", "../../common/tokens.mjs", "../../common/crease.mjs"])("leaves no slate in %s", (file) => {
    const source = readFileSync(join(import.meta.dirname, "..", file), "utf8");
    expect(source).not.toMatch(SLATE);
  });
});
