import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = join(import.meta.dirname, "..");
const TOKENS = readFileSync(join(import.meta.dirname, "tokens.css"), "utf8");
const DS = readFileSync(join(import.meta.dirname, "design-system.css"), "utf8");

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (name.endsWith(".css")) out.push(p);
  }
  return out;
}

const FILES = walk(SRC).map((p) => ({
  rel: relative(SRC, p),
  css: readFileSync(p, "utf8").replace(/\/\*[\s\S]*?\*\//g, ""),
}));

function reducedMotionBlocks(css) {
  const out = [];
  for (const m of css.matchAll(/@media\s*\(prefers-reduced-motion:\s*reduce\)\s*\{/g)) {
    let depth = 0;
    for (let i = m.index + m[0].length - 1; i < css.length; i += 1) {
      if (css[i] === "{") depth += 1;
      else if (css[i] === "}" && --depth === 0) {
        out.push(css.slice(m.index + m[0].length, i));
        break;
      }
    }
  }
  return out;
}

describe("motion vocabulary", () => {
  it("declares the shared durations", () => {
    expect(TOKENS).toMatch(/--dur-1:\s*120ms;/);
    expect(TOKENS).toMatch(/--dur-2:\s*200ms;/);
    expect(TOKENS).toMatch(/--dur-loop:\s*[0-9.]+m?s;/);
    expect(TOKENS).toMatch(/--dur-spin:\s*[0-9.]+m?s;/);
  });

  it("stops every animation and transition from one global reduced-motion rule", () => {
    const blocks = reducedMotionBlocks(DS);
    expect(blocks).toHaveLength(1);
    const [block] = blocks;
    expect(block).toMatch(/\*,\s*\*::before,\s*\*::after\s*\{/);
    expect(block).toMatch(/animation-duration:\s*0\.01ms\s*!important/);
    expect(block).toMatch(/animation-iteration-count:\s*1\s*!important/);
    expect(block).toMatch(/transition-duration:\s*0\.01ms\s*!important/);
  });

  it("runs every looping animation on the loop or spin token", () => {
    const offenders = [];
    for (const { rel, css } of FILES) {
      for (const m of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
        const body = m[2];
        if (!/infinite/.test(body)) continue;
        if (!/var\(--dur-(loop|spin)[,)]/.test(body)) offenders.push(`${rel} → ${m[1].trim()}`);
      }
    }
    expect(FILES.length).toBeGreaterThan(50);
    expect(offenders).toEqual([]);
  });

  it("never names a global keyframe from a CSS module, where it would be hashed away", () => {
    const offenders = [];
    for (const { rel, css } of FILES) {
      if (!rel.endsWith(".module.css")) continue;
      for (const m of css.matchAll(/animation(-name)?:\s*(ds-[\w-]+)/g)) offenders.push(`${rel} → ${m[2]}`);
    }
    expect(offenders).toEqual([]);
  });
});
