import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, it, expect } from "vitest";

import * as icons from "./icons.jsx";

const SRC = readFileSync(join(import.meta.dirname, "icons.jsx"), "utf8");

function exportedNames() {
  return [...SRC.matchAll(/^export (?:const|function) (\w+)/gm)].map((m) => m[1]);
}

function aliasPairs() {
  return [...SRC.matchAll(/^export const (\w+) = (\w+);$/gm)].map((m) => [m[1], m[2]]);
}

describe("icon exports", () => {
  it("gives every glyph exactly one exported name", () => {
    const exported = new Set(exportedNames());
    const doubled = aliasPairs().filter(([, target]) => exported.has(target));
    expect(doubled).toEqual([]);
  });

  it("exports no name twice", () => {
    const names = exportedNames();
    expect(names).toHaveLength(new Set(names).size);
  });

  it("keeps the I namespace resolvable, since most call sites reach glyphs through it", () => {
    expect(typeof icons.I).toBe("object");
    for (const [key, value] of Object.entries(icons.I)) {
      expect(typeof value, `I.${key}`).toBe("function");
    }
  });
});
