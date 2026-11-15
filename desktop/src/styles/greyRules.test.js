import { readdirSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = join(import.meta.dirname, "..");
const AUTHORED = new Set(["primitives/Message.module.css .md hr", "styles/design-system.css .alpi-md hr"]);
const CLIPPED_FLOAT = new Set(["tray/TrayApp.module.css .pop"]);

const walk = (dir, test) =>
  readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return walk(path, test);
    return test(entry.name) ? [path] : [];
  });

const rules = (css) => [...css.replace(/\/\*[\s\S]*?\*\//g, "").matchAll(/([^{}]+)\{([^{}]*)\}/g)].map((m) => [m[1].trim().replace(/\s+/g, " "), m[2]]);

const GREY = /var\(--(line|line-2|shadow|shadow-sm)\)/;
const HAIRLINE = /inset\s+-?[.\d]+px\s+0\s+0|inset\s+0\s+-?[.\d]+px\s+0(?!\s+-?[.\d])/;

export const greyRules = (file, css) => {
  const found = [];
  for (const [selector, body] of rules(css)) {
    const where = `${file} ${selector}`;
    for (const m of body.matchAll(/(?:^|;|\s)(border(?:-[a-z]+)*|box-shadow|outline)\s*:\s*([^;]+)/g)) {
      if ((GREY.test(m[2]) || (m[1] === "box-shadow" && HAIRLINE.test(m[2]))) && !AUTHORED.has(where) && !CLIPPED_FLOAT.has(where)) found.push(`${where}: ${m[1]} ${m[2].trim()}`);
    }
    if (/(?:^|;|\s)(width|height)\s*:\s*(1px|\.5px|0\.5px)/.test(body) && /background\s*:\s*var\(--line(-2)?\)/.test(body)) found.push(`${where}: divider`);
  }
  return found;
};

describe("grey rule scanner", () => {
  it.each([
    [".a { border-bottom: .5px solid var(--line); }"],
    [".a { border: 1px solid var(--line-2); }"],
    [".a { box-shadow: inset 0 .5px 0 var(--edge); }"],
    [".a { box-shadow: inset 0 -.5px 0 var(--ink-4); }"],
    [".a { box-shadow: var(--shadow-sm); }"],
    [".a { width: 1px; height: 14px; background: var(--line-2); }"],
  ])("flags %s", (css) => {
    expect(greyRules("primitives/Planted.module.css", css)).toHaveLength(1);
  });

  it("passes a fill, a float edge, the focus ring and an error ring", () => {
    const css = `.card { background: var(--card); }
.pop { box-shadow: var(--shadow-edge-sm); }
.well:focus { outline: var(--focus-outline); }
.well[aria-invalid] { box-shadow: var(--well-error); }
.tag { box-shadow: inset 0 0 0 1px var(--edge); }`;
    expect(greyRules("primitives/Planted.module.css", css)).toEqual([]);
  });
});

describe("planes told apart by tone", () => {
  it("draws no grey rule, hairline or divider in any stylesheet but the markdown rule an author writes", () => {
    const found = walk(SRC, (name) => name.endsWith(".css")).flatMap((path) => greyRules(relative(SRC, path), readFileSync(path, "utf8")));
    expect(found).toEqual([]);
  });

  it("lets only the tray popover, whose transparent window clips any drop shadow, keep a 1 px inset edge as its float edge", () => {
    const css = readFileSync(join(SRC, "tray/TrayApp.module.css"), "utf8");
    const pop = rules(css).find(([s]) => s === ".pop")[1];
    expect(pop).toMatch(/box-shadow:\s*inset 0 0 0 1px var\(--line\);/);
    expect(pop).not.toMatch(/shadow-(edge|float)|0 \d+px \d+px/);
    expect(greyRules("primitives/Planted.module.css", ".pop { box-shadow: inset 0 0 0 1px var(--line); }")).toHaveLength(1);
  });

  it("keeps every authored exception on the page", () => {
    const present = new Set(walk(SRC, (name) => name.endsWith(".css")).flatMap((path) => rules(readFileSync(path, "utf8")).map(([selector]) => `${relative(SRC, path)} ${selector}`)));
    for (const allowed of AUTHORED) expect(present.has(allowed), allowed).toBe(true);
  });

  it("sets the sidebar apart by its tint alone", () => {
    const sidebar = rules(readFileSync(join(SRC, "features/Sidebar.module.css"), "utf8")).find(([s]) => s === ".sidebar")[1];
    expect(sidebar).toMatch(/background:\s*var\(--bg-side\)/);
    expect(sidebar).not.toMatch(/border|box-shadow/);
  });

  it("draws no grey rule inline in any component", () => {
    const found = walk(SRC, (name) => /\.jsx?$/.test(name) && !/\.test\.jsx?$/.test(name)).filter((path) =>
      /(border[A-Za-z]*|boxShadow)\s*:\s*["'`][^"'`]*var\(--(line|line-2|shadow|shadow-sm)\)/.test(readFileSync(path, "utf8")),
    );
    expect(found.map((path) => relative(SRC, path))).toEqual([]);
  });
});
