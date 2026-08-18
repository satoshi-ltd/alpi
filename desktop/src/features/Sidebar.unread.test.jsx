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
  applyPendingUpdate: vi.fn(),
  checkForUpdates: vi.fn(),
  subscribeUpdater: vi.fn(() => () => {}),
}));

import Sidebar from "./Sidebar.jsx";
import { markProfileRead, markWorkgroupRead } from "../hooks/useReadState.js";

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
  view: { kind: "empty" },
  hostConnections: { active_id: "remote", connections: [] },
};

const row = (name) => screen.getByText(name).closest("button");
const nameSpan = (name) => row(name).querySelector(".sb-name");
const tsSpan = (name) => row(name).querySelector(".sb-ts");

beforeEach(() => {
  markProfileRead("remote", "mind", TS + 1);
  markWorkgroupRead("remote", "doc", "webfactory", TS + 1);
});

describe("Sidebar unread mark", () => {
  it("draws no dot — unread is typographic now", () => {
    const { container } = render(<Sidebar {...BASE} />);
    expect(container.querySelector(".sb-unread-dot")).toBeNull();
    expect(screen.queryByLabelText("unread")).not.toBeInTheDocument();
  });

  it("anchors unread at both ends — name weight on the left, timestamp on the right", () => {
    render(<Sidebar {...BASE} />);
    expect(nameSpan("doc").className).toContain("is-unr");
    expect(tsSpan("doc").className).toContain("is-unr");
  });

  it("keeps the timestamp visible on an unread row instead of swapping it out", () => {
    render(<Sidebar {...BASE} />);
    expect(tsSpan("doc").textContent).toBe(tsSpan("mind").textContent);
  });

  it("leaves a read row at its resting weight on both ends", () => {
    render(<Sidebar {...BASE} />);
    expect(nameSpan("mind").className).not.toContain("is-unr");
    expect(tsSpan("mind").className).not.toContain("is-unr");
  });

  it("marks an unread workgroup the same way, and a read one not at all", () => {
    render(<Sidebar {...BASE} />);
    expect(nameSpan("roma").className).toContain("is-unr");
    expect(tsSpan("roma").className).toContain("is-unr");
    expect(row("roma").getAttribute("aria-label")).toBe("roma unread");
    expect(nameSpan("webfactory").className).not.toContain("is-unr");
    expect(tsSpan("webfactory").className).not.toContain("is-unr");
    expect(row("webfactory").getAttribute("aria-label")).toBeNull();
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
