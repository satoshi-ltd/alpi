import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, configure, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { setSettingsDirty } from "./lib/settingsDirty.js";
import { EMPTY } from "../../common/emptyCopy.mjs";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };
window.matchMedia ??= () => ({
  matches: false,
  addEventListener() {},
  removeEventListener() {},
  addListener() {},
  removeListener() {},
});

vi.mock("@tauri-apps/api/window", () => ({
  getCurrentWindow: () => ({ startDragging: vi.fn(async () => {}), toggleMaximize: vi.fn(async () => {}) }),
}));
vi.mock("./lib/updater.js", () => ({
  installUpdater: () => () => {},
  describeUpdaterError: () => "",
  quitForUpdate: vi.fn(),
  applyPendingUpdate: vi.fn(),
  checkForUpdates: vi.fn(),
  subscribeUpdater: vi.fn(() => () => {}),
}));

import { _resetDaemonBus } from "./lib/daemon-bus.js";
import App from "./App.jsx";

configure({ asyncUtilTimeout: 5000 });

const ALPI = { name: "default", is_default: true, model: "m/a", latest_session: { kind: "chat", id: "s-alpi", updated_at: 1 } };
const DOC = { name: "doc", model: "m/d", latest_session: { kind: "chat", id: "s-doc", updated_at: 50 } };
const SCOUT = { name: "scout", model: "m/s", latest_session: { kind: "chat", id: "s-scout", updated_at: 90 } };
const PIXEL = { name: "pixel", model: "m/p", latest_session: { kind: "chat", id: "s-pixel", updated_at: 10 } };
const CREW = { profile: "doc", id: "crew", name: "crew", mtime: 60 };

function daemon({ profiles = [ALPI, DOC], workgroups = [CREW], role = "admin", localStatus = "online", remote = null, local = "running", startFails = null } = {}) {
  const state = { active: "local", profiles: { local: [...profiles], remote: remote?.profiles ?? [] }, calls: [], remoteStatus: remote?.status ?? "online", localStatus, local, startFails };
  invoke.mockImplementation(async (cmd, args = {}) => {
    state.calls.push([cmd, args]);
    if (cmd === "host_connections") {
      const connections = [{ id: "local", kind: "local", status: state.localStatus, role }];
      if (remote) connections.push({ id: "remote", kind: "remote", name: "mirai", url: "ws://mirai:7423", status: state.remoteStatus, role: "admin" });
      return { active_id: state.active, connections };
    }
    if (cmd === "host_connection_set_active") {
      if (remote?.revoked) throw new Error("device revoked");
      state.active = args.id;
      return null;
    }
    if (cmd === "host_connection_probe") return "online";
    if (cmd === "local_daemon_state") return { state: state.local };
    if (cmd === "local_daemon_start") {
      if (state.startFails) throw new Error(state.startFails);
      state.localStatus = "online";
      state.local = "running";
      return "started";
    }
    if (cmd === "profile_summaries") {
      if (state.hang) return new Promise(() => {});
      return state.profiles[args.connectionId ?? "local"] ?? [];
    }
    if (cmd === "profile_delete") {
      state.profiles.local = state.profiles.local.filter((p) => p.name !== args.name);
      return null;
    }
    if (cmd === "profiles") return [];
    if (cmd === "workgroups") return args.connectionId === "remote" ? [] : workgroups;
    return null;
  });
  return state;
}

const row = (label) => screen.getAllByText(label).map((el) => el.closest("button")).find((b) => b?.classList.contains("ds-sb-row"));
const selected = (label) => row(label)?.dataset.sel === "true";
const pressNewSession = () =>
  act(() => {
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "n", metaKey: true, bubbles: true, cancelable: true }));
  });

const listeners = {};

beforeEach(() => {
  invoke.mockReset();
  localStorage.clear();
  for (const key of Object.keys(listeners)) delete listeners[key];
  listen.mockImplementation(async (name, cb) => {
    listeners[name] = cb;
    return () => {};
  });
});

const openSettings = () =>
  act(() => {
    window.dispatchEvent(new KeyboardEvent("keydown", { key: ",", metaKey: true, bubbles: true, cancelable: true }));
  });

async function switchTo(name) {
  fireEvent.click(screen.getByText("This computer"));
  fireEvent.click(await screen.findByText(name));
}

