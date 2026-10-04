import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = join(import.meta.dirname, "..");
const read = (rel) => readFileSync(join(SRC, rel), "utf8");
const tokens = read("styles/tokens.css");

function blocks() {
  const light = tokens.slice(0, tokens.indexOf("@media (prefers-color-scheme: dark)"));
  const media = tokens.slice(tokens.indexOf("@media (prefers-color-scheme: dark)"), tokens.indexOf('[data-mode="dark"]'));
  const forced = tokens.slice(tokens.indexOf('[data-mode="dark"]'));
  return { light, media, forced };
}

const value = (css, name) => css.match(new RegExp(`${name}:\\s*([^;]+);`))?.[1].trim().toLowerCase();

describe("needs-you warning vs working accent", () => {
  it.each(Object.entries(blocks()))("resolves to different colours in the %s palette", (_mode, css) => {
    const warning = value(css, "--c-warning-text");
    const accent = value(css, "--accent");
    expect(warning).toBeTruthy();
    expect(accent).toBeTruthy();
    expect(warning).not.toBe(accent);
  });

  it.each([
    ["features/Sidebar.module.css", /\.stateChip\[data-state="needs-you"\] \{[^}]*var\(--c-warning-text\)/, /\.stateChip\[data-state="working"\] \{[^}]*var\(--c, var\(--ink-2\)\)/],
    ["features/ActivityPanel.module.css", /\.glyph\[data-tone="warning"\] \{[^}]*var\(--c-warning-text\)/, /\.glyph\[data-tone="accent"\] \{[^}]*var\(--c, var\(--ink-2\)\)/],
  ])("%s paints needs-you with the warning token and working with the profile colour", (file, needs, working) => {
    const css = read(file);
    expect(css).toMatch(needs);
    expect(css).toMatch(working);
  });

  it("never colours warning text with the fill token", () => {
    const offenders = [];
    for (const file of ["features/ToolsModal.module.css", "features/Sidebar.module.css", "features/ActivityPanel.module.css"]) {
      for (const m of read(file).matchAll(/(^|[\s;{])color:\s*var\(--c-warning[,)]/g)) offenders.push(`${file}: ${m[0].trim()}`);
    }
    expect(offenders).toEqual([]);
  });
});
