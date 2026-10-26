import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ICONS } from "../../../common/iconPaths.mjs";
import { iconStrokeRendered } from "../../../common/tokens.mjs";
import Icon, { iconPx } from "./Icon.jsx";

const SRC = join(import.meta.dirname, "..");
const walk = (dir) =>
  readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? walk(path) : [path];
  });
const SOURCES = walk(SRC).filter((p) => p.endsWith(".jsx") && !p.includes(".test."));
const svgOf = (props) => render(<Icon name="search" {...props} />).container.querySelector("svg");

describe("Icon sizes", () => {
  it.each([
    ["sm", 14],
    ["md", 16],
    [undefined, 16],
    [11, 14],
    [12, 14],
    [13, 14],
    [14, 14],
    [16, 16],
    [18, 16],
    ["lg", 16],
  ])("draws size %s at %s px", (size, px) => {
    expect(iconPx(size)).toBe(px);
    const svg = svgOf(size === undefined ? {} : { size });
    expect(svg.getAttribute("width")).toBe(String(px));
    expect(svg.getAttribute("height")).toBe(String(px));
  });

  it("renders the same 1.33 px line at both sizes", () => {
    for (const size of ["sm", "md"]) {
      const svg = svgOf({ size });
      const rendered = (Number(svg.getAttribute("stroke-width")) * Number(svg.getAttribute("width"))) / 24;
      expect(rendered).toBeCloseTo(iconStrokeRendered, 5);
    }
  });

  it("ignores a stroke override so no icon thickens", () => {
    const svg = svgOf({ size: "md", strokeWidth: 3 });
    expect(Number(svg.getAttribute("stroke-width"))).toBeCloseTo((iconStrokeRendered * 24) / 16, 5);
  });

  it("fills only the profile identity glyph", () => {
    const filled = Object.entries(ICONS).filter(([, def]) => !Array.isArray(def) && (def.sw === 0 || def.fill));
    expect(filled.map(([name]) => name)).toEqual(["alpi"]);
    const svg = render(<Icon name="alpi" />).container.querySelector("svg");
    expect(svg.getAttribute("stroke")).toBe("none");
    expect(svg.getAttribute("fill")).toBe("currentColor");
  });
});

describe("Icon call sites", () => {
  const tags = SOURCES.flatMap((file) => [...readFileSync(file, "utf8").matchAll(/<(?:Icon|[A-Z][A-Za-z]*Icon|I\.[A-Za-z]+)\b[^>]*?\/?>/gs)].map((m) => ({ file: relative(SRC, file), tag: m[0] })));

  it("scans a meaningful number of icons", () => {
    expect(tags.length).toBeGreaterThan(100);
  });

  it("passes only sm, md, 14 or 16 as an icon size", () => {
    const offenders = tags.filter(({ tag }) => /\bsize=(?:"(?:xs|lg|xl)"|\{(?!14\}|16\})\d+\})/.test(tag));
    expect(offenders).toEqual([]);
  });

  it("never sets a stroke or a pixel box on an icon by hand", () => {
    const offenders = tags.filter(({ tag }) => /strokeWidth|style=\{\{[^}]*(?:width|height):/.test(tag));
    expect(offenders).toEqual([]);
  });

  it("leaves the shared .ds-icon rule without a size or a stroke", () => {
    const css = readFileSync(join(SRC, "styles/design-system.css"), "utf8");
    const body = css.match(/\.ds-icon, \.icon \{([^}]*)\}/)[1];
    expect(body).not.toMatch(/width|height|stroke|fill/);
  });
});
