import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const read = (file) => readFileSync(join(import.meta.dirname, "..", file), "utf8");
const rule = (css, selector) => css.match(new RegExp(`(?:^|\\n)${selector.replace(".", "\\.")}\\s*\\{([^{}]*)\\}`))[1];

const OVERLAYS = [
  ["features/VersionButton.module.css", ".popover"],
  ["features/settings/Settings.module.css", ".popover"],
  ["features/settings/Usage.module.css", ".tip"],
  ["primitives/Composer.module.css", ".mentionPopover"],
  ["primitives/AppearancePicker.module.css", ".popover"],
  ["primitives/SearchBar.module.css", ".bar"],
  ["primitives/ContextMenu.module.css", ".root"],
  ["primitives/Dropdown.module.css", ".menu"],
  ["primitives/ModelPicker.module.css", ".modelPickerPop"],
];

describe("paper surfaces", () => {
  it("keeps every elevation token a seam with no blur and no offset", () => {
    const css = read("styles/tokens.css");
    const values = [...css.matchAll(/--shadow(?:-sm)?:\s*([^;]+);/g)].map((m) => m[1].trim());
    expect(values.length).toBeGreaterThanOrEqual(2);
    for (const value of values) expect(value).toMatch(/^0 0 0 \.5px var\(--line(-2)?\)$/);
  });

  it.each(OVERLAYS)("squares %s %s to the 4 px sheet corner", (file, selector) => {
    expect(rule(read(file), selector)).toMatch(/border-radius:\s*var\(--r-xs\)/);
  });

  it("squares the shared Popover primitive behind every header menu and picker", () => {
    expect(read("primitives/Popover.jsx")).toMatch(/borderRadius: "var\(--r-xs\)"/);
  });

  it("draws the error card as a sheet with no ring", () => {
    const error = rule(read("primitives/ErrorBoundary.module.css"), ".errorCard");
    expect(error).not.toMatch(/border:\s/);
    expect(error).toMatch(/background:\s*var\(--bg-pane\)/);
  });
});

