import { readdirSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

import { nestInset, radii, retiredRadii } from "../../../common/tokens.mjs";

const SRC = join(import.meta.dirname, "..");
const SLATE = /11, ?17, ?23|230, ?237, ?243|#0b1117|#3d4955|#626e7d|#b1bac4|#eef0f2|#f5f6f8|#f1f3f5|#0a0d11|#0c1014|#11151a|#161b22|#e6edf3|#828b97|#484f58|#1c242c/i;

const ROUND = new Set([
  "features/settings/Settings.module.css .budgetBar",
  "features/settings/Settings.module.css .budgetBarFill",
  "primitives/BrowseModal.module.css .flag",
  "primitives/WaveBars.module.css .bars span",
  "styles/design-system.css .ds-bar, .bar",
  "styles/design-system.css .ds-meter .bar",
]);

const FLOAT_TOKENS = new Set(["--shadow-float", "--shadow-cell"]);

const RETIRED = new RegExp(`var\\(--r-(${retiredRadii.join("|")})\\)`);
const LIVE = new RegExp(`^var\\(--r-(${Object.keys(radii).join("|")})\\)$`);
const cornerOk = (v) => LIVE.test(v) || v === "0" || v === "50%" || v === "inherit";

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
    for (const m of body.matchAll(/(--shadow[\w-]*)\s*:\s*([^;]+)/g)) {
      if (!FLOAT_TOKENS.has(m[1]) && layers(m[2].trim()).some(blurred)) found.push(`${where}: blurred shadow token`);
    }
    if (RETIRED.test(body)) found.push(`${where}: retired corner`);
    if (/border-(left|right|top|bottom)\s*:[^;]*var\(--c-/.test(body) || /box-shadow\s*:[^;]*inset\s+-?\d+(\.\d+)?px\s+0\s+0\s+var\(--c-/.test(body)) found.push(`${where}: coloured side stripe`);
    for (const m of body.matchAll(/border(?:-[a-z]+)*-radius\s*:\s*([^;]+)/g)) {
      if (!m[1].trim().split(/\s+(?![^(]*\))/).every(cornerOk)) found.push(`${where}: literal corner ${m[1].trim()}`);
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
  if (RETIRED.test(source)) found.push(`${file}: retired corner`);
  for (const m of source.matchAll(/(?:borderRadius\s*:|radius=)\s*(["'`]?)([^,}\n"'`]+)\1/g)) {
    const value = m[2].trim();
    if (/^radius$/.test(value)) continue;
    if (!cornerOk(value) && !/^0$/.test(value) && value !== "50%") found.push(`${file}: inline corner ${value}`);
  }
  return found;
};

describe("paper direction scanner", () => {
  it("passes every live corner, a seam, an inset ring and an allowed dot", () => {
    const css = `.card { border-radius: var(--r-surface); box-shadow: var(--shadow); }
.well:focus { outline: var(--focus-outline); }
.chip { border-radius: var(--r-pill); }
.box { border-radius: var(--r-xs); }
.btn { border-radius: var(--r-control); }
.dialog { border-radius: var(--r-sheet); }
.sheet { border-radius: var(--r-sheet) var(--r-sheet) 0 0; }
.circle { border-radius: 50%; }
.dot { border-radius: var(--r-pill); }`;
    expect(paperViolations("features/ScheduleModal.module.css", css)).toEqual([]);
  });

  it.each(retiredRadii)("flags the retired --r-%s token", (name) => {
    expect(paperViolations("primitives/Planted.module.css", `.a { border-radius: var(--r-${name}); }`).join("\n")).toContain("retired corner");
    expect(inlineViolations("a.jsx", `style={{ borderRadius: "var(--r-${name})" }}`).join("\n")).toContain("retired corner");
  });

  it.each([
    [".a { backdrop-filter: blur(8px); }", "backdrop-filter"],
    [".a { box-shadow: 0 8px 24px rgba(0, 0, 0, .2); }", "blurred shadow"],
    [".a { box-shadow: var(--shadow), 0 2px 6px black; }", "blurred shadow"],
    [".a { border-left: 2px solid var(--c-danger); }", "coloured side stripe"],
    [".a { box-shadow: inset 3px 0 0 var(--c-warning); }", "coloured side stripe"],
    [".a { border-radius: 12px; }", "literal corner"],
    [".a { border-radius: 4px; }", "literal corner"],
    [".a { border-radius: 2px; }", "literal corner"],
    [".a { border-radius: 1em; }", "literal corner"],
    [".a { border-radius: calc(var(--r-control) - 4px); }", "literal corner"],
    [".a { color: #626e7d; }", "slate grey"],
    [".a { background: rgba(11, 17, 23, .06); }", "slate grey"],
  ])("flags %s", (css, kind) => {
    expect(paperViolations("primitives/Planted.module.css", css).join("\n")).toContain(kind);
  });

  it("flags an inline backdrop blur, a literal corner and a slate literal in components", () => {
    expect(inlineViolations("a.jsx", 'style={{ backdropFilter: "blur(4px)" }}')).toHaveLength(1);
    expect(inlineViolations("a.jsx", 'const ink = "#0b1117";')).toHaveLength(1);
    expect(inlineViolations("a.jsx", "style={{ borderRadius: 999 }}")).toHaveLength(1);
    expect(inlineViolations("a.jsx", "style={{ borderRadius: 4 }}")).toHaveLength(1);
    expect(inlineViolations("a.jsx", 'style={{ borderRadius: "calc(var(--ctl-32) / 3)" }}')).toHaveLength(1);
    expect(inlineViolations("a.jsx", "style={{ borderRadius: size / 2 }}")).toHaveLength(1);
    expect(inlineViolations("a.jsx", '<Skeleton radius="2px" />')).toHaveLength(1);
    expect(inlineViolations("a.jsx", '<Skeleton radius="var(--r-xs)" />')).toEqual([]);
    expect(inlineViolations("a.jsx", 'style={{ borderRadius: "var(--r-pill)" }}')).toEqual([]);
    expect(inlineViolations("a.jsx", 'style={{ borderRadius: "var(--r-control)" }}')).toEqual([]);
    expect(paperViolations("a.css", ".a { filter: drop-shadow(0 2px 4px black); }").join()).toContain("filter blur");
    expect(paperViolations("a.css", ":root { --shadow-lg: 0 8px 24px black; }").join()).toContain("blurred shadow token");
    expect(paperViolations("a.css", ":root { --shadow-float: 0 12px 32px black; }")).toEqual([]);
  });
});

describe("the radius scale", () => {
  it("declares the five live radii in tokens.css and nothing retired", () => {
    const tokens = readFileSync(join(SRC, "styles/tokens.css"), "utf8");
    for (const [name, value] of Object.entries(radii)) expect(tokens).toMatch(new RegExp(`--r-${name}:\\s*${value}px;`));
    expect([...tokens.matchAll(/--r-([\w-]+):/g)].map((m) => m[1]).sort()).toEqual(Object.keys(radii).sort());
    expect(radii).toEqual({ xs: 6, control: 12, surface: 20, sheet: 28, pill: 999 });
  });

  const body = (file, selector) => {
    const found = rules(readFileSync(join(SRC, file), "utf8")).find(([s]) => s === selector);
    expect(found, `${file} ${selector}`).toBeDefined();
    return found[1];
  };
  const radius = (b) => b.match(/border-radius:\s*var\(--r-(\w+)\)/)?.[1];
  const inset = (b) => b.match(/padding:\s*var\(--nest-inset\)/) ? nestInset : null;

  it.each([
    ["context menu → item", ["primitives/ContextMenu.module.css", ".root"], ["primitives/ContextMenu.module.css", ".root"], ["primitives/Menu.module.css", ".row"]],
    ["dropdown list → item", ["primitives/Dropdown.module.css", ".menu"], ["primitives/Dropdown.module.css", ".list"], ["primitives/Menu.module.css", ".row"]],
    ["model picker → option", ["primitives/ModelPicker.module.css", ".modelPickerPop"], ["primitives/ModelPicker.module.css", ".modelPickerList"], ["primitives/ModelPicker.module.css", ".modelPickerOption"]],
    ["mention popover → item", ["primitives/Composer.module.css", ".mentionPopover"], ["primitives/Composer.module.css", ".mentionPopover"], ["primitives/Composer.module.css", ".mentionItem"]],
  ])("nests the %s pair concentrically: child = parent − inset", (_, outer, padded, inner) => {
    const parent = radii[radius(body(...outer))];
    const gap = inset(body(...padded));
    const child = radii[radius(body(...inner))];
    expect(gap).toBe(8);
    expect(parent - gap).toBe(child);
  });

  it("nests the segmented cells as pills inside a pill track", () => {
    expect(radius(body("styles/design-system.css", ".ds-seg"))).toBe("pill");
    expect(radius(body("styles/design-system.css", ".ds-seg > button"))).toBe("pill");
  });

  it("keeps every banner square", () => {
    expect(body("styles/design-system.css", ".banner")).not.toMatch(/border-radius/);
    expect(body("primitives/AlertBanner.module.css", ".banner")).not.toMatch(/border-radius/);
    expect(readFileSync(join(SRC, "primitives/Banner.jsx"), "utf8")).not.toMatch(/borderRadius|r-(xs|chip|control|surface|sheet)/);
  });
});

describe("the paper window", () => {
  it("leaves no blur, blurred shadow outside the float tokens, retired or literal corner or slate grey in any stylesheet", () => {
    const found = walk(SRC, (name) => name.endsWith(".css")).flatMap((path) => paperViolations(relative(SRC, path), readFileSync(path, "utf8")));
    expect(found).toEqual([]);
  });

  it("keeps every round selector it allows on the page", () => {
    const present = new Set(walk(SRC, (name) => name.endsWith(".css")).flatMap((path) => rules(readFileSync(path, "utf8")).map(([selector]) => `${relative(SRC, path)} ${selector}`)));
    for (const allowed of ROUND) expect(present.has(allowed), allowed).toBe(true);
  });

  it("leaves no blur, retired or literal corner or slate grey in any component", () => {
    const found = walk(SRC, (name) => /\.jsx?$/.test(name) && !/\.test\.jsx?$/.test(name)).flatMap((path) => inlineViolations(relative(SRC, path), readFileSync(path, "utf8")));
    expect(found).toEqual([]);
  });
});
