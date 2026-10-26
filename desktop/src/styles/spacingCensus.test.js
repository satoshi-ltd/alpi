import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

import { controlHeight, spaceScale } from "../../../common/tokens.mjs";

const SRC = join(import.meta.dirname, "..");
const walk = (dir) =>
  readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? walk(path) : [path];
  });
const SHEETS = walk(SRC).filter((p) => p.endsWith(".css") && !p.endsWith("tokens.css"));
const CSS = readFileSync(join(SRC, "styles/tokens.css"), "utf8");

const MICRO = new Set(["0", "1", "2", "3", ".5", "0.5"]);
const SCROLL_ROOM = new Set(["60", "80"]);
const HEIGHT_EXCEPTIONS = new Set(["18", "42"]);

const declarations = (property) =>
  SHEETS.flatMap((file) => {
    const found = [];
    const text = readFileSync(file, "utf8");
    for (const m of text.matchAll(new RegExp(`(?<![\\w-])(${property})\\s*:([^;{}]*)`, "g"))) {
      found.push({ file: relative(SRC, file), property: m[1], value: m[2] });
    }
    return found;
  });
const literals = (value) => [...value.replace(/var\([^)]*\)/g, "").matchAll(/(?<![\w.-])-?(\d*\.?\d+)px/g)].map((m) => m[1]);

describe("spacing census", () => {
  it("declares exactly the scale and the control heights shared with the phone", () => {
    for (const value of Object.values(spaceScale)) expect(CSS).toMatch(new RegExp(`--sp-${value}:\\s*${value}px;`));
    for (const value of Object.values(controlHeight)) expect(CSS).toMatch(new RegExp(`--ctl-${value}:\\s*${value}px;`));
  });

  it("scans a meaningful number of declarations", () => {
    expect(declarations("padding[a-z-]*|margin[a-z-]*|gap").length).toBeGreaterThan(300);
  });

  it("writes padding, margin and gap in scale tokens, zero or a documented micro value", () => {
    const offenders = declarations("padding[a-z-]*|margin[a-z-]*|gap|row-gap|column-gap").flatMap(({ file, property, value }) =>
      literals(value)
        .filter((px) => !MICRO.has(px) && !SCROLL_ROOM.has(px))
        .map((px) => `${file} ${property}:${value.trim()} (${px}px)`),
    );
    expect(offenders).toEqual([]);
  });

  it("never mixes a legacy --space-N step back in", () => {
    const offenders = SHEETS.filter((file) => /var\(--space-\d/.test(readFileSync(file, "utf8"))).map((f) => relative(SRC, f));
    expect(offenders).toEqual([]);
  });

  it("sizes controls from the four heights, never a literal between 19 and 48 px", () => {
    const offenders = declarations("min-height|height").flatMap(({ file, property, value }) =>
      literals(value)
        .filter((px) => Number(px) > 18 && Number(px) <= 48 && !HEIGHT_EXCEPTIONS.has(px))
        .map((px) => `${file} ${property}:${value.trim()}`),
    );
    expect(offenders).toEqual([]);
  });
});
