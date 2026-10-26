import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = join(import.meta.dirname, "..");
const css = (rel) => readFileSync(join(SRC, rel), "utf8");
const rule = (sheet, selector) => {
  const start = sheet.indexOf(`${selector} {`);
  expect(start, `${selector} rule`).toBeGreaterThanOrEqual(0);
  return sheet.slice(start, sheet.indexOf("}", start));
};

describe("sidebar footer", () => {
  const sidebar = css("features/Sidebar.module.css");
  const version = css("features/VersionButton.module.css");

  it("draws Settings as a 24 px icon button like its neighbours, with no label", () => {
    expect(sidebar).not.toMatch(/footerLabel|footerTight/);
    const jsx = readFileSync(join(SRC, "features/Sidebar.jsx"), "utf8");
    expect(jsx).toMatch(/aria-label="Settings"/);
    expect(jsx).not.toMatch(/>Settings<\/span>/);
    expect(rule(sidebar, ".footer :global(.ds-tip) .footerIcon")).toMatch(/width: var\(--ctl-24\);\s*height: var\(--ctl-24\)/);
  });

  it("lets the version fill the rest of the row, ending on the same inset the Settings pill starts on", () => {
    expect(rule(sidebar, ".footer > :last-child")).toMatch(/flex:\s*1 1 0/);
    expect(rule(sidebar, ".footer > :last-child")).not.toMatch(/margin-left/);
    const trigger = rule(version, ".trigger");
    expect(trigger).not.toMatch(/margin:/);
    expect(trigger).toMatch(/width:\s*100%/);
    expect(trigger).toMatch(/justify-content:\s*flex-end/);
  });

  it("sizes the version as a 24 px control centred like the icon buttons", () => {
    const trigger = rule(version, ".trigger");
    expect(trigger).toMatch(/height:\s*var\(--ctl-24\)/);
    expect(trigger).toMatch(/align-items:\s*center/);
    expect(trigger).toMatch(/line-height:\s*var\(--lh-tight\)/);
  });

  it("keeps the pin button on a whole pixel inside its wrapper", () => {
    expect(rule(sidebar, ".pinWrap")).toMatch(/display:\s*flex/);
  });
});

describe("connection label", () => {
  it("is a block on the section label column, not an inline span with dead padding", () => {
    const label = rule(css("features/ConnectionSwitcher.module.css"), ".label");
    expect(label).toMatch(/display:\s*block/);
    expect(label).toMatch(/padding:\s*0 var\(--sp-12\) var\(--sp-8\) calc\(var\(--sp-12\) \+ 2px\)/);
  });
});

describe("whole-pixel line boxes", () => {
  it("keeps the chat header meta row at a whole height with one shared line height", () => {
    const sheet = css("styles/design-system.css");
    const row = rule(sheet, ".ds-chat-header .meta-row");
    expect(row).toMatch(/line-height:\s*var\(--lh-tight\)/);
    expect(row).toMatch(/padding:\s*3px 0/);
    expect(rule(sheet, ".ds-chat-header .meta-row .sep")).toMatch(/height:\s*11px/);
  });

  it("gives menu rows a 16 px line so padding makes them exactly 32 px", () => {
    expect(rule(css("primitives/Menu.module.css"), ".row")).toMatch(/line-height:\s*var\(--sp-16\)/);
  });

  it("aligns a menu row caption to the name's baseline", () => {
    expect(rule(css("primitives/Dropdown.module.css"), ".rowMain")).toMatch(/align-items:\s*baseline/);
  });

  it("gives banners, action links, toasts, the welcome hint and the empty model whole-pixel lines", () => {
    expect(rule(css("primitives/Banner.module.css"), ".body")).toMatch(/line-height:\s*var\(--sp-16\)/);
    expect(rule(css("styles/design-system.css"), ".ds-alink, .alink")).toMatch(/line-height:\s*var\(--sp-16\)/);
    expect(rule(css("primitives/Notification.module.css"), ".text")).toMatch(/line-height:\s*var\(--sp-16\)/);
    const welcome = css("features/Welcome.module.css");
    expect(rule(welcome, ".hintTitle")).toMatch(/line-height:\s*var\(--sp-16\)/);
    expect(rule(welcome, ".hintText")).toMatch(/line-height:\s*var\(--sp-16\)/);
    expect(rule(css("pages/ChatPane.module.css"), ".emptyModel")).toMatch(/line-height:\s*var\(--sp-16\)/);
  });
});

