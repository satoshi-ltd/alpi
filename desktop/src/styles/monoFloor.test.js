import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const read = (rel) => readFileSync(join(import.meta.dirname, rel), "utf8");
const TOKENS = read("tokens.css");
const token = (name) => {
  const m = new RegExp(`--${name}:\\s*([^;]+);`).exec(TOKENS);
  return m[1].trim();
};

function px(value, parent) {
  const v = value.trim();
  const ref = /^var\(--([a-z0-9-]+)\)$/.exec(v);
  if (ref) return px(token(ref[1]), parent);
  const max = /^max\((.*)\)$/.exec(v);
  if (max) return Math.max(...max[1].split(",").map((part) => px(part, parent)));
  if (v.endsWith("px")) return parseFloat(v);
  if (v.endsWith("em")) return parseFloat(v) * parent;
  throw new Error(`cannot size ${v}`);
}

const fontSize = (css, selector) => {
  const body = new RegExp(`(^|\\n)\\s*${selector.replace(/\./g, "\\.")}\\s*\\{([^}]*)\\}`).exec(css)?.[2] ?? "";
  return /font-size:\s*([^;]+);/.exec(body)[1];
};

describe("the 12 px floor for mono and small notes", () => {
  it.each([12, 13, 14, 15, 16])("never draws .mono under 12 px inside %i px text, and scales it above", (parent) => {
    const size = px(fontSize(read("design-system.css"), ".mono"), parent);
    expect(size).toBeGreaterThanOrEqual(12);
    expect(size).toBeCloseTo(Math.max(12, parent * 0.92), 5);
  });

  it("keeps the workgroup phase notes at 12 px in a 12 px detail", () => {
    expect(px(fontSize(read("../pages/WorkgroupView.module.css"), ".phaseNote"), 12)).toBe(12);
  });
});
