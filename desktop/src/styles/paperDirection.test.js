import { readdirSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = join(import.meta.dirname, "..");
const SLATE = /11, ?17, ?23|230, ?237, ?243|#0b1117|#3d4955|#626e7d|#b1bac4|#eef0f2|#f5f6f8|#f1f3f5|#0a0d11|#0c1014|#11151a|#161b22|#e6edf3|#828b97|#484f58|#1c242c/i;

const ROUND = new Set([
  "features/NotificationsModal.module.css .unreadDot",
  "features/ScheduleModal.module.css .dot",
  "features/Sidebar.module.css .bellBadge",
  "features/settings/Settings.module.css .budgetBar",
  "features/settings/Settings.module.css .budgetBarFill",
  "primitives/WaveBars.module.css .bars span",
  "styles/design-system.css .ds-bar, .bar",
  "styles/design-system.css .ds-meter .bar",
]);

const walk = (dir, test) =>
  readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return walk(path, test);
    return test(entry.name) ? [path] : [];
  });

const rules = (css) => {
  const out = [];
  const plain = css.replace(/\/\*[\s\S]*?\*\//g, "");
  for (const m of plain.matchAll(/([^{}]+)\{([^{}]*)\}/g)) out.push([m[1].trim().replace(/\s+/g, " "), m[2]]);
  return out;
};

const layers = (value) => {
  const out = [];
  let depth = 0;
  let start = 0;
  for (let i = 0; i < value.length; i++) {
    if (value[i] === "(") depth++;
    else if (value[i] === ")") depth--;
    else if (value[i] === "," && depth === 0) {
      out.push(value.slice(start, i).trim());
      start = i + 1;
    }
  }
  out.push(value.slice(start).trim());
  return out;
};

const blurred = (layer) => {
  if (layer === "none" || /^var\(--[\w-]+\)$/.test(layer)) return false;
  const lengths = layer.replace(/^inset\s+/, "").match(/^(-?[\d.]+(?:px)?)\s+(-?[\d.]+(?:px)?)(?:\s+(-?[\d.]+(?:px)?))?/);
  if (!lengths) return true;
  return lengths[3] !== undefined && parseFloat(lengths[3]) !== 0;
};

const paperViolations = (file, css) => {
  const found = [];
  if (SLATE.test(css)) found.push(`${file}: slate grey`);
  for (const [selector, body] of rules(css)) {
    const where = `${file} ${selector}`;
    if (/backdrop-filter/.test(body)) found.push(`${where}: backdrop-filter`);
    if (/(?:^|;|\s)filter\s*:[^;]*(blur|drop-shadow)\(/.test(body)) found.push(`${where}: filter blur`);
    for (const m of body.matchAll(/--shadow[\w-]*\s*:\s*([^;]+)/g)) {
      if (layers(m[1].trim()).some(blurred)) found.push(`${where}: blurred shadow token`);
    }
    if (/var\(--r-(sm|md|lg|xl|2xl|3xl)\)/.test(body)) found.push(`${where}: old corner`);
    if (/border-(left|right|top|bottom)\s*:[^;]*var\(--c-/.test(body) || /box-shadow\s*:[^;]*inset\s+-?\d+(\.\d+)?px\s+0\s+0\s+var\(--c-/.test(body)) found.push(`${where}: coloured side stripe`);
    if (/var\(--r-pill\)/.test(body) && !ROUND.has(where)) found.push(`${where}: pill`);
    for (const m of body.matchAll(/border(?:-[a-z]+)*-radius\s*:\s*([^;]+)/g)) {
      if (m[1].split(/\s+/).some((v) => (/^\d+(\.\d+)?px$/.test(v) && parseFloat(v) > 4) || /^[\d.]+r?em$/.test(v) || /^calc\(/.test(v))) found.push(`${where}: literal corner ${m[1].trim()}`);
    }
    for (const m of body.matchAll(/(?:^|;|\s)box-shadow\s*:\s*([^;]+)/g)) {
      if (layers(m[1].trim()).some(blurred)) found.push(`${where}: blurred shadow`);
    }
  }
  return found;
};

const inlineViolations = (file, source) => {
  const found = [];
  if (SLATE.test(source)) found.push(`${file}: slate grey`);
  if (/backdropFilter|WebkitBackdropFilter/.test(source)) found.push(`${file}: backdrop-filter`);
  if (/var\(--r-(sm|md|lg|xl|2xl|3xl|pill)\)/.test(source)) found.push(`${file}: old corner`);
  for (const m of source.matchAll(/borderRadius\s*:\s*(["'`]?)([^,}\n]+)\1/g)) {
    const value = m[2].trim();
    if ((/^\d+(\.\d+)?$/.test(value) && parseFloat(value) > 4) || /calc\(|\/\s*2\b/.test(value)) found.push(`${file}: inline corner ${value}`);
  }
  return found;
};

describe("paper direction scanner", () => {
  it("passes a paper sheet, a seam, an inset ring and an allowed dot", () => {
    const css = `.card { border-radius: var(--r-xs); box-shadow: var(--shadow); }
.well:focus { box-shadow: inset 0 0 0 1px var(--focus-border), 0 0 0 .5px var(--line); }
.footer { box-shadow: inset 0 .5px 0 var(--line); }
.tag { border-radius: var(--r-tag); }
.dot { border-radius: var(--r-pill); }`;
    expect(paperViolations("features/ScheduleModal.module.css", css)).toEqual([]);
  });

  it.each([
    [".a { backdrop-filter: blur(8px); }", "backdrop-filter"],
    [".a { box-shadow: 0 8px 24px rgba(0, 0, 0, .2); }", "blurred shadow"],
    [".a { box-shadow: var(--shadow), 0 2px 6px black; }", "blurred shadow"],
    [".a { border-radius: var(--r-lg); }", "old corner"],
    [".a { border-radius: var(--r-3xl) var(--r-3xl) 0 0; }", "old corner"],
    [".a { border-radius: var(--r-md); }", "old corner"],
    [".a { border-radius: var(--r-pill); }", "pill"],
    [".a { border-left: 2px solid var(--c-danger); }", "coloured side stripe"],
    [".a { box-shadow: inset 3px 0 0 var(--c-warning); }", "coloured side stripe"],
    [".a { border-radius: 12px; }", "literal corner"],
    [".a { color: #626e7d; }", "slate grey"],
    [".a { background: rgba(11, 17, 23, .06); }", "slate grey"],
  ])("flags %s", (css, kind) => {
    expect(paperViolations("primitives/Planted.module.css", css).join("\n")).toContain(kind);
  });

  it("flags an inline backdrop blur, an old corner token and a slate literal in components", () => {
    expect(inlineViolations("a.jsx", 'style={{ backdropFilter: "blur(4px)" }}')).toHaveLength(1);
    expect(inlineViolations("a.jsx", 'style={{ borderRadius: "var(--r-lg)" }}')).toHaveLength(1);
    expect(inlineViolations("a.jsx", 'const ink = "#0b1117";')).toHaveLength(1);
    expect(inlineViolations("a.jsx", "style={{ borderRadius: 999 }}")).toHaveLength(1);
    expect(inlineViolations("a.jsx", 'style={{ borderRadius: "calc(var(--ctrl-md) / 3)" }}')).toHaveLength(1);
    expect(inlineViolations("a.jsx", "style={{ borderRadius: size / 2 }}")).toHaveLength(1);
    expect(paperViolations("a.css", ".a { filter: drop-shadow(0 2px 4px black); }").join()).toContain("filter blur");
    expect(paperViolations("a.css", ":root { --shadow-lg: 0 8px 24px black; }").join()).toContain("blurred shadow token");
    expect(paperViolations("a.css", ".a { border-radius: 1em; }").join()).toContain("literal corner");
  });
});

describe("the paper window", () => {
  it("leaves no blur, blurred shadow, old corner, stray pill or slate grey in any stylesheet", () => {
    const found = walk(SRC, (name) => name.endsWith(".css")).flatMap((path) => paperViolations(relative(SRC, path), readFileSync(path, "utf8")));
    expect(found).toEqual([]);
  });

  it("keeps every round selector it allows on the page", () => {
    const present = new Set(walk(SRC, (name) => name.endsWith(".css")).flatMap((path) => rules(readFileSync(path, "utf8")).map(([selector]) => `${relative(SRC, path)} ${selector}`)));
    for (const allowed of ROUND) expect(present.has(allowed), allowed).toBe(true);
  });

  it("leaves no blur, old corner or slate grey in any component", () => {
    const found = walk(SRC, (name) => /\.jsx?$/.test(name) && !/\.test\.jsx?$/.test(name)).flatMap((path) => inlineViolations(relative(SRC, path), readFileSync(path, "utf8")));
    expect(found).toEqual([]);
  });
});
