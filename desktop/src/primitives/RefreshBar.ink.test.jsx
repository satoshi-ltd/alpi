import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import RefreshBar from "./RefreshBar.jsx";
import BrowseModal from "./BrowseModal.jsx";

const SRC = join(import.meta.dirname, "..");

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.jsx?$/.test(name) && !/\.test\./.test(name)) out.push(p);
  }
  return out;
}

describe("the refresh bar waits in ink", () => {
  it("takes no colour from its caller", () => {
    render(<RefreshBar active controlled accent="#ff3366" style={{ "--c": "#ff3366" }} label="Syncing" />);
    const bar = screen.getByRole("progressbar", { name: "Syncing" });
    expect(bar.getAttribute("style")).toBeNull();
    expect(bar.outerHTML).not.toContain("#ff3366");
  });

  it("paints only the brand ink token, never an inherited profile colour", () => {
    const css = readFileSync(join(SRC, "styles/design-system.css"), "utf8");
    const rule = css.match(/\.refresh-bar > i \{([^}]*)\}/)[1];
    expect(rule).toMatch(/background: var\(--accent\);/);
    expect(rule).not.toMatch(/--c\b/);
  });

  it("a browse panel's wait carries no owner colour", () => {
    render(
      <BrowseModal open onClose={() => {}} title="Skills" loading loadingLabel="Loading skills" accent="#ff3366" owner={{ name: "lens", accent: "#ff3366", fold: "lens" }} list={<ul />} />,
    );
    const bar = screen.getByRole("progressbar", { name: "Loading skills" });
    expect(bar.getAttribute("style")).toBeNull();
    expect(bar.outerHTML).not.toContain("#ff3366");
  });

  it("no caller hands the bar a colour", () => {
    const offenders = [];
    for (const path of walk(SRC)) {
      const source = readFileSync(path, "utf8");
      for (const m of source.matchAll(/<RefreshBar\b[^>]*>/g)) {
        if (/\baccent=|\bstyle=/.test(m[0])) offenders.push(`${relative(SRC, path)}: ${m[0].replace(/\s+/g, " ")}`);
      }
    }
    expect(offenders).toEqual([]);
  });
});
