import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };
globalThis.Element.prototype.scrollTo ??= () => {};

const h = vi.hoisted(() => ({ invoke: vi.fn(), listeners: new Set() }));
vi.mock("@tauri-apps/api/core", () => ({ invoke: h.invoke }));
vi.mock("../lib/daemon-bus.js", () => ({
  subscribeDaemonEvent: (fn) => { h.listeners.add(fn); return () => h.listeners.delete(fn); },
}));
vi.mock("../primitives/Notification.jsx", () => ({ useNotify: () => () => {} }));

import ProfilePanels from "./ProfilePanels.jsx";

const OWNER = { name: "scout", fold: "house", accent: "#cc4422" };
const ATT = {
  memory: [{ file: "AGENT.md", used: 9454, limit: 8000, pct: 118, over: true }],
  skills: [{ name: "review-digest", category: "research", problem: "lint", message: "SKILL.md line 4: bad name" }],
  schedules: [],
  counts: { memory: 1, skills: 1, schedules: 0 },
  total: 2,
};
const SKILLS = [
  { name: "hotel-intake", category: "research", description: "Intake", size: 100, status: "active", reason: "" },
  { name: "review-digest", category: "research", description: "Digest", size: 100, status: "invalid", reason: "lint" },
];

let attention;

beforeEach(() => {
  h.listeners.clear();
  attention = ATT;
  h.invoke.mockReset();
  h.invoke.mockImplementation(async (cmd) => {
    if (cmd === "profile_attention") {
      if (attention === "absent") throw new Error("method-not-found");
      return attention;
    }
    if (cmd === "profile_memory") return { "AGENT.md": "who I am", "MEMORY.md": "", "USER.md": "" };
    if (cmd === "memory_usage") return { "AGENT.md": { used: 9454, limit: 8000, pct: 118, over: true }, "USER.md": { used: 10, limit: 3000, pct: 0, over: false } };
    if (cmd === "memory_read") return { text: "who I am", rev: "r1" };
    if (cmd === "profile_skills") return SKILLS;
    if (cmd === "profile_skill_read") return { name: "review-digest", category: "research", description: "Digest", status: "invalid", reason: "lint", tree: [], body: "b", requires: [], tools: [], platforms: [], keywords: [] };
    return [];
  });
});

const mount = (section) => render(<ProfilePanels section={section} onSection={() => {}} onClose={() => {}} owner={OWNER} profile="scout" connectionId={null} canEdit />);

describe("window tabs", () => {
  it("shows a red count on every flagged tab, open or not, and none on a healthy one", async () => {
    mount("memory");
    const memory = await screen.findByRole("tab", { name: /Memories/ });
    await waitFor(() => expect(screen.getByRole("tab", { name: "Memories, 1 file needs you" })).toBeTruthy());
    expect(screen.getByRole("tab", { name: "Skills, 1 skill needs you" })).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Tools" })).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Schedules" })).toBeTruthy();
    expect(memory.getAttribute("aria-selected")).toBe("true");
  });

  it("shows nothing and keeps today's look when the daemon lacks the verb", async () => {
    attention = "absent";
    mount("memory");
    await screen.findByRole("tab", { name: /Memories/ });
    await waitFor(() => expect(h.invoke).toHaveBeenCalledWith("profile_attention", { profile: "scout", connectionId: null }));
    expect(screen.queryByRole("tab", { name: /needs you/ })).toBeNull();
    expect(screen.queryByRole("group")).toBeNull();
  });

  it("refetches on attention.changed", async () => {
    mount("memory");
    await waitFor(() => expect(screen.getByRole("tab", { name: "Memories, 1 file needs you" })).toBeTruthy());
    attention = { ...ATT, memory: [], counts: { memory: 0, skills: 1, schedules: 0 }, total: 1 };
    await act(async () => { h.listeners.forEach((fn) => fn({ payload: { frame: { event: "attention.changed", data: { profile: "scout" } } } })); });
    await waitFor(() => expect(screen.queryByRole("tab", { name: "Memories, 1 file needs you" })).toBeNull());
  });
});

describe("memory panel", () => {
  it("says over in the row and opens on the banner whose Edit enters edit mode", async () => {
    mount("memory");
    const banner = await screen.findByRole("group", { name: /Over its limit/ });
    expect(banner.textContent).toMatch(/Over its limit by 1,454 characters/);
    expect(screen.getAllByRole("option")[0].textContent).toMatch(/over/);
    expect(screen.getAllByRole("option")[1].textContent).not.toMatch(/over|full/);
    await act(async () => { fireEvent.click(banner.querySelector("button")); });
    expect(await screen.findByLabelText("Edit AGENT.md")).toBeTruthy();
  });

  it("shows no banner for a healthy file", async () => {
    attention = { ...ATT, memory: [] };
    mount("memory");
    await screen.findAllByRole("option");
    expect(screen.queryByRole("group")).toBeNull();
  });
});

