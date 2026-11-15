import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const read = (file) => readFileSync(join(import.meta.dirname, "..", file), "utf8");

describe("chat header", () => {
  it("centres the title and the right-hand controls in one 56 px bar that fades into the stream", () => {
    const css = read("primitives/ChatHeader.module.css");
    expect(css).toMatch(/:global\(\.ds-chat-header\)\.bar \{[^}]*align-items: center;[^}]*height: var\(--header-h\);/);
    expect(css).toMatch(/:global\(\.ds-chat-header\)\.bar::after \{[^}]*background: linear-gradient\(var\(--bg-pane\), transparent\)/);
    expect(read("styles/tokens.css")).toMatch(/--header-h: 56px;/);
  });

  it("starts the header under the titlebar band, on the pane's left edge, level with the connection switcher", () => {
    const css = read("primitives/ChatHeader.module.css");
    const bar = css.match(/:global\(\.ds-chat-header\)\.bar \{([^}]*)\}/)[1];
    expect(bar).toMatch(/box-sizing: content-box;/);
    expect(bar).toMatch(/padding: var\(--titlebar-h\) var\(--sp-24\) 0 var\(--pane-pad-x\);/);
    expect(read("features/Sidebar.module.css")).toMatch(/\.titlebarSpacer \{\s*height: var\(--titlebar-h\);/);
    expect(read("features/ConnectionSwitcher.module.css")).toMatch(/\.label \{[^}]*position: absolute;[^}]*clip-path: inset\(50%\);/);
  });
});

describe("message action rows", () => {
  it("keeps the time on the outer edge, the text edge for an answer and the bubble edge for yours, so hidden actions never push it", () => {
    const source = read("pages/ChatPane.jsx");
    expect(source).toMatch(/data-side=\{side\}/);
    expect(source).toMatch(/\{side === "right" \? null : timeNode\}\s*<span className=\{`\$\{styles\.footActions\}/);
    expect(source).toMatch(/\{children\}<\/span>\s*\{side === "right" \? timeNode : null\}/);
    const css = read("pages/ChatPane.module.css");
    expect(css).toMatch(/\.foot\[data-side="right"\] \{\s*justify-content: flex-end;/);
    expect(css).not.toMatch(/\.footActions \{\s*margin-(left|right): calc/);
  });
});

describe("one disclosure affordance", () => {
  const steps = read("features/ToolSteps.jsx");
  const reasoning = read("primitives/Reasoning.jsx");

  it("places the chevron right after the label in tool rows, reasoning and the bucket", () => {
    expect(steps).toMatch(/styles\.name\}>\{tool\.name\}<\/span>\s*<Icon name="chevron-right"/);
    expect(steps).toMatch(/styles\.bucketLabel\}>[^\n]*<\/span>\s*<Icon name="chevron-right"/);
    expect(reasoning).toMatch(/\{labelNode\}\s*<Icon name="chevron-right"[^\n]*\s*\{peekNode\}/);
    expect(steps).not.toMatch(/CaretIcon/);
  });

  it("rotates every chevron from right to down and tucks it against the label", () => {
    const toolCss = read("features/ToolSteps.module.css");
    const reasoningCss = read("primitives/Reasoning.module.css");
    expect(toolCss).toMatch(/\.chevOpen \{ transform: rotate\(90deg\); \}/);
    expect(toolCss).toMatch(/\.bucketChevOpen \{ transform: rotate\(90deg\); \}/);
    expect(toolCss).not.toMatch(/rotate\(-90deg\)/);
    expect(reasoningCss).toMatch(/\.chevOpen \{ transform: rotate\(90deg\); \}/);
    for (const css of [toolCss, reasoningCss]) expect(css).toMatch(/\.(chev|bucketChev) \{[^}]*margin-left: calc\(var\(--sp-4\) \* -1\)/);
  });

  it("keeps the accent off the reasoning label", () => {
    expect(read("primitives/Reasoning.module.css")).toMatch(/\.label \{[^}]*color: var\(--ink-3\);/);
  });
});

describe("approval card", () => {
  it("draws the card as a fill at the surface radius with no ring and tints nothing but the glyph", () => {
    const css = read("features/InlineRequest.module.css");
    expect(css).toMatch(/\.card \{[^}]*border-radius: var\(--r-surface\);\s*background: var\(--card\);/);
    expect(css.match(/\.card \{([^}]*)\}/)[1]).not.toMatch(/box-shadow|border:/);
    expect(css).not.toMatch(/c-warning\) \d+%, var\(--bg-pane\)/);
    expect(css).not.toMatch(/\.dangerous \{/);
    expect(css).toMatch(/\.dangerous \.alert \{ color: var\(--c-danger\); \}/);
  });

  it("offers one primary action and ghost alternatives", () => {
    const source = read("features/InlineRequest.jsx");
    const approval = source.slice(source.indexOf("export function InlineApproval"), source.indexOf("function modeFor"));
    expect(approval.match(/variant="primary"/g)).toHaveLength(1);
    expect(approval.match(/variant="ghost"/g)).toHaveLength(3);
    expect(approval).not.toMatch(/variant="secondary"/);
  });
});

describe("banner grammar", () => {
  it("draws every banner as a flat tint with no rule or ring, in a 16 px lead lane", () => {
    const ds = read("styles/design-system.css");
    expect(ds).not.toMatch(/\n\.banner \{[^}]*border/);
    expect(ds).toMatch(/\.banner\.is-warning \{[^}]*background: color-mix\(in srgb, var\(--c-warning\)/);
    expect(read("primitives/Banner.module.css")).toMatch(/\.dot \{\s*margin-inline: calc\(\(var\(--icon-md\) - var\(--dot-md\)\) \/ 2\)/);
    expect(read("primitives/Banner.module.css")).toMatch(/\.glyph \{\s*margin-inline: calc\(\(var\(--icon-md\) - var\(--icon-sm\)\) \/ 2\)/);
    const alert = read("primitives/AlertBanner.module.css");
    expect(alert).toMatch(/\.banner \{[^}]*background: color-mix\(in srgb, var\(--c-danger\) var\(--banner-tint\), var\(--bg-pane\)\);/);
    expect(alert).not.toMatch(/box-shadow|ring-ctrl|border-radius/);
    expect(read("primitives/AlertBanner.jsx")).not.toMatch(/<Button/);
  });

  it("pads toasts the same with or without an action: 16 before the text, 8 round the action", () => {
    const css = read("primitives/Notification.module.css");
    expect(css).toMatch(/\.toast \{[^}]*padding: var\(--sp-8\) var\(--sp-8\) var\(--sp-8\) var\(--sp-16\);/);
    expect(css).toMatch(/\.toastWithAction \{\s*padding: var\(--sp-8\) var\(--sp-8\) var\(--sp-8\) var\(--sp-16\);/);
  });
});
