import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import TrayApp from "./TrayApp.jsx";

const NOW = Date.now();
const need = (i, over = {}) => ({
  id: `r${i}`,
  kind: "approval",
  profile: `p${i}`,
  label: `p${i}`,
  title: "wants to run a command",
  ts: NOW / 1000 - 120,
  shape: "twin",
  accent: null,
  deeplink: { kind: "approval", profile: `p${i}`, id: `r${i}`, connection_id: "c1" },
  ...over,
});
const snap = (over = {}) => ({
  state: "quiet",
  member: false,
  unread: 0,
  update: null,
  needs: { total: 0, approvals: 0, questions: 0, rows: [] },
  failing: { jobs: 0, profileCount: 0, profiles: [] },
  running: { count: 0, rows: [] },
  offline: null,
  ...over,
});

let handlers;
let current;
const calls = (name) => invoke.mock.calls.filter(([n]) => n === name);

async function mount(snapshot) {
  current = snapshot;
  const view = render(<TrayApp />);
  await waitFor(() => expect(handlers["tray-state"]).toBeTruthy());
  await act(async () => {});
  return view;
}
const push = (snapshot) => act(() => handlers["tray-state"]({ payload: snapshot }));

beforeEach(() => {
  handlers = {};
  current = null;
  invoke.mockReset();
  invoke.mockImplementation(async (name) => (name === "tray_state" ? current : null));
  listen.mockReset();
  listen.mockImplementation(async (name, cb) => {
    handlers[name] = cb;
    return () => {};
  });
  localStorage.clear();
  document.documentElement.removeAttribute("data-mode");
});

