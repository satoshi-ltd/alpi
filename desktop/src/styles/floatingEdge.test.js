import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const read = (file) => readFileSync(join(import.meta.dirname, "..", file), "utf8");
const rule = (css, selector) => css.match(new RegExp(`(?:^|\\n)${selector.replace(".", "\\.")}\\s*\\{([^{}]*)\\}`))[1];

const FLOATING = [
  ["primitives/Modal.module.css", ".modal"],
  ["primitives/BrowseModal.module.css", ".modal"],
  ["primitives/Panels.module.css", ".shell"],
  ["primitives/Dropdown.module.css", ".menu"],
  ["primitives/ContextMenu.module.css", ".root"],
  ["primitives/ModelPicker.module.css", ".modelPickerPop"],
  ["primitives/Notification.module.css", ".toast"],
  ["features/sessions/ManageSessionsModal.module.css", ".modal"],
  ["features/VersionButton.module.css", ".popover"],
  ["features/settings/Settings.module.css", ".popover"],
  ["primitives/AppearancePicker.module.css", ".popover"],
  ["primitives/SearchBar.module.css", ".bar"],
  ["primitives/JumpToLatest.module.css", ".btn"],
  ["features/settings/Usage.module.css", ".tip"],
];

describe("floating surfaces", () => {
  it.each(FLOATING)("%s %s separates from the page with the control-boundary edge", (file, selector) => {
    const body = rule(read(file), selector);
    expect(body).toMatch(/box-shadow:\s*var\(--shadow-edge\)/);
    expect(body).not.toMatch(/box-shadow:\s*var\(--shadow(-sm)?\)/);
  });

  it("keeps the jump button's focus ring on top of the edge", () => {
    expect(read("primitives/JumpToLatest.module.css")).toMatch(/box-shadow:\s*var\(--shadow-edge\),\s*var\(--well-ring\)/);
  });

  it("draws the shared Popover with the edge", () => {
    expect(read("primitives/Popover.jsx")).toMatch(/boxShadow: "var\(--shadow-edge\)"/);
  });

  it("resolves the edge token to a 1 px ring of --edge in every theme block", () => {
    const css = read("styles/tokens.css");
    const values = [...css.matchAll(/--shadow-edge:\s*([^;]+);/g)].map((m) => m[1].trim());
    expect(values.length).toBeGreaterThanOrEqual(3);
    for (const value of values) expect(value).toBe("0 0 0 1px var(--edge)");
  });
});
