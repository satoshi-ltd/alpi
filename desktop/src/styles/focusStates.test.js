import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = join(import.meta.dirname, "..");
const walk = (dir) =>
  readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? walk(path) : [path];
  });
const SHEETS = walk(SRC).filter((p) => p.endsWith(".css") && !p.endsWith("tokens.css"));
const read = (file) => readFileSync(join(SRC, file), "utf8");
const DS = read("styles/design-system.css");
const rules = (css) => [...css.matchAll(/([^{}]*)\{([^{}]*)\}/g)].map((m) => ({ selector: m[1].trim().split("\n").pop().trim(), body: m[2], all: m[1].trim() }));
const find = (css, selector) => rules(css).find((r) => r.all.split(",").map((s) => s.trim()).includes(selector))?.body ?? "";

describe("focus", () => {
  it("draws one :focus-visible rule from the focus tokens at primitive level", () => {
    const body = rules(DS).find((r) => r.all === ":focus-visible")?.body;
    expect(body).toMatch(/outline:\s*var\(--focus-outline\)/);
    expect(body).toMatch(/outline-offset:\s*var\(--focus-outline-offset\)/);
    expect(DS.match(/(?<![\w-]):focus-visible\s*\{/g)).toHaveLength(1);
  });

  it("repeats no literal outline recipe anywhere", () => {
    const offenders = SHEETS.filter((f) => /outline:\s*\d+px solid/.test(readFileSync(f, "utf8"))).map((f) => relative(SRC, f));
    expect(offenders).toEqual([]);
  });

  it("replaces every removed focus outline with a ring or a fill", () => {
    const offenders = SHEETS.flatMap((file) =>
      rules(readFileSync(file, "utf8"))
        .filter(({ all, body }) => /:focus-visible/.test(all) && !/:not\(:focus-visible\)/.test(all) && /outline:\s*(none|0)\b/.test(body) && !/box-shadow|background|border-color/.test(body))
        .map(({ all }) => `${relative(SRC, file)} ${all}`),
    );
    expect(offenders).toEqual([]);
  });

  it("keeps outline-less :focus resets only beside the shared rule", () => {
    expect(rules(DS).filter((r) => r.all === ":focus")).toHaveLength(1);
  });

  it("insets the focus outline on rows that sit inside a clipping scroller", () => {
    for (const [file, selector] of [["features/ToolSteps.module.css", ".head:focus-visible"], ["features/ToolSteps.module.css", ".bucket:focus-visible"], ["primitives/Reasoning.module.css", ".row:focus-visible"]]) {
      expect(find(read(file), selector), selector).toMatch(/outline-offset:\s*calc\(var\(--focus-outline-offset\) \* -1\)/);
    }
  });

  it("insets the focus ring on menu, dropdown, context menu and sidebar rows that sit inside a clipping surface", () => {
    const inset = /outline-offset:\s*calc\(var\(--focus-outline-offset\) \* -1\)/;
    const ruleFor = (css, selector) => rules(css).find((r) => r.all.split(",").map((x) => x.trim()).includes(selector) && /outline-offset/.test(r.body));
    expect(ruleFor(read("primitives/Menu.module.css"), ".row:focus-visible")?.body).toMatch(inset);
    expect(ruleFor(DS, ".ds-sb-row:focus-visible")?.body).toMatch(inset);
    expect(ruleFor(DS, ".sb-row:focus-visible")?.body).toMatch(inset);
    expect(read("primitives/Dropdown.jsx")).toMatch(/menuRowClass\(/);
    expect(read("primitives/ContextMenu.jsx")).toMatch(/menuRowClass\(/);
  });

  it("keeps the chip dot on the dot scale and hairline gaps on the micro tokens", () => {
    expect(find(read("primitives/Chip.module.css"), ".dot")).toMatch(/width:\s*var\(--dot-md\)/);
    for (const [file, selector, pattern] of [
      ["features/settings/Settings.module.css", '.checkboxRow input[type="checkbox"]', /margin-top:\s*var\(--space-snug\)/],
      ["primitives/TasksButton.module.css", ".phaseBody", /gap:\s*var\(--space-snug\)/],
      ["features/VersionButton.module.css", ".trigger", /padding:\s*0 calc\(\(var\(--ctl-24\) - var\(--icon-sm\)\) \/ 2\) 0 0/],
      ["features/NotificationBody.module.css", ".factLabel", /padding-top:\s*var\(--space-tight\)/],
      ["primitives/AppearancePicker.module.css", ".previewText", /gap:\s*var\(--space-tight\)/],
    ]) expect(find(read(file), selector), `${file} ${selector}`).toMatch(pattern);
  });
});

describe("state matrix", () => {
  it("gives the ghost button hover, active and disabled states", () => {
    const css = read("primitives/Button.module.css");
    expect(css).toMatch(/\.ghost:not\(:disabled\):hover/);
    expect(css).toMatch(/\.ghost:not\(:disabled\):active/);
    expect(find(css, ".button:disabled")).toMatch(/opacity:\s*var\(--alpha-disabled\)/);
  });

  it.each([".ds-iconbtn", ".ds-alink", ".ds-sb-row"])("gives %s an :active fill", (selector) => {
    expect(DS).toMatch(new RegExp(`\\${selector}:active[^{]*\\{\\s*background:`));
  });

  it("gives menu rows hover, active and disabled states", () => {
    const css = read("primitives/Menu.module.css");
    expect(css).toMatch(/\.row:not\(:disabled\):hover/);
    expect(css).toMatch(/\.row:not\(:disabled\):active\s*\{\s*background:\s*var\(--selected\)/);
    expect(find(css, ".row:disabled")).toMatch(/opacity:\s*var\(--alpha-disabled\)/);
  });

  it("gives the field hover, active, focus and disabled states", () => {
    expect(DS).toMatch(/\.ds-field:not\(:disabled\):hover/);
    expect(DS).toMatch(/\.ds-field:not\(:disabled\):active/);
    expect(find(DS, ".ds-field:focus")).toMatch(/box-shadow:\s*var\(--well-ring\)/);
    expect(find(DS, ".ds-field:disabled")).toMatch(/opacity:\s*var\(--alpha-disabled\)/);
  });
});

describe("motion", () => {
  it("opens floats on the enter duration and ease", () => {
    for (const name of ["anim-pop", "anim-fade", "anim-overlay", "anim-dialog"]) {
      expect(find(DS, `.${name}`), name).toMatch(/var\(--dur-enter\) var\(--ease-enter\)/);
    }
  });

  it("closes the modal and its backdrop on the exit duration and ease", () => {
    const css = read("primitives/Modal.module.css");
    expect(find(css, ".backdropClosing")).toMatch(/var\(--dur-exit\) var\(--ease-exit\)/);
    expect(find(css, ".modalClosing")).toMatch(/var\(--dur-exit\) var\(--ease-exit\)/);
  });

  it("fades floats in and out on opacity alone, with no scale on either side", () => {
    for (const name of ["ds-pop-in", "ds-dialog-in", "ds-notif-in", "ds-notif-out"]) {
      const body = DS.match(new RegExp(`@keyframes ${name}\\s*\\{([^@]*?)\\}\\s*(?=@|\\n\\.)`))?.[1] ?? DS.match(new RegExp(`@keyframes ${name}[^\\n]*`))[0];
      expect(body, name).not.toMatch(/transform|scale/);
    }
    expect(read("primitives/Modal.module.css")).not.toMatch(/scale\(/);
    expect(read("primitives/Notification.jsx")).toMatch(/ds-notif-out var\(--dur-exit\) var\(--ease-exit\)/);
    expect(read("primitives/Notification.jsx")).toMatch(/ds-notif-in var\(--dur-enter\) var\(--ease-enter\)/);
  });

  it("stops pulse, skeleton and spin loops under reduced motion from one global block", () => {
    const block = DS.match(/@media \(prefers-reduced-motion: reduce\)\s*\{([\s\S]*?)\n\}/)[1];
    expect(block).toMatch(/animation-iteration-count:\s*1\s*!important/);
    expect(block).toMatch(/animation-duration:\s*0\.01ms\s*!important/);
  });
});
