import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = join(import.meta.dirname, "..");

function walk(dir, hit, out = []) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, hit, out);
    else if (hit(name)) out.push(p);
  }
  return out;
}

const CSS = walk(SRC, (n) => n.endsWith(".css"));
const CODE = walk(SRC, (n) => /\.jsx?$/.test(n) && !n.includes(".test."));

const declared = new Set(
  CSS.flatMap((p) => [...readFileSync(p, "utf8").matchAll(/(--[a-z0-9-]+)\s*:/g)].map((m) => m[1])),
);
const fromScript = new Set(
  CODE.flatMap((p) => [...readFileSync(p, "utf8").matchAll(/["'](--[a-z0-9-]+)["']/g)].map((m) => m[1])),
);

function unresolved() {
  const out = [];
  for (const p of CSS) {
    for (const m of readFileSync(p, "utf8").matchAll(/var\((--[a-z0-9-]+)/g)) {
      const name = m[1];
      if (!declared.has(name) && !fromScript.has(name)) {
        out.push(`${p.slice(SRC.length + 1)} → var(${name})`);
      }
    }
  }
  return [...new Set(out)].sort();
}

describe("custom properties referenced by the stylesheets", () => {
  it("reads the stylesheets at all, so a path mistake cannot fake a pass", () => {
    expect(CSS.length).toBeGreaterThan(50);
    expect(declared.size).toBeGreaterThan(60);
  });

  it("resolves every var() to something that exists", () => {
    // CSS never logs this: with a fallback it renders off-palette, without one it drops the rule.
    expect(unresolved()).toEqual([]);
  });
});