const sessionOpened = (profile, id) =>
  invoke.mock.calls.some(([cmd, args]) => cmd === "session_detail" && args?.profile === profile && args?.id === id);

describe("App landing", () => {
  it("opens on the first roster row's latest session, never on a start screen", async () => {
    daemon();
    render(<App />);
    await waitFor(() => expect(selected("alpi")).toBe(true));
    expect(selected("doc")).toBe(false);
    expect(screen.queryByText("New session")).toBeNull();
    await waitFor(() => expect(sessionOpened("default", "s-alpi")).toBe(true));
  });

  it("starts a new thread with the last profile seen when ⌘N is pressed in a workgroup", async () => {
    daemon();
    render(<App />);
    await waitFor(() => expect(selected("alpi")).toBe(true));
    fireEvent.click(row("doc"));
    await waitFor(() => expect(selected("doc")).toBe(true));
    fireEvent.click(row("crew"));
    await waitFor(() => expect(selected("crew")).toBe(true));
    pressNewSession();
    await waitFor(() => expect(selected("doc")).toBe(true));
    expect(selected("crew")).toBe(false);
    expect(screen.getByText("Start a new thread")).toBeInTheDocument();
  });

  it("leaves Settings for a new thread with the last profile seen on ⌘N", async () => {
    daemon();
    render(<App />);
    await waitFor(() => expect(selected("alpi")).toBe(true));
    fireEvent.click(row("doc"));
    await waitFor(() => expect(selected("doc")).toBe(true));
    fireEvent.click(row("crew"));
    await waitFor(() => expect(selected("crew")).toBe(true));
    openSettings();
    await waitFor(() => expect(screen.getByText("Command…")).toBeInTheDocument());
    pressNewSession();
    await waitFor(() => expect(screen.getByText("Start a new thread")).toBeInTheDocument());
    expect(screen.queryByText("Command…")).toBeNull();
    expect(selected("doc")).toBe(true);
  });

  it("starts a new thread from the profile row's menu", async () => {
    daemon();
    render(<App />);
    await waitFor(() => expect(selected("alpi")).toBe(true));
    fireEvent.contextMenu(row("doc"));
    fireEvent.click(screen.getAllByRole("menuitem")[0]);
    await waitFor(() => expect(selected("doc")).toBe(true));
    expect(screen.getByText("Start a new thread")).toBeInTheDocument();
  });

  it("lands back on the local first row when a switch to a revoked connection fails", async () => {
    localStorage.setItem("alf:profiles:v1:remote", JSON.stringify([SCOUT]));
    daemon({ remote: { profiles: [SCOUT], revoked: true } });
    render(<App />);
    await waitFor(() => expect(selected("alpi")).toBe(true));
    await switchTo("mirai");
    await waitFor(() => expect(screen.queryByText("scout")).toBeNull());
    await waitFor(() => expect(selected("alpi")).toBe(true));
    pressNewSession();
    await waitFor(() => expect(screen.getByText("Start a new thread")).toBeInTheDocument());
    expect(selected("alpi")).toBe(true);
  });

  it("starts ⌘N from Settings with the new connection's first row when no profile was seen there yet", async () => {
    const state = daemon({ remote: { profiles: [PIXEL, SCOUT] } });
    render(<App />);
    await waitFor(() => expect(selected("alpi")).toBe(true));
    openSettings();
    await waitFor(() => expect(screen.getByText("Command…")).toBeInTheDocument());
    await switchTo("mirai");
    await waitFor(() => expect(state.active).toBe("remote"));
    await waitFor(() => expect(row("scout")).toBeTruthy());
    expect(screen.getByText("Command…")).toBeInTheDocument();
    pressNewSession();
    await waitFor(() => expect(screen.getByText("Start a new thread")).toBeInTheDocument());
    expect(selected("scout")).toBe(true);
  });

  it("starts an empty thread on ⌘N while a new chat of the same profile is still streaming", async () => {
    const state = daemon();
    render(<App />);
    await waitFor(() => expect(selected("alpi")).toBe(true));
    pressNewSession();
    await waitFor(() => expect(screen.getByText("Start a new thread")).toBeInTheDocument());
    const send = (text) => {
      const box = screen.getByPlaceholderText(/Message/);
      fireEvent.change(box, { target: { value: text } });
      fireEvent.keyDown(box, { key: "Enter", metaKey: true });
    };
    send("first question");
    await waitFor(() => expect(state.calls.filter(([c]) => c === "chat_send_stream")).toHaveLength(1));
    await waitFor(() => expect(screen.queryByText("Start a new thread")).toBeNull());
    pressNewSession();
    await waitFor(() => expect(screen.getByText("Start a new thread")).toBeInTheDocument());
    send("second question");
    await waitFor(() => expect(state.calls.filter(([c]) => c === "chat_send_stream")).toHaveLength(2));
    expect(screen.queryByText(/A turn is already running/)).toBeNull();
    expect(state.calls.filter(([c]) => c === "chat_send_stream").map(([, a]) => a.sessionId)).toEqual([null, null]);
  });

  it("puts the message back in the box when the daemon refuses it after the send was launched", async () => {
    const state = daemon();
    const chatListeners = [];
    listen.mockImplementation(async (name, cb) => {
      listeners[name] = cb;
      if (name === "chat-event") chatListeners.push(cb);
      return () => {};
    });
    const notify = vi.fn();
    window.notify = notify;
    render(<App />);
    await waitFor(() => expect(selected("alpi")).toBe(true));
    pressNewSession();
    await waitFor(() => expect(screen.getByText("Start a new thread")).toBeInTheDocument());
    const box = screen.getByPlaceholderText(/Message/);
    fireEvent.change(box, { target: { value: "while another device is running a turn" } });
    fireEvent.keyDown(box, { key: "Enter", metaKey: true });
    await waitFor(() => expect(state.calls.filter(([c]) => c === "chat_send_stream")).toHaveLength(1));
    const [, args] = state.calls.find(([c]) => c === "chat_send_stream");
    await act(async () => {
      chatListeners.forEach((cb) => cb({ payload: { request_id: args.requestId, kind: "error", text: "session already has a running turn" } }));
    });
    await waitFor(() => expect(screen.getByPlaceholderText(/Message/).value).toBe("while another device is running a turn"));
    expect(screen.queryByText("while another device is running a turn", { selector: "p, div:not(textarea)" })).toBeNull();
  });

  it("keeps an unsaved Settings draft when New session comes from ⌘N, the row menu or the palette", async () => {
    const notify = vi.fn();
    window.notify = notify;
    daemon();
    render(<App />);
    await waitFor(() => expect(selected("alpi")).toBe(true));
    openSettings();
    await waitFor(() => expect(screen.getByText("Command…")).toBeInTheDocument());
    setSettingsDirty("profile:default:bio", true);
    try {
      pressNewSession();
      fireEvent.contextMenu(row("doc"));
      fireEvent.click(screen.getAllByRole("menuitem")[0]);
      act(() => {
        window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true, cancelable: true }));
      });
      fireEvent.change(await screen.findByRole("combobox"), { target: { value: "New session" } });
      fireEvent.keyDown(screen.getByRole("combobox"), { key: "Enter" });
      expect(screen.getByText("Command…")).toBeInTheDocument();
      expect(screen.queryByText("Start a new thread")).toBeNull();
      expect(notify).toHaveBeenCalledTimes(3);
    } finally {
      setSettingsDirty("profile:default:bio", false);
      delete window.notify;
    }
  });

  it("lands on the first roster row after deleting the open profile", async () => {
    daemon();
    render(<App />);
    await waitFor(() => expect(selected("alpi")).toBe(true));
    fireEvent.click(row("doc"));
    await waitFor(() => expect(selected("doc")).toBe(true));
    fireEvent.contextMenu(row("doc"));
    fireEvent.click(screen.getByText("Delete profile…"));
    const dialog = await screen.findByRole("dialog");
    const field = dialog.querySelector("input");
    fireEvent.change(field, { target: { value: "doc" } });
    fireEvent.keyDown(field, { key: "Enter" });
    await waitFor(() => expect(selected("alpi")).toBe(true));
    expect(screen.queryByText("Command…")).toBeNull();
    await waitFor(() => expect(screen.queryAllByText("doc").filter((el) => el.closest(".ds-sb-row"))).toHaveLength(0));
  });

  it("lands a member snapped out of Settings on the first roster row", async () => {
    daemon({ role: "member" });
    render(<App />);
    await waitFor(() => expect(selected("alpi")).toBe(true));
    fireEvent.click(row("doc"));
    await waitFor(() => expect(selected("doc")).toBe(true));
    await waitFor(() => expect(listeners.nav).toBeTruthy());
    act(() => listeners.nav({ payload: "settings" }));
    await waitFor(() => expect(selected("alpi")).toBe(true));
    expect(screen.queryByText("Command…")).toBeNull();
  });

  it("shows nothing, not the empty roster state, before the roster answers", async () => {
    daemon({ profiles: [], workgroups: [], localStatus: "unknown" });
    render(<App />);
    await waitFor(() => expect(invoke).toHaveBeenCalledWith("host_connections"));
    await act(async () => { await new Promise((r) => setTimeout(r, 50)); });
    expect(screen.queryByText(EMPTY.roster.title)).toBeNull();
  });

  it("tells a member with no profiles to ask the host admin, with no New profile button", async () => {
    daemon({ profiles: [], workgroups: [], role: "member" });
    render(<App />);
    await waitFor(() => expect(screen.getByText(EMPTY.rosterMember.hint)).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "New profile" })).toBeNull();
  });

  it("waits for the live roster after a switch instead of landing on a stale cached one", async () => {
    localStorage.setItem("alf:profiles:v1:remote", JSON.stringify([SCOUT]));
    const state = daemon({ remote: { profiles: [PIXEL] } });
    render(<App />);
    await waitFor(() => expect(selected("alpi")).toBe(true));
    await switchTo("mirai");
    await waitFor(() => expect(state.active).toBe("remote"));
    await waitFor(() => expect(selected("pixel")).toBe(true));
    expect(screen.queryByText("scout")).toBeNull();
    await waitFor(() => expect(sessionOpened("pixel", "s-pixel")).toBe(true));
    expect(sessionOpened("scout", "s-scout")).toBe(false);
  });

  it("shows the empty roster state when the switched-to connection answers empty despite a cached roster", async () => {
    localStorage.setItem("alf:profiles:v1:remote", JSON.stringify([SCOUT]));
    daemon({ remote: { profiles: [] } });
    render(<App />);
    await waitFor(() => expect(selected("alpi")).toBe(true));
    await switchTo("mirai");
    await waitFor(() => expect(screen.getByText(EMPTY.roster.title)).toBeInTheDocument());
    expect(sessionOpened("scout", "s-scout")).toBe(false);
  });

  it("closes Settings onto the new connection's first row after a switch, not the old connection's profile", async () => {
    const state = daemon({ remote: { profiles: [PIXEL, SCOUT] } });
    render(<App />);
    await waitFor(() => expect(selected("alpi")).toBe(true));
    openSettings();
    await waitFor(() => expect(screen.getByText("Command…")).toBeInTheDocument());
    await switchTo("mirai");
    await waitFor(() => expect(state.active).toBe("remote"));
    await waitFor(() => expect(row("scout")).toBeTruthy());
    openSettings();
    await waitFor(() => expect(screen.queryByText("Command…")).toBeNull());
    await waitFor(() => expect(selected("scout")).toBe(true));
    expect(sessionOpened("default", "s-alpi")).toBe(true);
    expect(invoke.mock.calls.filter(([cmd, args]) => cmd === "session_detail" && args?.profile === "default" && args?.connectionId === "remote")).toHaveLength(0);
  });

  it("re-lands on the live first row when an offline switch landed on a cached profile the daemon no longer serves", async () => {
    localStorage.setItem("alf:profiles:v1:remote", JSON.stringify([SCOUT]));
    const state = daemon({ remote: { profiles: [PIXEL], status: "offline" } });
    render(<App />);
    await waitFor(() => expect(selected("alpi")).toBe(true));
    await switchTo("mirai");
    await waitFor(() => expect(state.active).toBe("remote"));
    await waitFor(() => expect(selected("scout")).toBe(true));
    state.remoteStatus = "online";
    await act(async () => { listeners["connection-status"]?.({ payload: { id: "remote", status: "online" } }); });
    await waitFor(() => expect(selected("pixel")).toBe(true));
    expect(screen.queryByText("scout")).toBeNull();
  });

  it("never reopens the old connection's session when Settings closes after a switch", async () => {
    const DOC_REMOTE = { ...DOC, latest_session: { kind: "chat", id: "s-doc-remote", updated_at: 70 } };
    const state = daemon({ remote: { profiles: [DOC_REMOTE] } });
    render(<App />);
    await waitFor(() => expect(selected("alpi")).toBe(true));
    fireEvent.click(row("doc"));
    await waitFor(() => expect(sessionOpened("doc", "s-doc")).toBe(true));
    fireEvent.contextMenu(row("crew"));
    fireEvent.click(await screen.findByText("Open settings"));
    await waitFor(() => expect(screen.getByText("Command…")).toBeInTheDocument());
    await switchTo("mirai");
    await waitFor(() => expect(state.active).toBe("remote"));
    await waitFor(() => expect(row("doc")).toBeTruthy());
    openSettings();
    await waitFor(() => expect(screen.queryByText("Command…")).toBeNull());
    await waitFor(() => expect(sessionOpened("doc", "s-doc-remote")).toBe(true));
    expect(invoke.mock.calls.some(([cmd, args]) => cmd === "session_detail" && args?.id === "s-doc" && args?.connectionId === "remote")).toBe(false);
  });

  it("lands on the cached first row when the online daemon's roster keeps failing", async () => {
    localStorage.setItem("alf:profiles:v1:local", JSON.stringify([ALPI, DOC]));
    const state = daemon();
    const base = invoke.getMockImplementation();
    invoke.mockImplementation(async (cmd, args) => {
      if (cmd === "profile_summaries") { state.calls.push([cmd, args]); throw new Error("timeout"); }
      return base(cmd, args);
    });
    render(<App />);
    await waitFor(() => expect(selected("alpi")).toBe(true));
    await waitFor(() => expect(sessionOpened("default", "s-alpi")).toBe(true));
  });

  it("offers a retry instead of a blank pane when the first roster call fails with nothing cached", async () => {
    const state = daemon();
    const base = invoke.getMockImplementation();
    let failing = true;
    invoke.mockImplementation(async (cmd, args) => {
      if (cmd === "profile_summaries" && failing) { state.calls.push([cmd, args]); throw new Error("timeout"); }
      return base(cmd, args);
    });
    render(<App />);
    const retry = await screen.findByRole("button", { name: /retry/i });
    expect(screen.getByText("Couldn't load profiles")).toBeInTheDocument();
    failing = false;
    fireEvent.click(retry);
    await waitFor(() => expect(selected("alpi")).toBe(true));
  });

  it("keeps a deep link to a profile the roster lists only after its next answer", async () => {
    const state = daemon();
    render(<App />);
    await waitFor(() => expect(selected("alpi")).toBe(true));
    await waitFor(() => expect(listeners["notification-activated"]).toBeTruthy());
    state.profiles.local = [ALPI, DOC, SCOUT];
    await act(async () => { listeners["notification-activated"]({ payload: { deeplink: { kind: "chat", profile: "scout", id: "s-scout" } } }); });
    await waitFor(() => expect(row("scout")).toBeTruthy());
    await waitFor(() => expect(selected("scout")).toBe(true));
    expect(selected("alpi")).toBe(false);
  });

  it("asks the daemon for its pending approvals and questions after a replayed burst", async () => {
    daemon();
    _resetDaemonBus();
    render(<App />);
    await waitFor(() => expect(selected("alpi")).toBe(true));
    await waitFor(() => expect(listeners["daemon-event"]).toBeTruthy());
    const pending = () => invoke.mock.calls.filter(([cmd]) => cmd === "approval_pending" || cmd === "clarification_pending").length;
    const before = pending();
    await act(async () => {
      listeners["daemon-event"]({ payload: { replay: true, frame: { event: "approval.request", data: { request_id: "r1" } } } });
      listeners["daemon-event"]({ payload: { replay: true, frame: { event: "clarification.resolved", data: { request_id: "q1" } } } });
      await new Promise((resolve) => setTimeout(resolve, 450));
    });
    expect(pending()).toBe(before + 2);
  });

  it("welcomes a computer with no alpi with two paths instead of a locked panel", async () => {
    daemon({ localStatus: "offline", local: "absent", profiles: [] });
    render(<App />);
    await waitFor(() => expect(screen.getByText("Set up alpi")).toBeInTheDocument());
    expect(screen.getByText("Run alpi here")).toBeInTheDocument();
    expect(screen.getByText("Connect to alpi elsewhere")).toBeInTheDocument();
    expect(screen.queryByText("No host yet. Add a connection to continue.")).toBeNull();
  });

  it("starts an installed alpi on its own and lands on the roster once it answers", async () => {
    const state = daemon({ localStatus: "offline", local: "stopped" });
    render(<App />);
    await waitFor(() => expect(state.calls.some(([cmd]) => cmd === "local_daemon_start")).toBe(true));
    await waitFor(() => expect(selected("alpi")).toBe(true));
    expect(screen.queryByText("alpi is installed but not running")).toBeNull();
    expect(state.calls.filter(([cmd]) => cmd === "local_daemon_start")).toHaveLength(1);
  });

  it("shows why alpi did not start and lets the user retry", async () => {
    const state = daemon({ localStatus: "offline", local: "stopped", startFails: "daemon start failed (1): bad config" });
    render(<App />);
    await waitFor(() => expect(screen.getByText("alpi didn't start")).toBeInTheDocument());
    expect(screen.getByText(/bad config/)).toBeInTheDocument();
    state.startFails = null;
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(selected("alpi")).toBe(true));
  });

  it("keeps the open view and shows the banner when a local alpi that answered drops, and starts it only on Retry", async () => {
    const state = daemon();
    render(<App />);
    await waitFor(() => expect(selected("alpi")).toBe(true));
    state.localStatus = "offline";
    state.local = "stopped";
    await act(async () => { listeners["connection-status"]?.({ payload: { id: "local", status: "offline" } }); });
    await waitFor(() => expect(screen.getByText("alpi on this computer is not answering — reconnecting…")).toBeInTheDocument());
    expect(selected("alpi")).toBe(true);
    expect(screen.queryByText("Starting alpi…")).toBeNull();
    expect(screen.queryByText("alpi is installed but not running")).toBeNull();
    expect(state.calls.some(([cmd]) => cmd === "local_daemon_start")).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(state.calls.some(([cmd]) => cmd === "local_daemon_start")).toBe(true));
    await waitFor(() => expect(selected("alpi")).toBe(true));
  });

  it("probes at once when alpi starts answering after it was installed from the welcome", async () => {
    const state = daemon({ localStatus: "offline", local: "absent", profiles: [ALPI] });
    render(<App />);
    await waitFor(() => expect(screen.getByText("Set up alpi")).toBeInTheDocument());
    state.local = "running";
    state.localStatus = "online";
    fireEvent.click(screen.getByRole("button", { name: "Check again" }));
    await waitFor(() => expect(selected("alpi")).toBe(true));
    expect(state.calls.some(([cmd]) => cmd === "host_connections_probe_active")).toBe(true);
  });

  it("names this computer once, with where a phone gets its link, and remembers the dismissal", async () => {
    daemon();
    const { unmount } = render(<App />);
    await waitFor(() => expect(screen.getByText("This is alpi on this computer")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Got it" }));
    expect(screen.queryByText("This is alpi on this computer")).toBeNull();
    unmount();
    render(<App />);
    await waitFor(() => expect(selected("alpi")).toBe(true));
    expect(screen.queryByText("This is alpi on this computer")).toBeNull();
  });

  it("keeps the empty roster state on screen while a later reload is in flight", async () => {
    const state = daemon({ profiles: [], workgroups: [] });
    render(<App />);
    await waitFor(() => expect(screen.getByText(EMPTY.roster.title)).toBeInTheDocument());
    await waitFor(() => expect(listeners["fs-change"]).toBeTruthy());
    state.hang = true;
    const before = state.calls.filter(([cmd]) => cmd === "profile_summaries").length;
    act(() => listeners["fs-change"]({ payload: { kind: "config" } }));
    await waitFor(() => expect(state.calls.filter(([cmd]) => cmd === "profile_summaries").length).toBeGreaterThan(before));
    await act(async () => { await new Promise((r) => setTimeout(r, 400)); });
    expect(screen.getByText(EMPTY.roster.title)).toBeInTheDocument();
    expect(screen.getByText(EMPTY.profiles.title)).toBeInTheDocument();
  });

  it("shows the empty roster state with no profiles, and ⌘N does nothing", async () => {
    daemon({ profiles: [], workgroups: [] });
    render(<App />);
    await waitFor(() => expect(screen.getByText(EMPTY.roster.title)).toBeInTheDocument());
    expect(screen.getByText(EMPTY.roster.hint)).toBeInTheDocument();
    pressNewSession();
    expect(screen.getByText(EMPTY.roster.title)).toBeInTheDocument();
    expect(screen.queryByText("Start a new thread")).toBeNull();
  });
});
