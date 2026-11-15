import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const read = (file) => readFileSync(join(import.meta.dirname, "..", file), "utf8");
const rule = (css, selector) => css.match(new RegExp(`(?:^|\\n)${selector.replace(/[.()[\]"=:,>*]/g, "\\$&")}\\s*\\{([^{}]*)\\}`))[1];

const FLOATS = [
  ["features/VersionButton.module.css", ".popover"],
  ["features/settings/Settings.module.css", ".popover"],
  ["primitives/Composer.module.css", ".mentionPopover"],
  ["primitives/AppearancePicker.module.css", ".popover"],
  ["primitives/ContextMenu.module.css", ".root"],
  ["primitives/Dropdown.module.css", ".menu"],
  ["primitives/ModelPicker.module.css", ".modelPickerPop"],
  ["tray/TrayApp.module.css", ".pop"],
  ["features/settings/Usage.module.css", ".tip"],
];

describe("paper surfaces", () => {
  it("keeps every elevation token a seam with no blur and no offset", () => {
    const css = read("styles/tokens.css");
    const values = [...css.matchAll(/--shadow(?:-sm)?:\s*([^;]+);/g)].map((m) => m[1].trim());
    expect(values.length).toBeGreaterThanOrEqual(2);
    for (const value of values) expect(value).toMatch(/^0 0 0 \.5px var\(--line(-2)?\)$/);
  });

  it.each(FLOATS)("rounds %s %s at the surface radius", (file, selector) => {
    expect(rule(read(file), selector)).toMatch(/border-radius:\s*var\(--r-surface\)/);
  });

  it("rounds the shared Popover primitive behind every header menu and picker at the surface radius", () => {
    expect(read("primitives/Popover.jsx")).toMatch(/borderRadius: "var\(--r-surface\)"/);
  });

  it("draws the error card as a sheet with no ring", () => {
    const error = rule(read("primitives/ErrorBoundary.module.css"), ".errorCard");
    expect(error).not.toMatch(/border:\s/);
    expect(error).toMatch(/background:\s*var\(--bg-pane\)/);
  });
});