describe("skills panel", () => {
  it("lifts a flagged skill under Needs you with its word and opens on the banner", async () => {
    mount("skills");
    expect(await screen.findByText("Needs you · 1")).toBeTruthy();
    const rows = screen.getAllByRole("option");
    expect(rows[0].textContent).toMatch(/review-digest.*lint/);
    expect(rows[1].textContent).toMatch(/hotel-intake/);
    await waitFor(() => expect(screen.getByRole("group").textContent).toMatch(/Does not pass lint.*bad name/));
  });

  it("keeps the plain categories and no banner when nothing is flagged", async () => {
    attention = { ...ATT, skills: [] };
    mount("skills");
    await screen.findAllByRole("option");
    expect(screen.queryByText(/Needs you/)).toBeNull();
    expect(screen.queryByText("lint", { selector: "span" })).toBeNull();
  });
});

describe("attention lifecycle", () => {
  const view = (profile, connectionId = null, section = "memory") => (
    <ProfilePanels section={section} onSection={() => {}} onClose={() => {}} owner={OWNER} profile={profile} connectionId={connectionId} canEdit />
  );

  it("never shows another profile's or connection's badges and banner", async () => {
    let release;
    const { rerender } = render(view("scout"));
    await screen.findByRole("tab", { name: "Memories, 1 file needs you" });
    attention = { memory: [], skills: [], schedules: [], counts: {}, total: 0 };
    h.invoke.mockImplementation(async (cmd) => {
      if (cmd === "profile_attention") return new Promise((r) => { release = () => r(attention); });
      if (cmd === "profile_memory") return { "AGENT.md": "x", "MEMORY.md": "", "USER.md": "" };
      if (cmd === "memory_usage") return { "AGENT.md": { used: 9454, limit: 8000, pct: 118, over: true } };
      return [];
    });
    rerender(view("other"));
    expect(screen.queryByRole("tab", { name: /needs you/ })).toBeNull();
    expect(screen.queryByRole("group")).toBeNull();
    await act(async () => { release(); });
    rerender(view("other", "c2"));
    expect(screen.queryByRole("tab", { name: /needs you/ })).toBeNull();
  });

  it("keeps the last value through a transient error and hides on method-not-found", async () => {
    render(view("scout"));
    await screen.findByRole("tab", { name: "Memories, 1 file needs you" });
    attention = "absent";
    const fail = (msg) => h.invoke.mockImplementation(async (cmd) => {
      if (cmd === "profile_attention") throw new Error(msg);
      if (cmd === "profile_memory") return { "AGENT.md": "x", "MEMORY.md": "", "USER.md": "" };
      return [];
    });
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    fail("socket closed");
    await act(async () => { h.listeners.forEach((fn) => fn({ payload: { frame: { event: "memory_changed", data: { profile: "scout" } } } })); vi.advanceTimersByTime(400); });
    vi.useRealTimers();
    expect(screen.getByRole("tab", { name: "Memories, 1 file needs you" })).toBeTruthy();
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    fail("rpc -32601 method not found");
    await act(async () => { h.listeners.forEach((fn) => fn({ payload: { frame: { event: "memory_changed", data: { profile: "scout" } } } })); vi.advanceTimersByTime(400); });
    vi.useRealTimers();
    await waitFor(() => expect(screen.queryByRole("tab", { name: /needs you/ })).toBeNull());
  });

  it("coalesces a burst of events into one call and ignores tab switches", async () => {
    const { rerender } = render(view("scout"));
    await screen.findByRole("tab", { name: "Memories, 1 file needs you" });
    const calls = () => h.invoke.mock.calls.filter(([c]) => c === "profile_attention").length;
    expect(calls()).toBe(1);
    rerender(view("scout", null, "skills"));
    await screen.findByRole("tab", { name: "Skills, 1 skill needs you" });
    expect(calls()).toBe(1);
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    await act(async () => {
      for (let i = 0; i < 20; i++) h.listeners.forEach((fn) => fn({ payload: { frame: { event: "schedule.changed", data: { profile: "scout" } } } }));
      vi.advanceTimersByTime(400);
    });
    vi.useRealTimers();
    await waitFor(() => expect(calls()).toBe(2));
  });

  it("does not move the skill selection when attention refetches after the first lift", async () => {
    render(view("scout", null, "skills"));
    await waitFor(() => expect(screen.getByRole("group").textContent).toMatch(/lint/));
    fireEvent.click(screen.getAllByRole("option").find((r) => /hotel-intake/.test(r.textContent)));
    await waitFor(() => expect(screen.queryByRole("group")).toBeNull());
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    attention = { ...ATT, total: 3 };
    await act(async () => { h.listeners.forEach((fn) => fn({ payload: { frame: { event: "attention.changed", data: { profile: "scout" } } } })); vi.advanceTimersByTime(400); });
    vi.useRealTimers();
    await new Promise((r) => setTimeout(r, 20));
    expect(screen.queryByRole("group")).toBeNull();
  });
  it("treats an empty connection id and null as the same connection", async () => {
    const { rerender } = render(view("scout", ""));
    await screen.findByRole("tab", { name: "Memories, 1 file needs you" });
    const calls = () => h.invoke.mock.calls.filter(([c]) => c === "profile_attention").length;
    expect(calls()).toBe(1);
    rerender(view("scout", null));
    await new Promise((r) => setTimeout(r, 20));
    expect(calls()).toBe(1);
    expect(screen.getByRole("tab", { name: "Memories, 1 file needs you" })).toBeTruthy();
  });
});