describe("TrayApp states", () => {
  it("renders All quiet from the stored snapshot with the footer", async () => {
    await mount(snap());
    expect(screen.getByRole("heading", { name: "All quiet" })).toBeInTheDocument();
    expect(screen.getByText("Nothing needs you")).toBeInTheDocument();
    for (const name of ["Open alpi", "Settings", "Quit alpi", "Notifications"]) {
      expect(screen.getByRole("button", { name })).toBeInTheDocument();
    }
  });

  it("renders needs-you rows, the failing banner, the running count and the unread bell", async () => {
    await mount(snap({
      state: "needs",
      unread: 2,
      needs: { total: 2, approvals: 2, questions: 0, rows: [need(0), need(1)] },
      failing: { jobs: 3, profileCount: 2, profiles: ["a", "b"] },
      running: { count: 2, rows: [] },
    }));
    expect(screen.getByRole("heading", { name: "2 need you" })).toBeInTheDocument();
    expect(screen.getByText("2 running")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /^Review:/ })).toHaveLength(2);
    expect(screen.getByRole("button", { name: "3 jobs failed in 24 h, a and b. Open alpi" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Running, 2/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Notifications · 2 unread" })).toBeInTheDocument();
  });

  it("renders four rows and the N more line", async () => {
    await mount(snap({ state: "needs", needs: { total: 7, approvals: 5, questions: 2, rows: [0, 1, 2, 3].map((i) => need(i)) } }));
    expect(screen.getAllByRole("button", { name: /^Review:/ })).toHaveLength(4);
    expect(screen.getByRole("button", { name: "3 more · Open alpi" })).toBeInTheDocument();
    expect(screen.getByText("5 approvals, 2 questions")).toBeInTheDocument();
  });

  it("renders running, failing, update, starting and stopped", async () => {
    await mount(snap({ state: "running", running: { count: 1, rows: [{ id: "t", profile: "alpi", label: "alpi", title: "Deploys", ts: Date.now() / 1000 - 120, shape: null, accent: null, deeplink: { kind: "chat", profile: "alpi", id: "s1", connection_id: "c" } }] } }));
    expect(screen.getByRole("heading", { name: "Alpi is working" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Deploys, alpi · running, 2m/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Running, 1/ })).toBeNull();
    await push(snap({ state: "failing", failing: { jobs: 3, profileCount: 2, profiles: ["sentinel", "clonara"] } }));
    expect(screen.getByRole("heading", { name: "3 jobs failing" })).toBeInTheDocument();
    expect(screen.getByText("3 jobs failed in 24 h")).toBeInTheDocument();
    expect(screen.getByText("sentinel and clonara")).toBeInTheDocument();
    await push(snap({ update: { version: "0.9.3", busy: false } }));
    expect(screen.getByText("alpi 0.9.3 is ready")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Restart to update" })).toHaveTextContent("Restart");
    await push(snap({ state: "starting" }));
    expect(screen.getByRole("heading", { name: "Starting alpi…" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Start requested");
    expect(screen.queryByRole("button", { name: "Start alpi" })).toBeNull();
    await push(snap({ state: "offline", offline: { local: true, canStart: true, absent: false } }));
    expect(screen.getByRole("heading", { name: "alpi isn’t running" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start alpi" })).toBeInTheDocument();
  });

  it("hides the bell for a member and draws no scheduled counts", async () => {
    await mount(snap({ member: true }));
    expect(screen.queryByRole("button", { name: /Notifications/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /failed in 24 h/ })).toBeNull();
    expect(screen.queryByText("Tomorrow")).toBeNull();
  });

  it("reads Connecting before the first snapshot", async () => {
    await mount(null);
    expect(screen.getByRole("heading", { name: "Connecting…" })).toBeInTheDocument();
  });

  it("replaces what it draws when a new snapshot arrives", async () => {
    await mount(snap());
    await push(snap({ state: "needs", needs: { total: 1, approvals: 1, questions: 0, rows: [need(0)] } }));
    expect(screen.getByRole("heading", { name: "P0 needs you" })).toBeInTheDocument();
  });

  it("never calls a daemon verb or reads files itself", async () => {
    await mount(snap({ state: "needs", needs: { total: 1, approvals: 1, questions: 0, rows: [need(0)] } }));
    const allowed = new Set(["tray_state", "resize_tray", "hide_tray", "show_main", "open_settings", "open_notifications", "restart_to_update", "quit_app", "start_alpi"]);
    for (const [name] of invoke.mock.calls) expect(allowed.has(name), name).toBe(true);
  });
});

describe("TrayApp actions", () => {
  const needing = () => snap({ state: "needs", needs: { total: 1, approvals: 1, questions: 0, rows: [need(0)] }, failing: { jobs: 1, profileCount: 1, profiles: ["x"] }, running: { count: 1, rows: [] }, update: { version: "0.9.3", busy: false }, unread: 1 });

  it("Review opens the request through its deeplink", async () => {
    await mount(needing());
    fireEvent.click(screen.getByRole("button", { name: /^Review:/ }));
    expect(calls("show_main")).toEqual([["show_main", { deeplink: { kind: "approval", profile: "p0", id: "r0", connection_id: "c1" } }]]);
  });

  it("clicking the row text opens the same request", async () => {
    await mount(needing());
    fireEvent.click(screen.getByText("wants to run a command"));
    expect(calls("show_main")[0][1].deeplink.id).toBe("r0");
  });

  it("Open alpi, the counts and N more bring the window forward with no deeplink", async () => {
    await mount(needing());
    fireEvent.click(screen.getByRole("button", { name: "Open alpi" }));
    fireEvent.click(screen.getByRole("button", { name: /failed in 24 h/ }));
    fireEvent.click(screen.getByRole("button", { name: /Running, 1/ }));
    expect(calls("show_main").map((c) => c[1])).toEqual([{ deeplink: null }, { deeplink: null }, { deeplink: null }]);
  });

  it("the footer buttons call their own commands", async () => {
    await mount(needing());
    fireEvent.click(screen.getByRole("button", { name: "Settings" }));
    fireEvent.click(screen.getByRole("button", { name: "Notifications · 1 unread" }));
    fireEvent.click(screen.getByRole("button", { name: "Quit alpi" }));
    fireEvent.click(screen.getByRole("button", { name: "Restart to update" }));
    for (const name of ["open_settings", "open_notifications", "quit_app", "restart_to_update"]) expect(calls(name)).toHaveLength(1);
  });

  it("Start alpi starts the daemon and shows Starting while it waits", async () => {
    let finish;
    invoke.mockImplementation(async (name) => {
      if (name === "tray_state") return snap({ state: "offline", offline: { local: true, canStart: true, absent: false } });
      if (name === "start_alpi") return new Promise((resolve) => { finish = resolve; });
      return null;
    });
    render(<TrayApp />);
    const start = await screen.findByRole("button", { name: "Start alpi" });
    fireEvent.click(start);
    expect(await screen.findByRole("heading", { name: "Starting alpi…" })).toBeInTheDocument();
    expect(calls("start_alpi")).toHaveLength(1);
    await act(async () => finish("started"));
    expect(screen.queryByRole("heading", { name: "Starting alpi…" })).toBeNull();
  });

  it("a failed start says why and offers Start alpi again", async () => {
    invoke.mockImplementation(async (name) => {
      if (name === "tray_state") return snap({ state: "offline", offline: { local: true, canStart: true, absent: false } });
      if (name === "start_alpi") throw new Error("no supervisor");
      return null;
    });
    render(<TrayApp />);
    fireEvent.click(await screen.findByRole("button", { name: "Start alpi" }));
    expect(await screen.findByText("no supervisor")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start alpi" })).toBeInTheDocument();
  });
});

describe("TrayApp window behaviour", () => {
  it("Escape hides the popover", async () => {
    await mount(snap());
    fireEvent.keyDown(window, { key: "Escape" });
    expect(calls("hide_tray")).toHaveLength(1);
  });

  it("losing the window hides it too", async () => {
    await mount(snap());
    fireEvent.blur(window);
    expect(calls("hide_tray")).toHaveLength(1);
  });

  it("other keys leave it open", async () => {
    await mount(snap());
    fireEvent.keyDown(window, { key: "a" });
    fireEvent.keyDown(window, { key: "Enter" });
    expect(calls("hide_tray")).toHaveLength(0);
  });

  const STATES = {
    needs: () => snap({ state: "needs", unread: 1, needs: { total: 1, approvals: 1, questions: 0, rows: [need(0)] }, update: { version: "0.9.3", busy: false } }),
    stopped: () => snap({ state: "offline", offline: { local: true, canStart: true, absent: false } }),
    update: () => snap({ update: { version: "0.9.3", busy: false } }),
    quiet: () => snap(),
  };
  const FIRST = { needs: /^Review:/, stopped: /^Start alpi$/, update: /^Restart to update$/, quiet: /^Open alpi$/ };

  it.each(Object.keys(STATES))("focuses the root, not a control, when shown (%s)", async (key) => {
    await mount(STATES[key]());
    await act(async () => handlers["tray-shown"]());
    const root = screen.getByRole("main").parentElement;
    expect(root).toHaveAttribute("tabindex", "-1");
    expect(document.activeElement).toBe(root);
    for (const button of screen.getAllByRole("button")) {
      expect(button).not.toHaveFocus();
      let visible = false;
      try { visible = button.matches(":focus-visible"); } catch { visible = false; }
      expect(visible).toBe(false);
    }
  });

  it.each(Object.keys(STATES))("makes the first Tab land on the first actionable control (%s)", async (key) => {
    await mount(STATES[key]());
    const buttons = [...document.querySelectorAll("button:not(:disabled)")];
    expect(buttons.every((b) => b.tabIndex >= 0)).toBe(true);
    expect(buttons[0]).toHaveAccessibleName(FIRST[key]);
  });

  it("does not focus anything on mount before it is shown", async () => {
    await mount(STATES.needs());
    expect(document.activeElement).toBe(document.body);
  });

  it("asks the window to fit its content", async () => {
    const heights = [];
    let observe;
    vi.stubGlobal("ResizeObserver", class {
      constructor(cb) { observe = cb; }
      observe() {}
      disconnect() {}
    });
    const spy = vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(() => ({ height: 123.2, width: 342, top: 0, left: 0, right: 342, bottom: 123.2 }));
    await mount(snap());
    for (const [name, args] of calls("resize_tray")) heights.push(args.height);
    expect(heights).toEqual([124]);
    observe();
    expect(calls("resize_tray")).toHaveLength(1);
    spy.mockImplementation(() => ({ height: 200, width: 342, top: 0, left: 0, right: 342, bottom: 200 }));
    observe();
    expect(calls("resize_tray").at(-1)[1]).toEqual({ height: 200 });
    spy.mockRestore();
    vi.unstubAllGlobals();
  });

  it("reloads the snapshot every time it is shown", async () => {
    await mount(snap());
    const before = calls("tray_state").length;
    current = snap({ state: "running", running: { count: 3, rows: [] } });
    await act(async () => handlers["tray-shown"]());
    await waitFor(() => expect(screen.getByRole("heading", { name: "3 working" })).toBeInTheDocument());
    expect(calls("tray_state").length).toBe(before + 1);
  });

  it("labels the surface for assistive tech", async () => {
    await mount(snap());
    expect(screen.getByRole("main", { name: "Alpi status" })).toBeInTheDocument();
    expect(within(screen.getByRole("main")).getByRole("contentinfo")).toBeInTheDocument();
  });
});

describe("TrayApp theme", () => {
  it("applies the theme the main window stored", async () => {
    localStorage.setItem("alpi.theme", "dark");
    await mount(snap());
    expect(document.documentElement.getAttribute("data-mode")).toBe("dark");
  });

  it("leaves system to the colour scheme media query", async () => {
    await mount(snap());
    expect(document.documentElement.hasAttribute("data-mode")).toBe(false);
  });

  it("follows a change made in the main window while it is open", async () => {
    await mount(snap());
    localStorage.setItem("alpi.theme", "light");
    act(() => { window.dispatchEvent(new StorageEvent("storage", { key: "alpi.theme" })); });
    expect(document.documentElement.getAttribute("data-mode")).toBe("light");
    localStorage.setItem("alpi.theme", "dark");
    act(() => { window.dispatchEvent(new StorageEvent("storage", { key: "alpi.theme" })); });
    expect(document.documentElement.getAttribute("data-mode")).toBe("dark");
    localStorage.removeItem("alpi.theme");
    act(() => { window.dispatchEvent(new StorageEvent("storage", { key: null })); });
    expect(document.documentElement.hasAttribute("data-mode")).toBe(false);
  });

  it("ignores unrelated storage keys", async () => {
    localStorage.setItem("alpi.theme", "dark");
    await mount(snap());
    localStorage.setItem("alpi.theme", "light");
    act(() => { window.dispatchEvent(new StorageEvent("storage", { key: "other" })); });
    expect(document.documentElement.getAttribute("data-mode")).toBe("dark");
  });

  it("re-reads the stored theme when the window regains focus", async () => {
    await mount(snap());
    localStorage.setItem("alpi.theme", "dark");
    fireEvent.focus(window);
    expect(document.documentElement.getAttribute("data-mode")).toBe("dark");
  });
});

describe("TrayApp schedule", () => {
  const AT = new Date(Date.now() + 2 * 3600e3 + 60e3).toISOString();
  const row = (i, over = {}) => ({ id: `c/p/j${i}`, title: `Job ${i}`, label: "scribe", at: AT, source: "casa", shape: null, accent: null, deeplink: { kind: "settings", profile: "scribe", id: "schedules", connection_id: "c" }, ...over });

  it("lists the next jobs under their day with the profile, the connection and the time on the name line", async () => {
    await mount(snap({ next: { rows: [row(0), row(1, { source: "mirai" })] } }));
    const group = screen.getByRole("region", { name: /^(Later today|Tomorrow)$/ });
    expect(within(group).getByRole("button", { name: /^Job 0, scribe · casa, in 2h\. Open schedule$/ })).toBeInTheDocument();
    expect(within(group).getByRole("button", { name: /Job 1, scribe · mirai/ })).toBeInTheDocument();
    expect(screen.getByText("Nothing needs you · next in 2h")).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("labels every section, even when it is the only one", async () => {
    await mount(snap({ next: { rows: [row(0)] } }));
    expect(document.querySelectorAll("section p").length).toBe(1);
    const turn = { id: "t", profile: "alpi", label: "alpi", title: "Deploys", ts: Date.now() / 1000 - 120, shape: null, accent: null, deeplink: null };
    await push(snap({ state: "running", running: { count: 1, rows: [turn] } }));
    expect(screen.getByText("Running")).toBeInTheDocument();
  });

  it("opens the schedule of the row on its connection", async () => {
    await mount(snap({ next: { rows: [row(0)] } }));
    fireEvent.click(screen.getByRole("button", { name: /Job 0/ }));
    expect(invoke).toHaveBeenCalledWith("show_main", { deeplink: { kind: "settings", profile: "scribe", id: "schedules", connection_id: "c" } });
  });

  it("says nothing is scheduled for an admin with no job", async () => {
    await mount(snap({ next: null }));
    expect(screen.getByText("Nothing needs you, nothing scheduled")).toBeInTheDocument();
  });

  it("keeps the container focused on open in the quiet state", async () => {
    await mount(snap({ next: { rows: [row(0)] } }));
    await act(async () => handlers["tray-shown"]());
    expect(document.activeElement).toBe(screen.getByRole("main").parentElement);
  });
});

describe("TrayApp marks and names", () => {
  const head = () => screen.getByRole("banner").querySelector("[data-mark]");
  const turn = { id: "t", profile: "sentinel", label: "sentinel", title: "Review", ts: Date.now() / 1000 - 60, shape: "bell", accent: "#3b6fe0", deeplink: null };
  const job = { id: "j", title: "Brief", label: "doc", at: new Date(Date.now() + 3600e3 + 60e3).toISOString(), source: null, shape: "squircle", accent: "#df4b9d", deeplink: null };

  it.each([
    ["quiet", snap(), "idle"],
    ["needs", snap({ state: "needs", needs: { total: 1, approvals: 1, questions: 0, rows: [need(0)] } }), "needs"],
    ["running", snap({ state: "running", running: { count: 1, rows: [turn] } }), "working"],
    ["failing", snap({ state: "failing", failing: { jobs: 1, profileCount: 1, profiles: ["x"] } }), "failed"],
    ["offline", snap({ state: "offline", offline: { local: true, canStart: true } }), "offline"],
    ["starting", snap({ state: "starting" }), "busy"],
    ["connecting", snap({ state: "connecting" }), "busy"],
    ["online", snap({ state: "online" }), "idle"],
  ])("heads %s with Twin at 40 wearing the state", async (_, snapshot, state) => {
    await mount(snapshot);
    expect(head()).toHaveAttribute("data-shape", "twin");
    expect(head()).toHaveAttribute("data-state", state);
    expect(head().style.width).toBe("40px");
  });

  it("leads each row with the profile's 24 px mark, live only on rows that are live", async () => {
    await mount(snap({ state: "needs", needs: { total: 1, approvals: 1, questions: 0, rows: [need(0, { shape: "heart", accent: "#df4b9d" })] }, running: { count: 1, rows: [turn] }, next: { rows: [job] } }));
    const mark = (kind) => document.querySelector(`li[data-kind="${kind}"] [data-mark]`);
    for (const kind of ["approval", "running", "next"]) expect(mark(kind).style.width).toBe("24px");
    expect(mark("approval")).toHaveAttribute("data-state", "needs");
    expect(mark("running")).toHaveAttribute("data-state", "working");
    expect(mark("next")).toHaveAttribute("data-state", "idle");
    expect(mark("next")).not.toHaveAttribute("data-live");
  });

  it("names the profile in its tone, both themes, and leaves the default profile in ink", async () => {
    await mount(snap({ state: "running", running: { count: 2, rows: [turn, { ...turn, id: "t2", label: "alpi", shape: "twin", accent: null }] } }));
    const [toned, plain] = document.querySelectorAll("li .ds-name");
    expect(toned).toHaveTextContent("sentinel");
    expect(toned.style.getPropertyValue("--name-light")).toMatch(/^#[0-9a-f]{6}$/);
    expect(toned.style.getPropertyValue("--name-dark")).toMatch(/^#[0-9a-f]{6}$/);
    expect(plain).toHaveTextContent("alpi");
    expect(plain.style.getPropertyValue("--name-light")).toBe("");
  });

  it("puts the time on the name line and the job alone on the second", async () => {
    await mount(snap({ next: { rows: [job] } }));
    const li = document.querySelector('li[data-kind="next"]');
    const name = li.querySelector(".ds-name");
    const time = within(li).getByText("in 1h");
    expect(time).toHaveClass("tnum");
    expect(name.parentElement.parentElement).toBe(time.parentElement);
    expect(within(li).getByText("Brief").parentElement).toBe(time.parentElement.parentElement);
  });

  it("draws the failing jobs and the update as tinted banners", async () => {
    await mount(snap({ state: "failing", failing: { jobs: 3, profileCount: 2, profiles: ["sentinel", "clonara"] }, update: { version: "0.18.11", busy: false } }));
    const failing = screen.getByRole("button", { name: /failed in 24 h/ });
    expect(failing).toHaveAttribute("data-tone", "danger");
    const update = screen.getByText("alpi 0.18.11 is ready").closest("[data-tone]");
    expect(update).toHaveAttribute("data-tone", "success");
    expect(within(update).getByRole("button", { name: "Restart to update" })).toBeInTheDocument();
  });

  it("offers Start alpi as one full-width action under the heading", async () => {
    await mount(snap({ state: "offline", offline: { local: true, canStart: true } }));
    const start = screen.getByRole("button", { name: "Start alpi" });
    expect(screen.getByRole("banner").contains(start)).toBe(false);
    expect(start.className).toMatch(/fullWidth/);
  });
});
