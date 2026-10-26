import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { STATUS_WORDS, statusDot, statusKind } from "../lib/statusVocab.js";

const read = (file) => readFileSync(join(import.meta.dirname, "..", file), "utf8");

describe("dialog anatomy", () => {
  it("builds modals from the dialog padding tokens", () => {
    const css = read("primitives/Modal.module.css");
    expect(css).toMatch(/\.modal \{[^}]*padding: var\(--dialog-pad\) 0 0/);
    expect(css).toMatch(/\.titleRow \{[^}]*padding: 0 var\(--dialog-pad\)/);
    expect(css).toMatch(/\.content \{[^}]*padding: 0 var\(--dialog-pad\) var\(--dialog-pad\)/);
    expect(css).toMatch(/\[data-dialog-footer\] \{[^}]*padding: var\(--dialog-foot-pad\)/);
    expect(css).toMatch(/\.title \{[^}]*font-size: var\(--text-dialog-title-size\)/);
  });

  it.each([
    "primitives/Panels.module.css",
    "features/ActivityPanel.module.css",
    "features/ShortcutsSheet.module.css",
    "features/sessions/ManageSessionsModal.module.css",
    "primitives/BrowseModal.module.css",
  ])("%s draws its panel header with --panel-head-pad", (file) => {
    expect(read(file)).toMatch(/padding: var\(--panel-head-pad\)/);
  });

  it("titles panel headers at 13 px", () => {
    expect(read("primitives/Panels.module.css")).toMatch(/\.panelTitle \{[^}]*font-size: var\(--text-ui\)/);
    expect(read("features/ShortcutsSheet.module.css")).toMatch(/\.title \{[^}]*font-size: var\(--text-ui\)/);
  });

  it("indents detail panes by --detail-gutter", () => {
    expect(read("primitives/BrowseModal.module.css")).toMatch(/var\(--detail-gutter\)/);
    expect(read("features/NotificationsModal.module.css")).toMatch(/var\(--detail-gutter\)/);
  });

  it.each([
    ["features/ScheduleModal.module.css", /\.fields \{[^}]*grid-template-columns: var\(--def-col\) 1fr/],
    ["features/SkillsModal.module.css", /\.fmLabel \{[^}]*width: var\(--def-col\)/],
    ["features/NotificationBody.module.css", /\.fact \{[^}]*grid-template-columns: var\(--def-col\) 1fr/],
  ])("%s labels details in the shared 84 px column", (file, pattern) => {
    expect(read(file)).toMatch(pattern);
    expect(read("styles/tokens.css")).toMatch(/--def-col: 84px/);
  });
});

describe("status vocabulary", () => {
  it("collapses every status word onto active, paused, attention and failed", () => {
    expect(STATUS_WORDS).toEqual(["active", "paused", "attention", "failed"]);
    const kinds = ["active", "running", "paused", "inactive", "lint", "over", "failed", "invalid"].map(statusKind);
    expect(kinds).toEqual(["active", "active", "paused", "attention", "attention", "attention", "failed", "failed"]);
  });

  it("draws filled for ok, hollow for off and red for attention and failure", () => {
    expect(["active", "paused", "inactive", "invalid"].map(statusDot)).toEqual(["filled", "hollow", "red", "red"]);
  });
});
