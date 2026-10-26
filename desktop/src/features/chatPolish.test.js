import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const read = (file) => readFileSync(join(import.meta.dirname, "..", file), "utf8");

describe("chat header", () => {
  it("aligns the right-hand controls to the title line", () => {
    const css = read("primitives/ChatHeader.module.css");
    expect(css).toMatch(/\.topRow \{\s*align-items: flex-start;/);
    expect(css).toMatch(/\.actions \{[^}]*height: var\(--ctl-32\);[^}]*margin-top: calc\(\(var\(--text-display\) - var\(--ctl-32\)\) \/ 2\)/);
  });
});

describe("message action rows", () => {
  it("sits the time on the opposite side of the bubble edge the icons align to", () => {
    const source = read("pages/ChatPane.jsx");
    expect(source).toMatch(/data-side=\{side\}/);
    expect(source).toMatch(/\{side === "right" \? timeNode : null\}\s*<span className=\{`\$\{styles\.footActions\}/);
    expect(source).toMatch(/\{side === "right" \? null : timeNode\}/);
  });

  it("pulls the first and last glyph onto the text and bubble edges", () => {
    const css = read("pages/ChatPane.module.css");
    expect(css).toMatch(/\.foot\[data-side="left"\] \.footActions \{\s*margin-left: calc\(\(var\(--ctl-28\) - var\(--icon-sm\)\) \/ -2\)/);
    expect(css).toMatch(/\.foot\[data-side="right"\] \.footActions \{\s*margin-right: calc\(\(var\(--ctl-24\) - var\(--icon-sm\)\) \/ -2\)/);
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
  it("rings the card with ink-4 and tints nothing but the glyph", () => {
    const css = read("features/InlineRequest.module.css");
    expect(css).toMatch(/\.card \{[^}]*background: var\(--card\);[^}]*box-shadow: var\(--ring-ctrl\)/);
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
  it("draws every banner with a tinted fill, an ink-4 border and a 16 px icon lane", () => {
    const ds = read("styles/design-system.css");
    expect(ds).toMatch(/\n\.banner \{[^}]*border-bottom: 1px solid var\(--ink-4\)/);
    expect(ds).toMatch(/\.banner\.is-warning \{ background: color-mix\(in srgb, var\(--c-warning\)/);
    expect(read("primitives/Banner.module.css")).toMatch(/\.dot \{\s*margin-inline: calc\(\(var\(--icon-md\) - var\(--dot-md\)\) \/ 2\)/);
    const alert = read("primitives/AlertBanner.module.css");
    expect(alert).toMatch(/\.banner \{[^}]*background: color-mix\(in srgb, var\(--c-danger\) 10%, var\(--bg-pane\)\);[^}]*box-shadow: var\(--ring-ctrl\)/);
    expect(read("primitives/AlertBanner.jsx")).toMatch(/variant="ghost"/);
  });

  it("pads toasts on the shared token with or without an action", () => {
    const css = read("primitives/Notification.module.css");
    expect(css).toMatch(/\.toast \{[^}]*padding: var\(--toast-pad\);/);
    expect(css).toMatch(/\.toastWithAction \{\s*padding: var\(--toast-pad\);/);
  });
});
