import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

import * as shared from "../../../common/tokens.mjs";

const SRC = join(import.meta.dirname, "..");
const walk = (dir) =>
  readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? walk(path) : [path];
  });
const FILES = walk(SRC).filter((p) => !p.includes(".test."));
const SHEETS = FILES.filter((p) => p.endsWith(".css") && !p.endsWith("tokens.css") && !p.endsWith("fonts.css"));
const SOURCES = FILES.filter((p) => p.endsWith(".jsx") || p.endsWith(".js"));
const text = (file) => readFileSync(file, "utf8");
const rules = (css) => [...css.matchAll(/([^{}]*)\{([^{}]*)\}/g)].map((m) => ({ selector: m[1].trim(), body: m[2] }));
const values = (property) =>
  SHEETS.flatMap((file) => [...text(file).matchAll(new RegExp(`(?<![\\w-])${property}\\s*:\\s*([^;{}]*)`, "g"))].map((m) => ({ file: relative(SRC, file), value: m[1].trim() })));

describe("type census", () => {
  it("never reads the retired --fs-* ladder", () => {
    const offenders = [...SHEETS, ...SOURCES, join(SRC, "styles/tokens.css")].filter((f) => /--fs-/.test(text(f))).map((f) => relative(SRC, f));
    expect(offenders).toEqual([]);
  });

  it("sizes text only from the ladder, the eyebrow size or a relative em", () => {
    const allowed = /^(var\(--(text-(meta|small|ui|read|chat|title|detail|display|hero|mono|mono-ui|mono-read|[a-z-]+-size)|eyebrow-size|mono-scale)\)|inherit|[0-9.]+em|calc\(.*\)|max\(var\(--text-meta\), (var\(--mono-scale\)|[0-9.]+em)\))$/;
    expect(values("font-size").filter(({ value }) => !allowed.test(value))).toEqual([]);
  });

  it("declares the ladder 12/14/15/16/20/28 and no other UI size token", () => {
    const tokens = text(join(SRC, "styles/tokens.css"));
    const sizes = [...tokens.matchAll(/--text-(meta|small|ui|read|title|display):\s*(\d+)px/g)].map((m) => Number(m[2]));
    expect(sizes.sort((a, b) => a - b)).toEqual([...Object.values(shared.typeLadder)].sort((a, b) => a - b));
  });

  it("sets weights from 400, 500 and 600 only, bar the name face", () => {
    const offenders = values("font-weight").filter(({ file, value }) => !/^(var\(--fw-(regular|medium|semibold)\)|400|500|600|inherit|normal)$/.test(value) && !(file.endsWith("design-system.css") && value === "800"));
    expect(offenders).toEqual([]);
    expect(text(join(SRC, "styles/tokens.css"))).not.toMatch(/--fw-bold/);
  });

  it("styles every uppercase rule with the one eyebrow tracking and size", () => {
    const offenders = SHEETS.flatMap((file) =>
      rules(text(file))
        .filter(({ selector, body }) => /text-transform:\s*uppercase/.test(body) && !selector.includes("::first-letter"))
        .filter(({ body }) => !/letter-spacing:\s*var\(--eyebrow-tracking\)/.test(body) || !/font-size:\s*var\(--eyebrow-size\)/.test(body))
        .map(({ selector }) => `${relative(SRC, file)} ${selector.split("\n").pop()}`),
    );
    expect(offenders).toEqual([]);
  });

  it("keeps the wide trackings out of every rule that is not an eyebrow", () => {
    const wide = values("letter-spacing").filter(({ value }) => /^(\.|0\.)?(06|08|10|1)\d*(em)?$|px$/.test(value.replace(/^0?\./, ".")) && value !== "var(--eyebrow-tracking)");
    expect(wide).toEqual([]);
  });

  it("collapses the section label to 14 px sentence-case sans with no tracking", () => {
    const tokens = text(join(SRC, "styles/tokens.css"));
    expect(tokens).toMatch(/--eyebrow-size:\s*14px;/);
    expect(tokens).toMatch(/--eyebrow-tracking:\s*0em;/);
    expect(shared.eyebrow).toMatchObject({ size: 14, tracking: 0, family: "sans", case: "sentence" });
  });

  it("keeps the name face to headers and the wordmark", () => {
    expect(SOURCES.filter((f) => /<Crease|creaseVars/.test(text(f))).map((f) => relative(SRC, f))).toEqual([]);
    expect(text(join(SRC, "primitives/SettingsLayout.jsx"))).not.toMatch(/ds-name/);
    expect(text(join(SRC, "primitives/BrowseModal.jsx"))).not.toMatch(/ds-name/);
    expect(text(join(SRC, "features/VersionButton.module.css"))).toMatch(/\.brandMark\s*\{\s*font-size:\s*var\(--text-detail\)/);
  });

  it("names members in Geist 600 at 15 px", () => {
    const body = rules(text(join(SRC, "primitives/SettingsLayout.module.css"))).find((r) => r.selector === ".memberName").body;
    expect(body).toMatch(/font-size:\s*var\(--text-chat\)/);
    expect(body).toMatch(/font-weight:\s*var\(--fw-semibold\)/);
  });

  it("writes every sidebar status word in the same sans 11/500 style with tabular figures", () => {
    const sidebar = rules(text(join(SRC, "features/Sidebar.module.css")));
    for (const selector of [".rowTime", ".stateChip", ".phaseCount"]) {
      const body = sidebar.find((r) => r.selector.split("\n").pop() === selector).body;
      expect(body, selector).toMatch(/font-family:\s*var\(--font-sans\)/);
      expect(body, selector).toMatch(/font-weight:\s*var\(--fw-medium\)/);
      expect(body, selector).toMatch(/font-size:\s*var\(--text-meta\)/);
      expect(body, selector).toMatch(/tabular-nums/);
    }
    const ds = text(join(SRC, "styles/design-system.css"));
    expect(ds).toMatch(/\.sb-ts\s*\{ font-family: var\(--font-sans\);/);
  });
});
