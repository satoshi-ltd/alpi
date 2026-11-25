import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };
window.matchMedia ??= () => ({
  matches: false,
  addEventListener() {},
  removeEventListener() {},
  addListener() {},
  removeListener() {},
});

vi.mock("../lib/updater.js", () => ({
  describeUpdaterError: () => "",
  quitForUpdate: vi.fn(),
  applyPendingUpdate: vi.fn(),
  checkForUpdates: vi.fn(),
  subscribeUpdater: vi.fn(() => () => {}),
}));

import Sidebar from "./Sidebar.jsx";
import { markProfileRead } from "../hooks/useReadState.js";

const TS = Math.floor(Date.now() / 1000) - 300;

const BASE = {
  profiles: [
    { name: "doc", model: "a/b", latest_session: { updated_at: TS } },
    { name: "mind", model: "a/b", latest_session: { updated_at: TS } },
  ],
  workgroups: [
    { profile: "doc", id: "webfactory", name: "webfactory", mtime: TS },
    { profile: "doc", id: "roma", name: "roma", mtime: TS },
  ],
  view: { kind: "landing" },
  hostConnections: { active_id: "remote", connections: [] },
};

const row = (name) => screen.getByText(name).closest("button");
const nameSpan = (name) => row(name).querySelector(".sb-name");
const tsSpan = (name) => row(name).querySelector(".sb-ts");

beforeEach(() => {
  markProfileRead("remote", "mind", TS + 1);
});

describe("Sidebar unread mark", () => {
  it("draws no dot — unread is typographic now", () => {
    const { container } = render(<Sidebar {...BASE} />);
    expect(container.querySelector(".sb-unread-dot")).toBeNull();
    expect(screen.queryByLabelText("unread")).not.toBeInTheDocument();
  });

  it("says unread once, in the weight of the profile's name: the time keeps its resting weight", () => {
    render(<Sidebar {...BASE} />);
    expect(nameSpan("doc").className).toContain("is-unr");
    expect(tsSpan("doc").className).toBe("tnum sb-ts");
    const css = readFileSync(join(import.meta.dirname, "../styles/design-system.css"), "utf8");
    expect(css).toContain(".sb-name.is-unr { font-weight: var(--fw-semibold); color: var(--ink); }");
    expect(css).not.toMatch(/\.sb-ts\.is-unr/);
  });

  it("keeps the timestamp visible on an unread row instead of swapping it out", () => {
    render(<Sidebar {...BASE} />);
    expect(tsSpan("doc").textContent).toBe(tsSpan("mind").textContent);
  });

  it("leaves a read row at its resting weight", () => {
    render(<Sidebar {...BASE} />);
    expect(nameSpan("mind").className).not.toContain("is-unr");
    expect(tsSpan("mind").className).toBe("tnum sb-ts");
  });

  it("gives a workgroup no unread state: one that changed and was never opened reads like any other", () => {
    render(<Sidebar {...BASE} />);
    for (const name of ["roma", "webfactory"]) {
      expect(nameSpan(name).className).not.toContain("is-unr");
      expect(tsSpan(name).className).toBe("tnum sb-ts");
      expect(tsSpan(name).textContent).toBe(tsSpan("doc").textContent);
      expect(row(name).getAttribute("aria-label")).toBeNull();
    }
  });

  it("gives a pinned workgroup no unread state either", () => {
    render(<Sidebar {...BASE} pinned={{ profiles: [], workgroups: ["doc/roma"] }} />);
    const tile = screen.getByRole("button", { name: "roma" });
    expect(tile.dataset.unread).toBeUndefined();
    expect(screen.queryByRole("button", { name: /roma.*unread/ })).toBeNull();
  });

  it("keeps a pinned profile's unread in its accessible name", () => {
    render(<Sidebar {...BASE} pinned={{ profiles: ["doc"], workgroups: [] }} />);
    expect(screen.getByRole("button", { name: "doc, unread" }).dataset.unread).toBe("true");
  });

  it("announces unread now that no dot carries the label", () => {
    render(<Sidebar {...BASE} />);
    expect(row("doc").getAttribute("aria-label")).toBe("doc unread");
    expect(row("mind").getAttribute("aria-label")).toBeNull();
  });

  it("keeps the needs-provider hint as the accessible name — such a row is never unread", () => {
    render(<Sidebar {...BASE} profiles={[{ name: "doc", latest_session: { updated_at: TS } }]} />);
    expect(row("doc").getAttribute("aria-label")).toBe("@doc, needs provider — tap to set up");
  });
});
