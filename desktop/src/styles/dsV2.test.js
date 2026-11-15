import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

import { fieldFocus, focusRing, palettes, radii, stateFills, surfaces, typeFloor, typeLadder } from "../../../common/tokens.mjs";

const SRC = join(import.meta.dirname, "..");
const TOKENS = readFileSync(join(import.meta.dirname, "tokens.css"), "utf8");

function cssFiles(dir = SRC) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return cssFiles(path);
    return name.endsWith(".css") ? [path] : [];
  });
}

const SHEETS = cssFiles().map((path) => ({ path: relative(SRC, path), css: readFileSync(path, "utf8").replace(/\/\*[\s\S]*?\*\//g, "") }));

function rules(css) {
  return [...css.matchAll(/([^{}]*)\{([^{}]*)\}/g)].map((m) => ({ selector: m[1].trim(), body: m[2] }));
}

function rootVar(name) {
  const m = new RegExp(`--${name}:\\s*([^;]+);`).exec(TOKENS);
  return m ? m[1].trim() : null;
}

function px(value) {
  const v = value.trim();
  let m = /^(\d+(?:\.\d+)?)px$/.exec(v);
  if (m) return Number(m[1]);
  m = /^var\(--([a-z0-9-]+)\)$/.exec(v);
  if (m) {
    const inner = rootVar(m[1]);
    return inner ? px(inner) : null;
  }
  m = /^calc\(var\(--([a-z0-9-]+)\)\s*\*\s*([0-9.]+)\)$/.exec(v);
  if (m) {
    const base = px(`var(--${m[1]})`);
    return base == null ? null : base * Number(m[2]);
  }
  return null;
}

const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
const over = (fg, a, ground) => fg.map((c, i) => c * a + ground[i] * (1 - a));
const lum = (rgb) => {
  const [r, g, b] = rgb.map((v) => {
    const c = v / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const ratio = (a, b) => {
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

describe("DS v2 type", () => {
  it("declares the six-size ladder with a 12 px floor", () => {
    expect(Object.values(typeLadder)).toEqual([12, 14, 15, 16, 20, 28]);
    for (const [role, size] of Object.entries(typeLadder)) expect(rootVar(`text-${role}`)).toBe(`${size}px`);
    expect(typeFloor).toBe(12);
  });

  it("renders no font-size below the floor in any stylesheet", () => {
    const low = [];
    for (const { path, css } of SHEETS) {
      for (const m of css.matchAll(/font-size:\s*([^;]+);/g)) {
        const size = px(m[1]);
        if (size != null && size < typeFloor - 1e-9) low.push(`${path}: ${m[1]}`);
      }
    }
    expect(low).toEqual([]);
  });

  it("sets section labels as 14 px sentence-case sans in ink3, never uppercase", () => {
    expect(rootVar("eyebrow-size")).toBe("14px");
    for (const { path, css } of SHEETS) expect(css, path).not.toMatch(/text-transform:\s*uppercase/);
    const eyebrow = rules(readFileSync(join(import.meta.dirname, "design-system.css"), "utf8")).find((r) => r.selector === ".eyebrow");
    expect(eyebrow.body).toMatch(/font-family:\s*var\(--font-sans\)/);
    expect(eyebrow.body).toMatch(/color:\s*var\(--ink-3\)/);
  });

  it("keeps Geist Mono to machine text: code, paths, commands, ids and model names", () => {
    const MACHINE = /(^|[\s,.])(code|pre|command|cwd|codeblock|codeView|editWrap|detailsTrace|stack|toolName|toolNameLg|params|payload|rowId|detailId|detailName|reqName|treeRow|fileName|typedToken|mono|field-mono|ds-field-mono|ds-hash|hash|richCode|mdCode|mdPre|md-code-copy|md-code-lang|host|emptyModel|modelPickerOptionLabel|pipelineKey|codeChip|recipePipelineName|detailHandle|output|log|kw|emptyHash|name)\b/;
    const prose = [];
    for (const { path, css } of SHEETS) {
      if (path.endsWith("reset.css")) continue;
      for (const { selector, body } of rules(css)) {
        if (/font-family:\s*var\(--font-mono\)/.test(body) && !MACHINE.test(selector)) prose.push(`${path}: ${selector}`);
      }
    }
    expect(prose).toEqual([]);
  });
});

describe("DS v2 shape", () => {
  it("declares the five radii and nothing retired", () => {
    expect(radii).toEqual({ xs: 6, control: 12, surface: 20, sheet: 28, pill: 999 });
    for (const [k, v] of Object.entries(radii)) expect(rootVar(`r-${k}`)).toBe(`${v}px`);
    for (const { path, css } of SHEETS) expect(css, path).not.toMatch(/--r-chip/);
  });

  const radiusOf = (file, selector) => {
    const css = readFileSync(join(SRC, file), "utf8");
    const rule = rules(css).find((r) => r.selector === selector);
    expect(rule, `${file} ${selector}`).toBeTruthy();
    return /border-radius:\s*([^;]+);/.exec(rule.body)[1].trim();
  };

  it.each([
    ["primitives/Button.module.css", ".button", "var(--r-pill)"],
    ["primitives/Chip.module.css", ".chip", "var(--r-pill)"],
    ["styles/design-system.css", ".ds-selectish, .selectish", "var(--r-pill)"],
    ["styles/design-system.css", ".ds-iconbtn, .iconbtn", "var(--r-pill)"],
    ["styles/design-system.css", ".ds-field, .field", "var(--r-control)"],
    ["styles/design-system.css", ".ds-checkbox", "var(--r-xs)"],
    ["styles/design-system.css", ".ds-kbd, .kbd", "var(--r-xs)"],
    ["primitives/ContextMenu.module.css", ".root", "var(--r-surface)"],
    ["primitives/Notification.module.css", ".toast", "var(--r-surface)"],
    ["primitives/MessageBubble.module.css", ".bubble", "var(--r-surface)"],
    ["primitives/Modal.module.css", ".modal", "var(--r-sheet)"],
    ["primitives/Panels.module.css", ".shell", "var(--r-sheet)"],
    ["primitives/Composer.module.css", ".body", "var(--r-sheet)"],
  ])("cuts %s %s at %s", (file, selector, radius) => {
    expect(radiusOf(file, selector)).toBe(radius);
  });
});

describe("DS v2 surfaces and states", () => {
  const block = (selector) => {
    const i = TOKENS.indexOf(selector);
    return TOKENS.slice(TOKENS.indexOf("{", i) + 1, TOKENS.indexOf("}", i));
  };
  const modes = { light: block(":root {"), dark: block('[data-mode="dark"] {') };
  const read = (body, name) => new RegExp(`--${name}:\\s*([^;]+);`).exec(body)?.[1].trim();

  it.each(["light", "dark"])("draws the four %s surfaces with the shared values", (mode) => {
    const s = surfaces[mode];
    expect(read(modes[mode], "bg-side")).toBe(s.side);
    expect(read(modes[mode], "bg-pane")).toBe(s.pane);
    expect(read(modes[mode], "fill")).toBe(s.fill);
    expect(read(modes[mode], "raised")).toBe(s.raised);
    expect(read(modes[mode], "bg-elev")).toBe(s.raised);
  });

  it.each(["light", "dark"])("fills hover, selected and pressed at the %s alphas", (mode) => {
    const alpha = (name) => Number(/,\s*([0-9.]+)\)$/.exec(read(modes[mode], name))[1]);
    expect(alpha("hover")).toBe(stateFills[mode].hover);
    expect(alpha("selected")).toBe(stateFills[mode].selected);
    expect(alpha("pressed")).toBe(stateFills[mode].pressed);
  });

  it("fades the state fill in on the fast enter curve and out on the exit curve, pressed instant", () => {
    expect(rootVar("state-in")).toBe("var(--dur-fast) var(--ease-enter)");
    expect(rootVar("state-out")).toBe("var(--dur-exit) var(--ease-exit)");
    const button = rules(readFileSync(join(SRC, "primitives/Button.module.css"), "utf8"));
    expect(button.find((r) => r.selector === ".button").body).toMatch(/transition:[^;]*var\(--state-out\)/);
    expect(button.find((r) => r.selector === ".button:not(:disabled):hover").body).toMatch(/var\(--state-in\)/);
    expect(button.find((r) => r.selector === ".button:not(:disabled):active").body).toMatch(/transition:\s*none/);
    for (const { selector, body } of button) expect(`${selector} ${body}`).not.toMatch(/transform|scale\(/);
  });

  it("turns every transition off under reduced motion", () => {
    const ds = readFileSync(join(import.meta.dirname, "design-system.css"), "utf8");
    expect(ds).toMatch(/@media \(prefers-reduced-motion: reduce\) \{\s*\*, \*::before, \*::after \{[^}]*transition-duration: 0\.01ms !important/);
  });

  it("fades every disabled control to .45", () => {
    expect(rootVar("alpha-disabled")).toBe("0.45");
    const button = readFileSync(join(SRC, "primitives/Button.module.css"), "utf8");
    expect(button).toMatch(/\.button:disabled:not\(\.loading\) \{[^}]*opacity: var\(--alpha-disabled\)/);
    const ds = readFileSync(join(import.meta.dirname, "design-system.css"), "utf8");
    expect(ds).toMatch(/\.ds-iconbtn:disabled[^{]*\{[^}]*opacity: var\(--alpha-disabled\)/);
    expect(ds).toMatch(/\.ds-field:disabled[^{]*\{[^}]*opacity: var\(--alpha-disabled\)/);
  });
});

describe("DS v2 focus", () => {
  it("rings pressables at 2 px of 60 % ink, offset 2, keyboard only", () => {
    expect(focusRing).toEqual({ width: 2, offset: 2, alpha: 0.6 });
    expect(rootVar("focus-outline")).toBe("var(--focus-outline-width) solid color-mix(in srgb, var(--ink) 60%, transparent)");
    const ds = readFileSync(join(import.meta.dirname, "design-system.css"), "utf8");
    expect(ds).toMatch(/:focus \{ outline: 0; \}\s*:focus-visible \{\s*outline: var\(--focus-outline\);\s*outline-offset: var\(--focus-outline-offset\);/);
  });

  it.each(["light", "dark"])("keeps the %s ring at 3:1 or more on side, pane and fill", (mode) => {
    const p = palettes[mode];
    for (const ground of [p.bgSide, p.bgPane, p.fill]) {
      const ring = over(hex(p.ink), focusRing.alpha, hex(ground));
      expect(ratio(ring, hex(ground))).toBeGreaterThanOrEqual(3);
    }
  });

  it("shows field focus as a 1.5 px inset ink3 line, at 3:1 or more on the fill", () => {
    expect(fieldFocus).toEqual({ width: 1.5, ink: "ink3" });
    expect(rootVar("field-focus")).toBe("inset 0 0 0 1.5px var(--ink-3)");
    const ds = readFileSync(join(import.meta.dirname, "design-system.css"), "utf8");
    expect(ds).toMatch(/\.ds-field:focus, \.field:focus \{[^}]*box-shadow: var\(--field-focus\);[^}]*outline: none;/);
    for (const mode of ["light", "dark"]) expect(ratio(hex(palettes[mode].ink3), hex(palettes[mode].fill))).toBeGreaterThanOrEqual(3);
  });

  it("draws no ring around the composer: the caret is its focus", () => {
    const css = rules(readFileSync(join(SRC, "primitives/Composer.module.css"), "utf8"));
    const focused = css.find((r) => r.selector === ".body:has(.input:focus)");
    expect(focused.body).toMatch(/outline: none/);
    expect(focused.body).toMatch(/box-shadow: none/);
  });
});

describe("DS v2 floating surfaces", () => {
  it("floats menus, toasts and dialogs on the raised surface with the soft shadow", () => {
    expect(rootVar("shadow-edge-sm")).toBe("var(--shadow-float)");
    expect(rootVar("shadow-edge-lg")).toBe("var(--shadow-float)");
    const menu = rules(readFileSync(join(SRC, "primitives/ContextMenu.module.css"), "utf8")).find((r) => r.selector === ".root").body;
    expect(menu).toMatch(/background: var\(--raised\)/);
    expect(menu).toMatch(/box-shadow: var\(--shadow-float\)/);
    expect(menu).toMatch(/padding: var\(--nest-inset\)/);
    expect(rootVar("nest-inset")).toBe("8px");
  });

  it("gives menu rows 40 px at 15 px, and the highlighted row the fill without a ring", () => {
    const row = rules(readFileSync(join(SRC, "primitives/Menu.module.css"), "utf8"));
    expect(row.find((r) => r.selector === ".row").body).toMatch(/min-height: var\(--row-h\)/);
    expect(row.find((r) => r.selector === ".row").body).toMatch(/font-size: var\(--text-ui\)/);
    const focus = row.find((r) => r.selector === ".row:focus-visible").body;
    expect(focus).toMatch(/background: var\(--selected\)/);
    expect(focus).toMatch(/outline: none/);
  });
});