describe("paper buttons", () => {
  const css = read("primitives/Button.module.css");

  it("cuts every button with the 4 px sheet corner", () => {
    expect(rule(css, ".button")).toMatch(/border-radius:\s*var\(--r-xs\)/);
  });

  it("presses by tone, never by moving", () => {
    expect(css).not.toMatch(/translateY|scale\(/);
    expect(rule(css, ".button")).not.toMatch(/transform/);
  });

  it("darkens a pressed primary or danger button with a solid tone", () => {
    expect(css).toMatch(/\.primary:not\(:disabled\):active\s*\{\s*background:\s*color-mix\(in srgb, var\(--ink\) 85%, var\(--bg-pane\)\)/);
    expect(css).toMatch(/\.danger:not\(:disabled\):active\s*\{\s*background:\s*color-mix\(in srgb, var\(--c-danger\) \d+%, black\)/);
  });

  it("squares the icon buttons, action links and error buttons outside the primitive", () => {
    const ds = read("styles/design-system.css");
    for (const selector of [".ds-iconbtn, .iconbtn", ".ds-alink, .alink"]) {
      const body = ds.match(new RegExp(`${selector.replace(/[.]/g, "\\.")}\\s*\\{([^{}]*)\\}`))[1];
      expect(body).toMatch(/border-radius:\s*var\(--r-xs\)/);
    }
    expect(ds).not.toMatch(/(iconbtn|alink):active[^{]*\{[^}]*transform/);
    expect(read("primitives/ErrorBoundary.module.css")).toMatch(/\.primary,\n\.secondary \{[^}]*border-radius:\s*var\(--r-xs\)/);
  });

  it("gives the secondary button a solid step that reads without a border", () => {
    expect(rule(css, ".secondary")).toMatch(/background:\s*var\(--selected\)/);
    expect(css).toMatch(/\.secondary:not\(:disabled\):hover\s*\{\s*background:\s*var\(--line-2\)/);
  });
});

describe("paper fields", () => {
  const FIELDS = [
    ["features/ConnectionSwitcher.module.css", ".payload"],
    ["features/Sidebar.module.css", ".searchRow"],
    ["features/settings/Settings.module.css", ".input"],
    ["features/settings/Settings.module.css", ".railSearch"],
    ["features/ClarificationModal.module.css", ".otherBlock"],
    ["primitives/Composer.module.css", ".body"],
    ["primitives/Dropdown.module.css", ".triggerField"],
    ["primitives/Dropdown.module.css", ".search"],
    ["primitives/EditableSessionTitle.module.css", ".input"],
    ["primitives/ModelPicker.module.css", ".modelPickerTriggerField"],
    ["primitives/Panels.module.css", ".renameInput"],
    ["styles/design-system.css", ".ds-field, .field"],
  ];

  it.each(FIELDS)("makes %s %s a borderless 4 px well", (file, selector) => {
    const body = rule(read(file), selector);
    expect(body).toMatch(/background:\s*var\(--well\)/);
    expect(body).toMatch(/border-radius:\s*var\(--r-xs\)/);
    expect(body).not.toMatch(/border:\s*[.\d]+px solid var\(--line/);
  });

  it("focuses a well by deepening it and ringing it, never with an underline or a halo", () => {
    const tokens = read("styles/tokens.css");
    expect(tokens).toMatch(/--well-ring:\s*inset 0 0 0 1px var\(--focus-border\);/);
    const FOCUS = [
      ["features/settings/Settings.module.css", ".input:focus-visible"],
      ["primitives/Composer.module.css", ".body:has(.input:focus)"],
      ["primitives/Dropdown.module.css", ".triggerField.triggerField.triggerOpen:hover"],
      ["styles/design-system.css", ".ds-field:focus, .field:focus"],
      ["features/ConnectionSwitcher.module.css", ".payload:focus,\n.payload:focus-visible"],
      ["features/InlineRequest.module.css", ".otherInput:focus"],
      ["features/Sidebar.module.css", ".searchRow:focus-within"],
      ["features/ClarificationModal.module.css", ".otherBlock:focus-within"],
    ];
    for (const [file, selector] of FOCUS) {
      const body = read(file).match(new RegExp(`${selector.replace(/[.():,]/g, "\\$&")}\\s*\\{([^{}]*)\\}`))[1];
      expect(body, selector).toMatch(/background:\s*var\(--well-focus\)/);
      expect(body, selector).toMatch(/box-shadow:\s*var\(--well-ring\)/);
      expect(body, selector).not.toMatch(/border-bottom|focus-ring/);
    }
  });
});

describe("one active style for every field", () => {
  it("draws an open dropdown, an expanded picker and a focused field the same way", () => {
    const dropdown = read("primitives/Dropdown.module.css");
    expect(dropdown).toMatch(/\.triggerField\.triggerField\.triggerOpen,[^{]*\{[^}]*background:\s*var\(--well-focus\);[^}]*box-shadow:\s*var\(--well-ring\)/);
    expect(read("primitives/ModelPicker.module.css")).toMatch(/\.modelPickerTriggerField\.modelPickerTriggerField\[aria-expanded="true"\]:not\(:disabled\):active\s*\{[^}]*outline:\s*none;[^}]*background:\s*var\(--well-focus\);[^}]*box-shadow:\s*var\(--well-ring\)/);
    expect(read("styles/design-system.css")).toMatch(/\.selectish\[aria-expanded="true"\]\s*\{[^}]*background:\s*var\(--well-focus\);[^}]*box-shadow:\s*var\(--well-ring\)/);
  });

  it("leaves the 4 px halo nowhere", () => {
    for (const file of ["primitives/Dropdown.module.css", "primitives/ModelPicker.module.css", "styles/design-system.css", "features/ConnectionSwitcher.module.css", "features/settings/Settings.module.css", "primitives/JumpToLatest.module.css", "primitives/Composer.module.css"]) {
      expect(read(file), file).not.toMatch(/var\(--focus-ring\)|0 0 0 4px color-mix/);
    }
  });
});

describe("the active field style outranks the button and global focus rules", () => {
  const specificity = (selector) => {
    const plain = selector.replace(/:not\(([^)]*)\)/g, " $1");
    const classes = (plain.match(/\.[\w-]+|\[[^\]]+\]|:(?!:)[\w-]+/g) || []).length;
    const tags = (plain.replace(/\.[\w-]+|\[[^\]]+\]|:[\w-]+/g, " ").match(/\b[a-z]+\b/g) || []).length;
    return classes * 100 + tags;
  };

  it("beats the ghost button hover and the global button focus radius", () => {
    const ghostHover = specificity(".ghost:not(:disabled):hover");
    const globalFocus = specificity("button:focus-visible");
    for (const selector of ['.modelPickerTriggerField.modelPickerTriggerField[aria-expanded="true"]:not(:disabled):hover', ".triggerField.triggerField.triggerOpen:hover", ".triggerField.triggerField:focus-visible"]) {
      expect(specificity(selector), selector).toBeGreaterThanOrEqual(ghostHover);
      expect(specificity(selector), selector).toBeGreaterThan(globalFocus);
    }
    for (const file of ["primitives/ModelPicker.module.css", "primitives/Dropdown.module.css"]) {
      expect(read(file), file).toMatch(/background:\s*var\(--well-focus\);[^}]*box-shadow:\s*var\(--well-ring\)/);
      expect(read(file).match(/border-radius:\s*var\(--r-xs\);\s*background:\s*var\(--well-focus\)/), file).not.toBeNull();
    }
  });
});

