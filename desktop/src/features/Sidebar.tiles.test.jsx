import { afterEach, describe, it, expect, vi } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { cleanup, render, screen, fireEvent, within } from "@testing-library/react";

globalThis.ResizeObserver = class {
  constructor(cb) {
    this.cb = cb;
  }
  observe() {
    this.cb([{ contentRect: { height: 0 } }]);
  }
  unobserve() {}
  disconnect() {}
};
window.matchMedia ??= () => ({ matches: false, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} });

vi.mock("../lib/updater.js", () => ({
  describeUpdaterError: () => "",
  quitForUpdate: vi.fn(),
  applyPendingUpdate: vi.fn(),
  checkForUpdates: vi.fn(),
  subscribeUpdater: vi.fn(() => () => {}),
}));

import Sidebar from "./Sidebar.jsx";
import { MARK_SIZES } from "../../../common/agentMarks.mjs";
import { nameTone } from "../../../common/name.mjs";
import { palettes } from "../../../common/tokens.mjs";

afterEach(cleanup);

const TS = Math.floor(Date.now() / 1000);
const PROFILES = [
  { name: "default", is_default: true, model: "a/b", latest_session: { updated_at: TS - 60 } },
  { name: "doc", model: "a/b", accent: "#3899e2", shape: "drop", latest_session: { updated_at: TS - 120 } },
  { name: "yuri", model: "a/b", accent: "#3899e2", shape: "pill", paused: true },
  { name: "otto", model: "a/b", latest_session: { updated_at: TS - 300 } },
];
const BASE = { workgroups: [], view: { kind: "profile", profile: "doc" }, hostConnections: { active_id: "local", connections: [] } };
const group = () => screen.getByRole("group", { name: "Pinned" });