describe("approved pixel decisions", () => {
  it("puts the toast stack 32 px from the right and 16 px from the bottom", () => {
    const stack = rule(css("primitives/Notification.module.css"), ".stack");
    expect(stack).toMatch(/bottom:\s*var\(--sp-16\)/);
    expect(stack).toMatch(/right:\s*var\(--sp-32\)/);
    expect(stack).toMatch(/max-width:\s*calc\(100vw - var\(--sp-32\) \* 2\)/);
  });

  it("draws every status dot on the 6 or 8 px tokens and declares no 7 px dot", () => {
    expect(css("styles/tokens.css")).not.toMatch(/--dot-size/);
    expect(css("styles/tokens.css")).toMatch(/--dot-sm:\s*6px;[^]*--dot-md:\s*8px;/);
    for (const file of ["styles/design-system.css", "primitives/Banner.module.css", "primitives/ConnPill.module.css", "features/ConnectionSwitcher.module.css", "primitives/MarkerCard.module.css", "pages/WorkgroupView.module.css", "pages/WorkgroupsView.module.css", "primitives/Notification.module.css"]) {
      expect(css(file), file).not.toMatch(/dot-size|(width|height):\s*7px/);
    }
    expect(rule(css("primitives/Banner.module.css"), ".dot")).toMatch(/width:\s*var\(--dot-md\);\s*height:\s*var\(--dot-md\)/);
    expect(rule(css("primitives/ConnPill.module.css"), ".dot")).toMatch(/width:\s*var\(--dot-md\)/);
    expect(rule(css("primitives/Notification.module.css"), ".dot")).toMatch(/width:\s*var\(--dot-md\)/);
  });

  it("insets the composer's send button 16 px from the right and 12 px from the bottom over the half pixel border", () => {
    const body = rule(css("primitives/Composer.module.css"), ".body");
    expect(body).toMatch(/border:\s*\.5px solid/);
    expect(body).toMatch(/padding:\s*calc\(var\(--sp-16\) \+ \.5px\) calc\(var\(--sp-16\) - \.5px\) calc\(var\(--sp-12\) - \.5px\);/);
  });

  it("sets the banner action at the message size, distinguished by weight", () => {
    const action = rule(css("primitives/Banner.module.css"), ".action");
    expect(action).toMatch(/font-size:\s*var\(--text-meta\)/);
    expect(action).toMatch(/font-weight:\s*var\(--fw-semibold\)/);
    expect(rule(css("primitives/Banner.module.css"), ".body")).toMatch(/font-size:\s*var\(--text-meta\)/);
    expect(rule(css("styles/design-system.css"), ".ds-alink, .alink")).toMatch(/font-size:\s*var\(--text-ui\)/);
  });

  it("keeps menu and dropdown rows at exactly 32 px", () => {
    const row = rule(css("primitives/Menu.module.css"), ".row");
    expect(row).toMatch(/min-height:\s*var\(--ctl-32\)/);
    expect(row).toMatch(/padding:\s*var\(--sp-8\) var\(--sp-12\)/);
    expect(row).toMatch(/line-height:\s*var\(--sp-16\)/);
    expect(css("primitives/Dropdown.module.css")).toMatch(/height:\s*var\(--ctl-32\)/);
    expect(rule(css("primitives/Dropdown.module.css"), ".rowMain")).toMatch(/height:\s*var\(--sp-16\)/);
  });

  it("starts the sidebar section label on the glyph column", () => {
    expect(rule(css("primitives/SectionLabel.module.css"), ".label")).toMatch(/padding-left:\s*0;/);
  });
});