describe("paper dialogs", () => {
  it("fades the window towards the ground instead of darkening it", () => {
    expect(read("styles/tokens.css")).toMatch(/--veil:\s*color-mix\(in srgb, var\(--bg\) 72%, transparent\);/);
    for (const [file, selector] of [["primitives/Modal.module.css", ".backdrop"], ["primitives/BrowseModal.module.css", ".backdrop"], ["features/sessions/ManageSessionsModal.module.css", ".backdrop"], ["primitives/Panels.module.css", ".scrim"]]) {
      expect(rule(read(file), selector), file).toMatch(/background:\s*var\(--veil\)/);
    }
  });

  it.each([["primitives/Modal.module.css", ".modal"], ["primitives/BrowseModal.module.css", ".modal"], ["features/sessions/ManageSessionsModal.module.css", ".modal"], ["primitives/Panels.module.css", ".shell"]])("cuts %s %s as a 4 px sheet", (file, selector) => {
    expect(rule(read(file), selector)).toMatch(/border-radius:\s*var\(--r-xs\)/);
  });

  it("sets the dialog actions on a footer band one tone down that spans the sheet", () => {
    const css = read("primitives/Modal.module.css");
    expect(css).toMatch(/\.content \[data-dialog-footer\]\s*\{[^}]*margin:\s*var\(--space-6\) calc\(-1 \* var\(--space-9\)\) 0;[^}]*background:\s*var\(--bg-side\)/);
    expect(read("primitives/DialogFooter.jsx")).toMatch(/data-dialog-footer/);
  });
});

describe("paper selection", () => {
  it("draws the selected sidebar row as the pane's own sheet, square and edge to edge", () => {
    const ds = read("styles/design-system.css");
    expect(ds).toMatch(/\.ds-sb-row\[data-sel\], \.sb-row\[data-sel\] \{[^}]*margin: 0 calc\(-1 \* var\(--sb-bleed, 0px\)\);[^}]*border-radius: 0;/);
    expect(rule(read("features/Sidebar.module.css"), ".inner")).toMatch(/--sb-bleed:\s*var\(--space-5\)/);
    expect(ds).toMatch(/\.ds-sb-row:hover, \.sb-row:hover \{ background: color-mix\(in srgb, var\(--bg-pane\) 50%, transparent\); \}/);
    const row = read("primitives/SidebarRow.jsx");
    expect(row).toMatch(/\? "var\(--bg-pane\)"/);
    expect(row).toMatch(/data-sel=\{sel \|\| undefined\}/);
  });

  it("cuts chips and status pills as 2 px tags", () => {
    expect(read("styles/tokens.css")).toMatch(/--r-tag:\s*2px;/);
    expect(rule(read("primitives/Chip.module.css"), ".chip")).toMatch(/border-radius:\s*var\(--r-tag\)/);
    expect(read("primitives/StatusPill.module.css")).toMatch(/border-radius:\s*var\(--r-tag\)/);
  });
});

describe("paper headers", () => {
  it("ends every chat, settings and workgroup header on its seam, with no accent stripe", () => {
    expect(read("styles/design-system.css")).not.toMatch(/\.stripe\b/);
    for (const file of ["primitives/ChatHeader.jsx", "primitives/SettingsHero.jsx", "pages/WorkgroupsView.jsx"]) {
      expect(read(file), file).not.toMatch(/className="stripe"/);
    }
  });

  it("lets the workgroup loading bar run the whole seam instead of the reading column", () => {
    expect(read("pages/WorkgroupView.module.css")).toMatch(/\.body > :global\(\.refresh-bar\) \{\s*max-width: none;\s*margin: 0;\s*\}/);
  });
});

describe("paper bubbles", () => {
  it("draws your message as a neutral 4 px sheet, never in the profile's colour", () => {
    expect(rule(read("primitives/ProfileMessage.module.css"), ".userBubble")).toMatch(/border-radius:\s*var\(--r-xs\);\s*background:\s*var\(--selected\)/);
    expect(read("primitives/ProfileMessage.jsx")).not.toMatch(/color-mix|accent/);
    expect(rule(read("primitives/MessageBubble.module.css"), ".bubble")).toMatch(/border-radius:\s*var\(--r-xs\)/);
    expect(rule(read("primitives/Message.module.css"), ".bubble")).not.toMatch(/box-shadow/);
    expect(read("primitives/MarkerCard.module.css")).not.toMatch(/r-2xl/);
    expect(rule(read("pages/ChatSkeletons.module.css"), ".userBubble")).toMatch(/border-radius:\s*var\(--r-xs\)/);
  });
});

describe("paper toasts", () => {
  it("draws a notice as a flat 4 px card with one seam", () => {
    const toast = rule(read("primitives/Notification.module.css"), ".toast");
    expect(toast).toMatch(/border-radius:\s*var\(--r-xs\)/);
    expect(toast).toMatch(/box-shadow:\s*var\(--shadow\)/);
    expect(toast).toMatch(/border:\s*0;/);
  });
});
