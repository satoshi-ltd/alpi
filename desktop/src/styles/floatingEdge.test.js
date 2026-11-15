import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const read = (file) => readFileSync(join(import.meta.dirname, "..", file), "utf8");
const rule = (css, selector) => css.match(new RegExp(`(?:^|\\n)${selector.replace(".", "\\.")}\\s*\\{([^{}]*)\\}`))[1];

const SMALL = [
  ["primitives/ContextMenu.module.css", ".root"],
  ["primitives/Dropdown.module.css", ".menu"],
  ["primitives/ModelPicker.module.css", ".modelPickerPop"],
  ["primitives/Notification.module.css", ".toast"],
  ["primitives/Composer.module.css", ".mentionPopover"],
  ["features/VersionButton.module.css", ".popover"],
  ["features/settings/Settings.module.css", ".popover"],
  ["primitives/AppearancePicker.module.css", ".popover"],
  ["primitives/SearchBar.module.css", ".bar"],
  ["primitives/JumpToLatest.module.css", ".btn"],
  ["features/settings/Usage.module.css", ".tip"],
];

const LARGE = [
  ["primitives/Modal.module.css", ".modal"],
  ["primitives/BrowseModal.module.css", ".modal"],
  ["primitives/Panels.module.css", ".shell"],
  ["features/sessions/ManageSessionsModal.module.css", ".modal"],
];

describe("floating surfaces", () => {
  it.each(SMALL)("%s %s floats on the float shadow with no border", (file, selector) => {
    const body = rule(read(file), selector);
    expect(body).toMatch(/box-shadow:\s*var\(--shadow-(edge-sm|float)\)/);
    expect(body).not.toMatch(/(?:^|\n)\s*border:\s*\.?0?\.5px/);
    expect(body).not.toMatch(/box-shadow:\s*var\(--shadow(-sm)?\)/);
  });

  it.each(LARGE)("%s %s floats on the float shadow with no border", (file, selector) => {
    const body = rule(read(file), selector);
    expect(body).toMatch(/box-shadow:\s*var\(--shadow-edge-lg\)/);
    expect(body).not.toMatch(/(?:^|\n)\s*border:\s*0?\.5px/);
  });

  it("focuses the jump button with the system ring outside its edge", () => {
    expect(read("primitives/JumpToLatest.module.css")).toMatch(/\.btn:focus-visible \{\s*outline: var\(--focus-outline\);\s*outline-offset: var\(--focus-outline-offset\);/);
  });

  it("draws the tooltip as one ink fill at the xs radius with no edge", () => {
    const body = rule(read("styles/design-system.css"), ".ds-tip-body");
    expect(body).toMatch(/background:\s*var\(--ink\)/);
    expect(body).toMatch(/border-radius:\s*var\(--r-xs\)/);
    expect(body).not.toMatch(/box-shadow|border:/);
  });

  it("draws the shared Popover with the small ring and no border", () => {
    const source = read("primitives/Popover.jsx");
    expect(source).toMatch(/: "var\(--shadow-edge-sm\)"/);
    expect(source).not.toMatch(/border: "\.5px/);
  });

  it("rings the Sessions and Tasks popovers and searchable dropdown menus with the large tier", () => {
    expect(read("primitives/Popover.jsx")).toMatch(/large \? "var\(--shadow-edge-lg\)"/);
    expect(read("primitives/SessionsButton.jsx")).toMatch(/<Popover[^\n]* large>/);
    expect(read("primitives/TasksButton.jsx")).toMatch(/<Popover[^\n]* large>/);
    expect(rule(read("primitives/Dropdown.module.css"), ".menuLarge")).toMatch(/box-shadow:\s*var\(--shadow-edge-lg\)/);
    expect(read("primitives/Dropdown.jsx")).toMatch(/searchable \? styles\.menuLarge/);
  });

  it("no longer declares the --shadow-edge alias or uses it", () => {
    expect(read("styles/tokens.css")).not.toMatch(/--shadow-edge:/);
  });

  it("floats every small and large surface on the one float shadow: soft in light, a hairline and a deep shadow in dark", () => {
    const css = read("styles/tokens.css");
    const small = [...css.matchAll(/--shadow-edge-sm:\s*([^;]+);/g)].map((m) => m[1].trim());
    expect(small).toEqual(["var(--shadow-float)"]);
    const large = [...css.matchAll(/--shadow-edge-lg:\s*([^;]+);/g)].map((m) => m[1].trim());
    expect(large).toEqual(["var(--shadow-float)"]);
    const float = [...css.matchAll(/--shadow-float:\s*([^;]+);/g)].map((m) => m[1].trim());
    expect(float).toEqual([
      "0 12px 32px rgba(0, 0, 0, .10), 0 1px 3px rgba(0, 0, 0, .06)",
      "0 0 0 1px rgba(237, 237, 237, .09), 0 16px 40px rgba(0, 0, 0, .55)",
      "0 0 0 1px rgba(237, 237, 237, .09), 0 16px 40px rgba(0, 0, 0, .55)",
    ]);
  });

  it("never stacks a .5 px border on a ring token", () => {
    const css = read("styles/tokens.css");
    expect(css).not.toMatch(/--shadow-edge-(sm|lg):[^;]*\.5px/);
  });
});