describe("paper buttons", () => {
  const css = read("primitives/Button.module.css");

  it("cuts every button as a pill", () => {
    expect(rule(css, ".button")).toMatch(/border-radius:\s*var\(--r-pill\)/);
  });

  it("presses by tone, never by moving", () => {
    expect(css).not.toMatch(/translateY|scale\(/);
    expect(rule(css, ".button")).not.toMatch(/transform/);
  });

  it("fills the primary with alpi's ink and steps it toward the pane on hover and press", () => {
    expect(rule(css, ".primary")).toMatch(/background:\s*var\(--accent\)/);
    expect(rule(css, ".primary")).toMatch(/color:\s*var\(--bg-pane\)/);
    expect(css).toMatch(/\.primary:not\(:disabled\):hover\s*\{\s*background:\s*var\(--accent-hover\)/);
    expect(css).toMatch(/\.primary:not\(:disabled\):active\s*\{\s*background:\s*var\(--accent-pressed\)/);
    expect(css).toMatch(/\.danger:not\(:disabled\):active\s*\{\s*background:\s*color-mix\(in srgb, var\(--c-danger\) \d+%, black\)/);
  });

  it("rounds the icon buttons, action links and error buttons outside the primitive as pills", () => {
    const ds = read("styles/design-system.css");
    for (const selector of [".ds-iconbtn, .iconbtn", ".ds-alink, .alink"]) {
      expect(rule(ds, selector)).toMatch(/border-radius:\s*var\(--r-pill\)/);
    }
    expect(ds).not.toMatch(/(iconbtn|alink):active[^{]*\{[^}]*transform/);
    expect(read("primitives/ErrorBoundary.module.css")).toMatch(/\.primary,\n\.secondary \{[^}]*border-radius:\s*var\(--r-pill\)/);
  });

  it("lays the secondary on the fill and steps it with the hover and pressed state fills, without a border", () => {
    expect(rule(css, ".secondary")).toMatch(/background:\s*var\(--fill\)/);
    expect(css).toMatch(/\.secondary:not\(:disabled\):hover\s*\{\s*box-shadow:\s*var\(--hover-wash\)/);
    expect(css).toMatch(/\.secondary:not\(:disabled\):active\s*\{\s*box-shadow:\s*var\(--pressed-wash\)/);
    expect(css).toMatch(/\.ghost:not\(:disabled\):active\s*\{\s*background:\s*var\(--pressed\)/);
    expect(css).not.toMatch(/var\(--line(-2)?\)\s*;\s*\}/);
  });
});

describe("paper fields", () => {
  const FIELDS = [
    ["features/ConnectionSwitcher.module.css", ".payload"],
    ["features/Sidebar.module.css", ".searchRow"],
    ["features/settings/Settings.module.css", ".input"],
    ["features/settings/Settings.module.css", ".railSearch"],
    ["features/ClarificationModal.module.css", ".otherBlock"],
    ["primitives/Dropdown.module.css", ".search"],
    ["primitives/EditableSessionTitle.module.css", ".input"],
    ["primitives/Panels.module.css", ".renameInput"],
    ["styles/design-system.css", ".ds-field, .field"],
  ];

  it.each(FIELDS)("makes %s %s a well: a fill at the control radius with no edge", (file, selector) => {
    const body = rule(read(file), selector);
    expect(body).toMatch(/background:\s*var\(--well\)/);
    expect(body).toMatch(/border-radius:\s*var\(--r-control\)/);
    expect(body).not.toMatch(/box-shadow:(?!\s*none)/);
    expect(body).not.toMatch(/border:\s*[.\d]+px solid var\(--(line|edge)/);
  });

  it.each([["primitives/Dropdown.module.css", ".triggerField"], ["primitives/ModelPicker.module.css", ".modelPickerTriggerField"]])("makes %s %s a select: a pill on the fill", (file, selector) => {
    const body = rule(read(file), selector);
    expect(body).toMatch(/background:\s*var\(--fill\)/);
    expect(body).toMatch(/border-radius:\s*var\(--r-pill\)/);
    expect(body).toMatch(/height:\s*var\(--ctl-40\)/);
  });

  it("makes the composer one pill on the fill at the sheet radius with no rule above it", () => {
    const css = read("primitives/Composer.module.css");
    expect(rule(css, ".body")).toMatch(/background:\s*var\(--fill\)/);
    expect(rule(css, ".body")).toMatch(/border-radius:\s*var\(--r-sheet\)/);
    expect(rule(css, ".body")).not.toMatch(/box-shadow:(?!\s*none)/);
    expect(rule(css, ".wrap")).not.toMatch(/border-top/);
  });

  it("draws the well on the fill in both modes, with no edge token left", () => {
    const tokens = read("styles/tokens.css");
    expect(tokens).toMatch(/:root \{[\s\S]*?--well: var\(--card\);/);
    expect([...tokens.matchAll(/--well: var\(--bg-elev\);/g)]).toHaveLength(0);
    expect(tokens).not.toMatch(/--well-edge|--well-ring|--ring-ctrl|--focus-border|--focus-ring:/);
  });

  it("focuses a well with the 1.5 px inset ink3 line, never a ring, a darker fill, an underline or a halo", () => {
    const FOCUS = [
      ["features/settings/Settings.module.css", ".input:focus-visible"],
      ["styles/design-system.css", ".ds-field:focus, .field:focus"],
      ["features/ConnectionSwitcher.module.css", ".payload:focus,\n.payload:focus-visible"],
      ["features/InlineRequest.module.css", ".otherInput:focus"],
      ["features/Sidebar.module.css", ".searchRow:focus-within"],
      ["features/ClarificationModal.module.css", ".otherBlock:focus-within"],
    ];
    for (const [file, selector] of FOCUS) {
      const body = rule(read(file), selector);
      expect(body, selector).toMatch(/box-shadow:\s*var\(--field-focus\)/);
      expect(body, selector).toMatch(/outline:\s*none/);
      expect(body, selector).not.toMatch(/var\(--focus-outline\)|border-bottom/);
    }
  });

  it("errs with a 1.5 px danger line and keeps the fill", () => {
    expect(read("styles/tokens.css")).toMatch(/--well-error:\s*inset 0 0 0 1.5px var\(--c-danger-text\);/);
    expect(read("styles/design-system.css")).toMatch(/\.field\[aria-invalid="true"\]:not\(:disabled\):focus \{\s*box-shadow: var\(--well-error\);/);
  });
});

describe("disabled fields", () => {
  it("turn grey only when disabled, with no edge", () => {
    expect(read("primitives/Composer.module.css")).toMatch(/\.body\[data-disabled="true"\]:not\(\[data-busy\]\)\s*\{[^}]*background:\s*var\(--fill\);/);
    expect(read("styles/design-system.css")).toMatch(/\.ds-field:disabled, \.field:disabled \{[^}]*background:\s*var\(--well-off\);\s*box-shadow:\s*none;/);
    expect(read("features/settings/Settings.module.css")).toMatch(/\.input:disabled,\s*\.textarea:disabled \{[^}]*background:\s*var\(--well-off\);\s*box-shadow:\s*none;/);
    expect(read("primitives/Dropdown.module.css")).toMatch(/\.triggerField\.triggerField:disabled \{[^}]*background:\s*var\(--well-off\);\s*box-shadow:\s*none;/);
  });

  it("keeps a composer white while it is only busy sending", () => {
    expect(read("pages/WorkgroupView.jsx")).toMatch(/busy=\{posting && !paused\}/);
    expect(read("primitives/Composer.jsx")).toMatch(/data-busy=\{busy \|\| undefined\}/);
  });

  it("rings rows and segments with the system outline, drawn inside the row", () => {
    expect(read("features/NotificationsModal.module.css")).toMatch(/\.row:focus-visible \{ outline: var\(--focus-outline\); outline-offset: var\(--focus-inset\); \}/);
    expect(read("styles/tokens.css")).toMatch(/--focus-inset:\s*-2px;/);
    expect(read("styles/design-system.css")).not.toMatch(/\.ds-seg > button:focus-visible/);
  });
});

describe("one active style for every field", () => {
  it("draws an open dropdown, an expanded picker and an open select the same way: the selected fill over the pill", () => {
    expect(read("primitives/Dropdown.module.css")).toMatch(/\.triggerField\.triggerField\.triggerOpen,[^{]*\{[^}]*box-shadow:\s*var\(--selected-wash\);[^}]*outline:\s*none/);
    expect(read("primitives/ModelPicker.module.css")).toMatch(/\.modelPickerTriggerField\.modelPickerTriggerField:not\(:disabled\):active\s*\{[^}]*box-shadow:\s*var\(--selected-wash\);[^}]*outline:\s*none/);
    expect(read("styles/design-system.css")).toMatch(/\.selectish\[aria-expanded="true"\]\s*\{[^}]*box-shadow:\s*var\(--selected-wash\);[^}]*outline:\s*none/);
  });

  it("leaves the 4 px halo nowhere", () => {
    for (const file of ["primitives/Dropdown.module.css", "primitives/ModelPicker.module.css", "styles/design-system.css", "features/ConnectionSwitcher.module.css", "features/settings/Settings.module.css", "primitives/JumpToLatest.module.css", "primitives/Composer.module.css", "primitives/PipelineStages.module.css"]) {
      expect(read(file), file).not.toMatch(/var\(--focus-ring\)|0 0 0 4px color-mix|var\(--focus-border\)/);
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
      expect(read(file).match(/border-radius:\s*var\(--r-pill\);\s*background:\s*var\(--fill\)/), file).not.toBeNull();
    }
  });
});

describe("paper dialogs", () => {
  it("dims the window under a dialog with the veil, darker in dark", () => {
    expect(read("styles/tokens.css")).toMatch(/--veil:\s*rgba\(20, 20, 20, \.22\);/);
    expect(read("styles/tokens.css")).toMatch(/--veil:\s*rgba\(0, 0, 0, \.55\);/);
    for (const [file, selector] of [["primitives/Modal.module.css", ".backdrop"], ["primitives/BrowseModal.module.css", ".backdrop"], ["features/sessions/ManageSessionsModal.module.css", ".backdrop"], ["primitives/Panels.module.css", ".scrim"]]) {
      expect(rule(read(file), selector), file).toMatch(/background:\s*var\(--veil\)/);
    }
  });

  it.each([["primitives/Modal.module.css", ".modal"], ["primitives/BrowseModal.module.css", ".modal"], ["features/sessions/ManageSessionsModal.module.css", ".modal"], ["primitives/Panels.module.css", ".shell"]])("cuts %s %s at the sheet radius", (file, selector) => {
    expect(rule(read(file), selector)).toMatch(/border-radius:\s*var\(--r-sheet\)/);
  });

  it("sets the dialog actions on the dialog's own surface, with no band and no seam", () => {
    const footer = rule(read("primitives/Modal.module.css"), ".content [data-dialog-footer]");
    expect(footer).toMatch(/background:\s*transparent/);
    expect(footer).not.toMatch(/box-shadow|border/);
    const sheet = rule(read("primitives/ConfirmDelete.module.css"), ".body.inSheet [data-dialog-footer]");
    expect(sheet).toMatch(/background:\s*transparent/);
    expect(sheet).not.toMatch(/box-shadow|border/);
    expect(read("primitives/DialogFooter.jsx")).toMatch(/data-dialog-footer/);
  });
});

describe("paper selection", () => {
  it("draws the chosen sidebar row as a rounded neutral fill inside the gutter, no bleed and no stripe", () => {
    const ds = read("styles/design-system.css");
    expect(rule(ds, ".ds-sb-row, .sb-row")).toMatch(/border-radius:\s*var\(--r-control\)/);
    expect(ds).toMatch(/\.ds-sb-row:hover, \.sb-row:hover \{ background: var\(--hover\); transition: background-color var\(--state-in\); \}/);
    expect(ds).toMatch(/\.ds-sb-row\[data-sel\]:hover, \.sb-row\[data-sel\]:hover \{\s*background: var\(--selected\);\s*\}/);
    expect(ds).not.toMatch(/sb-bleed|--row-accent|border-radius: 0;\s*\}\s*\.ds-sb-row \.ts/);
    expect(read("features/Sidebar.module.css")).not.toMatch(/--sb-bleed/);
    const row = read("primitives/SidebarRow.jsx");
    expect(row).not.toMatch(/--row-accent|colorWash|color-mix/);
    expect(row).toMatch(/data-sel=\{sel \|\| undefined\}/);
    expect(row).toMatch(/aria-current=\{sel \? "page" : undefined\}/);
  });

  it("steps the trailing text on the chosen row to ink-2", () => {
    expect(read("styles/design-system.css")).toMatch(/\.sb-row\[data-sel\] \.ts \{ color: var\(--ink-2\); \}/);
  });

  it("cuts chips and status pills as pills, the chip radius retired", () => {
    expect(read("styles/tokens.css")).not.toMatch(/--r-chip/);
    expect(rule(read("primitives/Chip.module.css"), ".chip")).toMatch(/border-radius:\s*var\(--r-pill\)/);
    expect(rule(read("primitives/PipelineStages.module.css"), ".chip")).toMatch(/border-radius:\s*var\(--r-pill\)/);
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
  it("draws your message as a neutral bubble at the surface radius, never in the profile's colour", () => {
    expect(rule(read("primitives/ProfileMessage.module.css"), ".userBubble")).toMatch(/border-radius:\s*var\(--r-surface\);\s*background:\s*var\(--fill\)/);
    expect(read("primitives/ProfileMessage.jsx")).not.toMatch(/color-mix|accent/);
    expect(rule(read("primitives/MessageBubble.module.css"), ".bubble")).toMatch(/border-radius:\s*var\(--r-surface\)/);
    expect(rule(read("primitives/Message.module.css"), ".bubble")).not.toMatch(/box-shadow/);
    expect(rule(read("pages/ChatSkeletons.module.css"), ".userBubble")).toMatch(/border-radius:\s*var\(--r-surface\)/);
  });
});

describe("paper toasts", () => {
  it("floats a notice on the raised surface at the surface radius with the float shadow", () => {
    const toast = rule(read("primitives/Notification.module.css"), ".toast");
    expect(toast).toMatch(/border-radius:\s*var\(--r-surface\)/);
    expect(toast).toMatch(/background:\s*var\(--raised\)/);
    expect(toast).toMatch(/box-shadow:\s*var\(--shadow-float\)/);
    expect(toast).toMatch(/border:\s*0;/);
  });
});
