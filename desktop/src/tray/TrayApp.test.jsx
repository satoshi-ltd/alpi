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
  fold: "alpaca",
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
  running: { count: 0, first: null },
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
    expect(screen.getByText("Nothing needs you · online")).toBeInTheDocument();
    for (const name of ["Open alpi", "Settings", "Quit alpi", "Notifications"]) {
      expect(screen.getByRole("button", { name })).toBeInTheDocument();
    }
  });

  it("renders needs-you rows, counts and the unread bell", async () => {
    await mount(snap({
      state: "needs",
      unread: 2,
      needs: { total: 2, approvals: 2, questions: 0, rows: [need(0), need(1)] },
      failing: { jobs: 3, profileCount: 2, profiles: ["a", "b"] },
      running: { count: 2, first: null },
    }));
    expect(screen.getByRole("heading", { name: "2 need you" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /^Review:/ })).toHaveLength(2);
    expect(screen.getByRole("button", { name: /Failing jobs, 3 in 2 profiles/ })).toBeInTheDocument();
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
    await mount(snap({ state: "running", running: { count: 2, first: { label: "alpi", title: "Deploys" } } }));
    expect(screen.getByText("alpi · Deploys")).toBeInTheDocument();
    await push(snap({ state: "failing", failing: { jobs: 3, profileCount: 2, profiles: ["sentinel", "clonara"] } }));
    expect(screen.getByRole("heading", { name: "3 jobs failing" })).toBeInTheDocument();
    await push(snap({ update: { version: "0.9.3", busy: false } }));
    expect(screen.getByText("alpi 0.9.3 is ready")).toBeInTheDocument();
    await push(snap({ state: "starting" }));
    expect(screen.getByRole("heading", { name: "Starting alpi…" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Start requested");
    expect(screen.queryByRole("button", { name: "Start alpi" })).toBeNull();
    await push(snap({ state: "offline", offline: { local: true, canStart: true, absent: false } }));
    expect(screen.getByRole("heading", { name: "alpi is installed but not running" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start alpi" })).toBeInTheDocument();
  });

  it("hides the bell for a member and draws no scheduled counts", async () => {
    await mount(snap({ member: true }));
    expect(screen.queryByRole("button", { name: /Notifications/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /Failing jobs/ })).toBeNull();
  });

  it("reads Connecting before the first snapshot", async () => {
    await mount(null);
    expect(screen.getByRole("heading", { name: "Connecting…" })).toBeInTheDocument();
  });

  it("replaces what it draws when a new snapshot arrives", async () => {
    await mount(snap());
    await push(snap({ state: "needs", needs: { total: 1, approvals: 1, questions: 0, rows: [need(0)] } }));
    expect(screen.getByRole("heading", { name: "1 needs you" })).toBeInTheDocument();
  });

  it("never calls a daemon verb or reads files itself", async () => {
    await mount(snap({ state: "needs", needs: { total: 1, approvals: 1, questions: 0, rows: [need(0)] } }));
    const allowed = new Set(["tray_state", "resize_tray", "hide_tray", "show_main", "open_settings", "open_notifications", "restart_to_update", "quit_app", "start_alpi"]);
    for (const [name] of invoke.mock.calls) expect(allowed.has(name), name).toBe(true);
  });
});

describe("TrayApp actions", () => {
  const needing = () => snap({ state: "needs", needs: { total: 1, approvals: 1, questions: 0, rows: [need(0)] }, failing: { jobs: 1, profileCount: 1, profiles: ["x"] }, running: { count: 1, first: null }, update: { version: "0.9.3", busy: false }, unread: 1 });

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
    fireEvent.click(screen.getByRole("button", { name: /Failing jobs/ }));
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
    current = snap({ state: "running", running: { count: 3, first: null } });
    await act(async () => handlers["tray-shown"]());
    await waitFor(() => expect(screen.getByRole("heading", { name: "3 running" })).toBeInTheDocument());
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

describe("TrayApp Next line", () => {
  const AT = new Date(Date.now() + 5 * 3600e3).toISOString();

  it("draws the Next line with the title apart from the time, and no field", async () => {
    await mount(snap({ next: { title: "Daily brief", at: AT } }));
    expect(screen.getByText("Next:", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("Daily brief")).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("says Nothing scheduled for an admin with no job", async () => {
    await mount(snap({ next: null }));
    expect(screen.getByText("Nothing scheduled")).toBeInTheDocument();
  });

  it("keeps the container focused on open in the quiet state", async () => {
    await mount(snap({ next: { title: "Daily brief", at: AT } }));
    await act(async () => handlers["tray-shown"]());
    expect(document.activeElement).toBe(screen.getByRole("main").parentElement);
  });
});