describe("Sidebar pinned tiles", () => {
  it("leads with the default profile and every pinned profile as 48 px marks with their names under them", () => {
    render(<Sidebar {...BASE} profiles={PROFILES} pinned={{ profiles: ["doc", "yuri"], workgroups: [] }} />);
    const tiles = within(group()).getAllByRole("button");
    expect(tiles.map((t) => t.querySelector(".ds-name").textContent)).toEqual(["alpi", "doc", "yuri"]);
    for (const tile of tiles) {
      const mark = tile.querySelector("[data-shape]");
      expect(mark.style.width).toBe(`${MARK_SIZES.tile}px`);
      expect(MARK_SIZES.tile).toBe(48);
      expect(tile.lastElementChild.className).toMatch(/ds-name/);
    }
    expect(screen.queryByText("otto").closest("button").classList.contains("ds-sb-row")).toBe(true);
  });

  it("sets a tile's name in its nameTone and marks the open profile with the neutral selection", () => {
    render(<Sidebar {...BASE} profiles={PROFILES} pinned={{ profiles: ["doc"], workgroups: [] }} />);
    const doc = within(group()).getByRole("button", { name: /^doc/ });
    expect(doc).toHaveAttribute("aria-current", "page");
    expect(doc.dataset.sel).toBe("true");
    const name = doc.querySelector(".ds-name");
    expect(name.style.getPropertyValue("--name-light")).toBe(nameTone("#3899e2", palettes.light.bgPane));
    const css = readFileSync(join(import.meta.dirname, "Sidebar.module.css"), "utf8");
    expect(css).toMatch(/\.tile\[data-sel\],\s*\.tile\[data-sel\]:hover \{\s*background: var\(--selected\);/);
    expect(css).toMatch(/\.tileMark \{[^}]*width: var\(--tile-mark\);/);
  });

  it("lays the tiles three to a row on the sidebar gutter, evenly spaced, wrapping in rows of three", () => {
    const css = readFileSync(join(import.meta.dirname, "Sidebar.module.css"), "utf8");
    const rule = (sel) => new RegExp(`(^|\\n)\\${sel} \\{([^}]*)\\}`).exec(css)?.[2] ?? "";
    const tiles = rule(".tiles");
    expect(tiles).toMatch(/grid-template-columns: repeat\(3, minmax\(0, 1fr\)\);/);
    expect(tiles).toMatch(/gap: var\(--sp-4\);/);
    expect(tiles).not.toMatch(/margin:[^;]*-/);
    const inset = (body) => /padding: ([^;]+);/.exec(body)[1].split(/\s+/)[1];
    expect(inset(rule(".nav"))).toBe("var(--sp-12)");
    expect(inset(rule(".actions"))).toBe(inset(rule(".nav")));
    const many = ["ana", "bo", "cy", "di", "ed"].map((name) => ({ name, model: "a/b", accent: "#3899e2", shape: "bell" }));
    render(<Sidebar {...BASE} profiles={many} pinned={{ profiles: many.map((p) => p.name), workgroups: [] }} />);
    expect(within(group()).getAllByRole("button")).toHaveLength(5);
    expect(within(group()).getByRole("button", { name: "ana" })).toBeTruthy();
  });

  it("says paused in a pinned workgroup tile's name", () => {
    render(<Sidebar {...BASE} profiles={PROFILES} workgroups={[{ profile: "doc", id: "crew", name: "launch-crew", paused: true }]} pinned={{ profiles: [], workgroups: ["doc/crew"] }} />);
    expect(within(group()).getByRole("button", { name: "launch-crew, paused" })).toBeTruthy();
  });

  it("keeps the context menu, the paused state and unpinning on a tile", () => {
    const onTogglePin = vi.fn();
    render(<Sidebar {...BASE} profiles={PROFILES} pinned={{ profiles: ["yuri"], workgroups: [] }} onOpenSettingsTarget={() => {}} onTogglePin={onTogglePin} />);
    const yuri = within(group()).getByRole("button", { name: /yuri/ });
    expect(yuri.dataset.state).toBe("paused");
    fireEvent.contextMenu(yuri);
    fireEvent.click(screen.getByText("Unpin from top"));
    expect(onTogglePin).toHaveBeenCalledWith("profiles", "yuri");
  });

  it("opens a profile from its tile", () => {
    const onOpenProfile = vi.fn();
    render(<Sidebar {...BASE} profiles={PROFILES} pinned={{ profiles: ["doc"], workgroups: [] }} onOpenProfile={onOpenProfile} />);
    fireEvent.click(within(group()).getByRole("button", { name: /^alpi/ }));
    expect(onOpenProfile).toHaveBeenCalledWith(PROFILES[0]);
  });
});

describe("Sidebar head and rows", () => {
  it("leaves the connection switcher alone at the top, with no icon buttons and no new-session button", () => {
    const { container } = render(<Sidebar {...BASE} profiles={PROFILES} onOpenPalette={vi.fn()} onNewSessionWith={vi.fn()} />);
    const head = container.querySelector('[class*="actionSection"]');
    expect(head.querySelectorAll("button").length).toBe(head.querySelectorAll('[class*="connectionSlot"] button').length);
    expect(screen.queryByRole("button", { name: "New session" })).toBeNull();
    expect(container.innerHTML).not.toContain('data-icon="pencil"');
  });

  it("puts Search in the footer beside settings, notifications, activity and theme, keeping its shortcut", () => {
    const onOpenPalette = vi.fn();
    const { container } = render(<Sidebar {...BASE} profiles={PROFILES} onOpenPalette={onOpenPalette} onOpenSettings={vi.fn()} />);
    const footer = container.querySelector('[class*="footer"]');
    const search = within(footer).getByRole("button", { name: "Search profiles, sessions and commands" });
    expect(search.className).toMatch(/footerIcon/);
    expect(search.parentElement.querySelector(".ds-tip-body").textContent).toMatch(/^Search · .+K$/);
    fireEvent.click(search);
    expect(onOpenPalette).toHaveBeenCalled();
  });

  it("draws 40 px rows with 24 px marks and 15 px names, under 14 px sentence-case section labels", () => {
    render(<Sidebar {...BASE} profiles={PROFILES} />);
    expect(screen.getByText("otto").closest("button").querySelector("[data-shape]").style.width).toBe(`${MARK_SIZES.row}px`);
    expect(MARK_SIZES.row).toBe(24);
    const ds = readFileSync(join(import.meta.dirname, "../styles/design-system.css"), "utf8");
    expect(ds).toMatch(/\.ds-sb-row, \.sb-row \{[^}]*height: var\(--row-h\);/);
    expect(ds).toMatch(/\.sb-name\s+\{[^}]*font-size: var\(--text-ui\);/);
    const tokens = readFileSync(join(import.meta.dirname, "../styles/tokens.css"), "utf8");
    expect(tokens).toMatch(/--sidebar-w: 272px;/);
    expect(tokens).toMatch(/--row-h: 40px;/);
    expect(tokens).toMatch(/--text-ui:\s*15px;/);
    expect(screen.getByText("Profiles").className).toMatch(/eyebrow/);
  });
});

describe("Sidebar tiles ignore the pointer", () => {
  it("never turns a tile toward the pointer: no gaze, no hover turn, the same transforms after the pointer moves over it", async () => {
    const { trackedCount } = await import("../lib/gaze.js");
    render(<Sidebar {...BASE} view={{ kind: "profile", profile: "default" }} profiles={PROFILES} pinned={{ profiles: ["doc"], workgroups: [] }} />);
    const tiles = within(group()).getAllByRole("button");
    const poses = () => tiles.map((t) => [...t.querySelectorAll("[data-shape], [data-shape] span, [data-shape] svg")].map((n) => `${n.style.transform}|${n.style.getPropertyValue("--gx")}|${n.style.getPropertyValue("--gy")}`).join(";"));
    const before = poses();
    for (const tile of tiles) {
      const box = tile.querySelector("[data-shape]");
      fireEvent.mouseEnter(tile);
      fireEvent.mouseOver(box);
      fireEvent.mouseMove(window, { clientX: 400, clientY: 20 });
      fireEvent.mouseMove(box, { clientX: 2, clientY: 2 });
    }
    expect(poses()).toEqual(before);
    expect(group().querySelector("[data-watch]")).toBeNull();
    expect(trackedCount()).toBe(0);
    const injected = [...document.querySelectorAll("style[data-agent-marks]")].map((s) => s.textContent).join("");
    expect(injected).toContain("vt-turn-idle");
    expect(injected).not.toMatch(/:hover/);
  });
});
