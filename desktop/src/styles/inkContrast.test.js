import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = join(import.meta.dirname, "..");

const DECORATIVE_GLYPHS = {
  "primitives/BootSplash.module.css": [".glyph"],
  "primitives/ErrorBoundary.module.css": [".mark"],
  "primitives/EmptyState.module.css": [".hash"],
  "pages/ChatPane.module.css": [".emptyHash"],
  "styles/design-system.css": [".ds-chat-header .title-row .ds-hash, .hash"],
};

function walk(dir, hit, out = []) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, hit, out);
    else if (hit(name)) out.push(p);
  }
  return out;
}

export function ink4InlineColors(code) {
  const out = [];
  const patterns = [/\bcolor\s*:\s*[^,}\n]*var\(--ink-4\)/g, /\bcolor=\{?\s*["'`][^"'`]*var\(--ink-4\)/g];
  for (const re of patterns) {
    for (const m of code.matchAll(re)) out.push(code.slice(0, m.index).split("\n").length);
  }
  return out.sort((a, b) => a - b);
}

function ink4TextSelectors(css) {
  const clean = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const out = [];
  for (const m of clean.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    if (/(^|[;\s{])color:\s*var\(--ink-4\)/.test(m[2])) {
      out.push(m[1].trim().replace(/\s+/g, " "));
    }
  }
  return out;
}

const FILES = walk(SRC, (n) => n.endsWith(".css"));
const SCRIPTS = walk(SRC, (n) => /\.jsx?$/.test(n) && !n.includes(".test."));

describe("readable text never uses --ink-4", () => {
  it("reads the stylesheets at all, so a path mistake cannot fake a pass", () => {
    expect(FILES.length).toBeGreaterThan(50);
  });

  it("finds the declaration inside nested rules and ignores border and background colours", () => {
    const sample = `
      .a { border-color: var(--ink-4); background-color: var(--ink-4); }
      @media (min-width: 1px) { .b .c { font-size: 1px; color: var(--ink-4); } }
      .d{color:var(--ink-4)}
    `;
    expect(ink4TextSelectors(sample)).toEqual([".b .c", ".d"]);
  });

  it("keeps --ink-4 for decorative glyphs only", () => {
    const offenders = [];
    for (const path of FILES) {
      const rel = relative(SRC, path);
      const allowed = DECORATIVE_GLYPHS[rel] ?? [];
      for (const selector of ink4TextSelectors(readFileSync(path, "utf8"))) {
        if (!allowed.includes(selector)) offenders.push(`${rel} → ${selector}`);
      }
    }
    expect(offenders).toEqual([]);
  });

  it("names only allow-listed glyphs that still exist", () => {
    const stale = [];
    for (const [rel, selectors] of Object.entries(DECORATIVE_GLYPHS)) {
      const found = ink4TextSelectors(readFileSync(join(SRC, rel), "utf8"));
      for (const s of selectors) if (!found.includes(s)) stale.push(`${rel} → ${s}`);
    }
    expect(stale).toEqual([]);
  });

  it("finds inline text colours in scripts but not borders or backgrounds", () => {
    const sample = [
      'style={{ color: accent || "var(--ink-4)" }}',
      'style={{ border: "1px solid var(--ink-4)", backgroundColor: "var(--ink-4)" }}',
      '<Icon color="var(--ink-4)" />',
    ].join("\n");
    expect(ink4InlineColors(sample)).toEqual([1, 3]);
  });

  it("keeps --ink-4 out of inline text colours in components", () => {
    expect(SCRIPTS.length).toBeGreaterThan(100);
    const offenders = [];
    for (const path of SCRIPTS) {
      for (const line of ink4InlineColors(readFileSync(path, "utf8"))) offenders.push(`${relative(SRC, path)}:${line}`);
    }
    expect(offenders).toEqual([]);
  });
});
