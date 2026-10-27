import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const read = (file) => readFileSync(join(import.meta.dirname, "..", file), "utf8");

describe("one left edge", () => {
  it("pads the chat header and banners on the pane edge, not on the centred column", () => {
    const css = read("styles/design-system.css");
    expect(css).toMatch(/\.ds-chat-header \{[^}]*padding:[^;]*var\(--pane-pad-x\)/);
    expect(css).toMatch(/\n\.banner \{[^}]*padding:[^;]*var\(--pane-pad-x\)/);
    expect(css + read("styles/tokens.css")).not.toMatch(/--pane-edge/);
  });

  it("keeps the settings body on the left edge, not in a centred column", () => {
    const css = read("features/settings/Settings.module.css");
    expect(css).toMatch(/\.body > \* \{[^}]*max-width: calc\(var\(--stream-max\) \+ 200px\)[^}]*width: 100%/);
    expect(css).not.toMatch(/\.body > \* \{[^}]*margin-left: auto/);
    expect(css).not.toMatch(/\.navLayout \{[^}]*max-width/);
  });

  it("lets the brief and identity textareas fill the settings column", () => {
    const css = read("features/settings/Settings.module.css");
    expect(css).toMatch(/\.briefingWrap \.textarea \{\s*max-width: none;/);
    expect(css).not.toMatch(/\.identityBlock \{[^}]*max-width/);
  });

  it("keeps stream and composer on the same centred column", () => {
    expect(read("pages/ChatPane.module.css")).toMatch(/\.timeline \{[^}]*max-width: var\(--stream-max\)[^}]*margin-left: auto/);
    expect(read("primitives/Composer.module.css")).toMatch(/max-width: var\(--composer-max\);\s*margin: 0 auto;/);
    expect(read("styles/tokens.css")).toMatch(/--composer-max: var\(--stream-max\)/);
  });

  it.each([
    ["pages/WorkgroupsView.module.css", /\.toolbar, \.tableHead, \.row \{[^}]*margin-inline: calc\(-1 \* var\(--row-bleed\)\)/],
    ["features/settings/ConnectionsPage.module.css", /\.tableToolbar, \.tableHead, \.group[^{]*\{[^}]*margin-inline: calc\(-1 \* var\(--row-bleed\)\)/],
  ])("%s bleeds the hover fill so cell text sits on the header edge", (file, pattern) => {
    expect(read(file)).toMatch(pattern);
    expect(read("styles/tokens.css")).toMatch(/--row-bleed:\s*var\(--sp-12\)/);
  });

  it("gives the workgroups table one row height with a single-line status", () => {
    const css = read("pages/WorkgroupsView.module.css");
    expect(css).toMatch(/\.row \{ min-height: var\(--ctl-40\);/);
    expect(css).toMatch(/\.statusCell \{[^}]*flex-direction: row|\.statusCell \{ min-width: 0; display: flex; align-items: center/);
    expect(css).toMatch(/\.tableHead span:nth-child\(n \+ 3\) \{ text-align: right; \}/);
    expect(css).toMatch(/\.row > :global\(\.mono\) \{ text-align: right;/);
  });
});
