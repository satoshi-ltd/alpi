import { readFileSync } from "node:fs";
import { join } from "node:path";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import RefreshBar from "./RefreshBar.jsx";
import BrowseModal from "./BrowseModal.jsx";
import { ACCENT_HEXES } from "../../../common/accents.mjs";
import { contrastRatio, nameTone } from "../../../common/name.mjs";
import { palettes } from "../../../common/tokens.mjs";

const SRC = join(import.meta.dirname, "..");

describe("the refresh bar wears the profile colour", () => {
  it("carries the profile hue, toned per theme like the name", () => {
    render(<RefreshBar active controlled color="#ff3366" label="Syncing" />);
    const bar = screen.getByRole("progressbar", { name: "Syncing" });
    expect(bar.style.getPropertyValue("--c-light")).toBe(nameTone("#ff3366", palettes.light.bgPane));
    expect(bar.style.getPropertyValue("--c-dark")).toBe(nameTone("#ff3366", palettes.dark.bgPane));
  });

  it.each(ACCENT_HEXES)("%s passes 3:1 on both grounds of both themes", (accent) => {
    render(<RefreshBar active controlled color={accent} label={`bar ${accent}`} />);
    const bar = screen.getByRole("progressbar", { name: `bar ${accent}` });
    for (const [mode, prop] of [["light", "--c-light"], ["dark", "--c-dark"]]) {
      const tone = bar.style.getPropertyValue(prop);
      expect(tone).toMatch(/^#[0-9a-f]{6}$/);
      expect(contrastRatio(tone, palettes[mode].bg)).toBeGreaterThanOrEqual(3);
      expect(contrastRatio(tone, palettes[mode].bgPane)).toBeGreaterThanOrEqual(3);
    }
  });

  it("falls back to the brand ink without a colour", () => {
    render(<RefreshBar active controlled label="Syncing" />);
    const bar = screen.getByRole("progressbar", { name: "Syncing" });
    expect(bar.getAttribute("style")).toBeNull();
    const css = readFileSync(join(SRC, "styles/design-system.css"), "utf8");
    const rule = css.match(/\.refresh-bar > i \{([^}]*)\}/)[1];
    expect(rule).toMatch(/background: var\(--c-light, var\(--accent\)\);/);
    expect(css).toMatch(/:root:not\(\[data-mode="light"\]\) \.refresh-bar > i \{ background: var\(--c-dark, var\(--accent\)\); \}/);
    expect(css).toMatch(/\[data-mode="dark"\] \.refresh-bar > i \{ background: var\(--c-dark, var\(--accent\)\); \}/);
  });

  it("a browse panel's wait keeps the brand ink", () => {
    render(
      <BrowseModal open onClose={() => {}} title="Skills" loading loadingLabel="Loading skills" accent="#ff3366" owner={{ name: "lens", accent: "#ff3366", shape: "lens" }} list={<ul />} />,
    );
    const bar = screen.getByRole("progressbar", { name: "Loading skills" });
    expect(bar.getAttribute("style")).toBeNull();
    expect(bar.outerHTML).not.toContain("#ff3366");
  });

  it.each([
    ["pages/ChatPane.jsx", "activeProfile?.accent"],
    ["features/settings/ProfileDetail.jsx", "profile.accent"],
    ["pages/WorkgroupView.jsx", "ownerProfile?.accent"],
    ["features/settings/WorkgroupDetail.jsx", "hub?.accent"],
  ])("%s hands the bar its owner's accent", (file, expr) => {
    const source = readFileSync(join(SRC, file), "utf8");
    const bars = [...source.matchAll(/<RefreshBar\b[\s\S]*?\/>/g)].map((m) => m[0]);
    expect(bars.some((tag) => tag.includes(`color={${expr}`))).toBe(true);
  });
});
