import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { bannerTint } from "../../../common/tokens.mjs";

const read = (file) => readFileSync(join(import.meta.dirname, "..", file), "utf8");
const TOKENS = read("styles/tokens.css");
const DS = read("styles/design-system.css");
const block = (re) => TOKENS.match(re)[1];

describe("banner tints come from the shared token module", () => {
  it.each([
    ["light", /^:root\s*\{([\s\S]*?)\n\}/m],
    ["dark", /:root:not\(\[data-mode="light"\]\)\s*\{([^}]*)\}/],
    ["dark", /^\[data-mode="dark"\]\s*\{([^}]*)\}/m],
  ])("declares the %s tint and quiet tint as the shared percentages", (mode, re) => {
    const body = block(re);
    expect(body).toMatch(new RegExp(`--banner-tint:\\s*${Math.round(bannerTint[mode].tint * 100)}%;`));
    expect(body).toMatch(new RegExp(`--banner-tint-quiet:\\s*${Math.round(bannerTint[mode].quiet * 100)}%;`));
  });
});

describe("banners in forced colours", () => {
  it("gives the shared banner a CanvasText edge and a CanvasText lead dot", () => {
    const media = DS.match(/@media \(forced-colors: active\) \{([\s\S]*?)\n\}/)[1];
    expect(media).toMatch(/\.banner \{ border-block-end: 1px solid CanvasText; \}/);
    expect(media).toMatch(/\.banner > \.ds-dot \{ forced-color-adjust: none; background: CanvasText; \}/);
  });

  it("gives the alert banner the same CanvasText edge", () => {
    expect(read("primitives/AlertBanner.module.css")).toMatch(/@media \(forced-colors: active\) \{\s*\.banner \{ border-block-end: 1px solid CanvasText; \}/);
  });
});

describe("banner actions", () => {
  it("never hovers or presses a disabled action link", () => {
    expect(DS).toMatch(/\.alink:not\(:disabled\):hover\s*\{/);
    expect(DS).toMatch(/\.alink:not\(:disabled\):active\s*\{/);
    expect(DS).not.toMatch(/\.alink:hover|\.alink:active/);
    expect(DS).toMatch(/\.alink:disabled \{ opacity: var\(--alpha-disabled\); cursor: not-allowed; \}/);
  });

  it("keeps a banner action in its kind's text colour on hover, over a faint tint of the same hue", () => {
    expect(DS).toMatch(/\.alink:not\(:disabled\):hover\s*\{ background: var\(--alink-hover-fill, var\(--hover\)\); color: var\(--alink-hover, var\(--ink\)\); transition: background-color var\(--state-in\), color var\(--state-in\); \}/);
    const banner = read("primitives/Banner.module.css").match(/\.action \{([^}]*)\}/)[1];
    expect(banner).toMatch(/--alink-hover: var\(--banner-text, var\(--ink-2\)\);/);
    expect(banner).toMatch(/--alink-hover-fill: color-mix\(in srgb, var\(--banner-text, var\(--ink-2\)\) 10%, transparent\);/);
    const alert = read("primitives/AlertBanner.module.css").match(/\.action \{([^}]*)\}/)[1];
    expect(alert).toMatch(/--alink-hover: var\(--c-danger-text\);/);
  });
});

describe("one banner everywhere", () => {
  it.each([
    ["features/SkillsModal.jsx", /<Banner kind=\{invalid \? "danger" : "warning"\}>/, "features/SkillsModal.module.css", /\.callout/],
    ["pages/WorkgroupView.jsx", /<Banner kind="danger">\{error\}<\/Banner>/, "pages/WorkgroupView.module.css", /^\.error \{/m],
    ["features/NotificationsModal.jsx", /<Banner kind="warning">\{unreachableTitle\(unreachable\)\}/, "features/NotificationsModal.module.css", /\.partial \{[^}]*background/],
  ])("%s draws its notice with the shared Banner and keeps no custom tint", (file, use, css, gone) => {
    expect(read(file)).toMatch(use);
    expect(read(css)).not.toMatch(gone);
  });
});
