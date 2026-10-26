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
  ["styles/design-system.css", ".ds-tip-body"],
];

const LARGE = [
  ["primitives/Modal.module.css", ".modal"],
  ["primitives/BrowseModal.module.css", ".modal"],
  ["primitives/Panels.module.css", ".shell"],
  ["features/sessions/ManageSessionsModal.module.css", ".modal"],
];

describe("floating surfaces", () => {
  it.each(SMALL)("%s %s rings with the small tier and no border", (file, selector) => {
    const body = rule(read(file), selector);
    expect(body).toMatch(/box-shadow:\s*var\(--shadow-edge-sm\)/);
    expect(body).not.toMatch(/(?:^|\n)\s*border:\s*\.?0?\.5px/);
    expect(body).not.toMatch(/box-shadow:\s*var\(--shadow(-sm)?\)/);
  });

  it.each(LARGE)("%s %s rings with the large tier and no border", (file, selector) => {
    const body = rule(read(file), selector);
    expect(body).toMatch(/box-shadow:\s*var\(--shadow-edge-lg\)/);
    expect(body).not.toMatch(/(?:^|\n)\s*border:\s*0?\.5px/);
  });

  it("keeps the jump button's focus ring on top of the edge", () => {
    expect(read("primitives/JumpToLatest.module.css")).toMatch(/box-shadow:\s*var\(--shadow-edge-sm\),\s*var\(--well-ring\)/);
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

  it("rings small floats with --edge and large floats with ink-4 in light and line-2 in dark", () => {
    const css = read("styles/tokens.css");
    const small = [...css.matchAll(/--shadow-edge-sm:\s*([^;]+);/g)].map((m) => m[1].trim());
    expect(small).toEqual(["0 0 0 1px var(--edge)"]);
    const large = [...css.matchAll(/--shadow-edge-lg:\s*([^;]+);/g)].map((m) => m[1].trim());
    expect(large).toEqual(["0 0 0 1px var(--ink-4)", "0 0 0 1px var(--line-2)", "0 0 0 1px var(--line-2)"]);
  });

  it("never stacks a .5 px border on a ring token", () => {
    const css = read("styles/tokens.css");
    expect(css).not.toMatch(/--shadow-edge-(sm|lg):[^;]*\.5px/);
  });
});
