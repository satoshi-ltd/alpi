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

const inSettingsView = () => screen.queryAllByRole("button", { name: "Settings" }).some((el) => el.getAttribute("aria-current") === "page");

const HINT_LINE = "This is alpi on this computer · To use it from a phone: Settings → Connections";
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
    if (cmd === "local_daemon_install") {
      if (state.installFails) throw new Error(state.installFails);
      state.local = "stopped";
      return null;
    }
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
    await waitFor(() => expect(inSettingsView()).toBe(true));
    pressNewSession();
    await waitFor(() => expect(screen.getByText("Start a new thread")).toBeInTheDocument());
    expect(inSettingsView()).toBe(false);
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
    await waitFor(() => expect(inSettingsView()).toBe(true));
    await switchTo("mirai");
    await waitFor(() => expect(state.active).toBe("remote"));
    await waitFor(() => expect(row("scout")).toBeTruthy());
    expect(inSettingsView()).toBe(true);
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
    await waitFor(() => expect(inSettingsView()).toBe(true));
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
      expect(inSettingsView()).toBe(true);
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
    expect(inSettingsView()).toBe(false);
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
    expect(inSettingsView()).toBe(false);
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
    await waitFor(() => expect(inSettingsView()).toBe(true));
    await switchTo("mirai");
    await waitFor(() => expect(state.active).toBe("remote"));
    await waitFor(() => expect(row("scout")).toBeTruthy());
    openSettings();
    await waitFor(() => expect(inSettingsView()).toBe(false));
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
    await waitFor(() => expect(inSettingsView()).toBe(true));
    await switchTo("mirai");
    await waitFor(() => expect(state.active).toBe("remote"));
    await waitFor(() => expect(row("doc")).toBeTruthy());
    openSettings();
    await waitFor(() => expect(inSettingsView()).toBe(false));
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

  it("welcomes a computer with no alpi with one primary and a way to connect elsewhere, instead of a locked panel", async () => {
    daemon({ localStatus: "offline", local: "absent", profiles: [] });
    render(<App />);
    await waitFor(() => expect(screen.getByText("Set up alpi")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Install and start alpi" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Connect to another computer" })).toBeInTheDocument();
    expect(screen.queryByText("Run alpi here")).toBeNull();
    expect(screen.queryByText("No host yet. Add a connection to continue.")).toBeNull();
  });

  it("shows the welcome full window with no sidebar and a drag strip, and mounts the sidebar once the roster is shown", async () => {
    daemon({ localStatus: "offline", local: "absent" });
    const { container } = render(<App />);
    await waitFor(() => expect(screen.getByText("Set up alpi")).toBeInTheDocument());
    expect(container.querySelector("aside")).toBeNull();
    expect(screen.queryByText("This computer")).toBeNull();
    expect(container.querySelectorAll("[data-drag]")).toHaveLength(1);
    expect(container.querySelector("[data-drag]").closest("section")).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Install and start alpi" }));
    await waitFor(() => expect(selected("alpi")).toBe(true));
    expect(container.querySelector("aside")).not.toBeNull();
    expect(container.querySelectorAll("[data-drag]").length).toBeGreaterThan(0);
    expect(screen.queryByText("Set up alpi")).toBeNull();
  });

  it("keeps the sidebar and its connection switcher beside the welcome when another connection is saved", async () => {
    daemon({ localStatus: "offline", local: "absent", remote: { profiles: [DOC], status: "online" } });
    const { container } = render(<App />);
    await waitFor(() => expect(screen.getByText("Set up alpi")).toBeInTheDocument());
    expect(container.querySelector("aside")).not.toBeNull();
    expect(screen.getByText("This computer")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Install and start alpi" })).toBeInTheDocument();
    expect(container.querySelector("main [data-drag]")).not.toBeNull();
    expect(container.firstElementChild.className).not.toMatch(/bare/);
  });

  it("hands the bare first run over to the sidebar when the link form connects to another computer", async () => {
    const state = daemon({ localStatus: "offline", local: "absent", remote: { profiles: [DOC], status: "online" } });
    const base = invoke.getMockImplementation();
    invoke.mockImplementation(async (cmd, args) => {
      if (cmd === "host_connection_add_remote") {
        state.added = true;
        state.active = "remote";
        return null;
      }
      const result = await base(cmd, args);
      if (cmd === "host_connections" && !state.added) {
        return { ...result, connections: result.connections.filter((c) => c.id === "local") };
      }
      return result;
    });
    const { container } = render(<App />);
    await waitFor(() => expect(screen.getByText("Set up alpi")).toBeInTheDocument());
    expect(container.querySelector("aside")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Connect to another computer" }));
    fireEvent.change(screen.getByLabelText("alpi:// link"), { target: { value: "alpi://device?url=ws%3A%2F%2Fmirai%3A7423&name=mirai&pairing_token=abc" } });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Connect" })); });
    await waitFor(() => expect(container.querySelector("aside")).not.toBeNull());
    expect(screen.queryByText("Set up alpi")).toBeNull();
  });

  it("never replaces the whole window when a daemon that was online stops: the sidebar stays through Retry and a failure", async () => {
    const state = daemon();
    const { container } = render(<App />);
    await waitFor(() => expect(selected("alpi")).toBe(true));
    state.localStatus = "offline";
    state.local = "stopped";
    state.startFails = "daemon start failed (1): bad config";
    await act(async () => { listeners["connection-status"]?.({ payload: { id: "local", status: "offline" } }); });
    await waitFor(() => expect(screen.getByText("alpi on this computer is not answering — reconnecting…")).toBeInTheDocument());
    expect(container.querySelector("aside")).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(screen.getByText("alpi didn't start")).toBeInTheDocument());
    expect(container.querySelector("aside")).not.toBeNull();
    expect(container.firstElementChild.className).not.toMatch(/bare/);
  });

  it("ignores the shell shortcuts while the first-run welcome is bare, and keeps them when it is not", async () => {
    daemon({ localStatus: "offline", local: "absent" });
    const { container, unmount } = render(<App />);
    await waitFor(() => expect(screen.getByText("Set up alpi")).toBeInTheDocument());
    openSettings();
    for (const key of ["j", "o"]) act(() => { window.dispatchEvent(new KeyboardEvent("keydown", { key, metaKey: true, bubbles: true, cancelable: true })); });
    fireEvent.click(screen.getByRole("button", { name: "Install and start alpi" }));
    await waitFor(() => expect(selected("alpi")).toBe(true));
    expect(container.querySelector("aside")).not.toBeNull();
    expect(inSettingsView()).toBe(false);
    unmount();
    localStorage.clear();
    daemon({ localStatus: "offline", local: "absent", remote: { profiles: [DOC], status: "online" } });
    render(<App />);
    await waitFor(() => expect(screen.getByText("Set up alpi")).toBeInTheDocument());
    openSettings();
    fireEvent.click(screen.getByRole("button", { name: "Install and start alpi" }));
    await waitFor(() => expect(inSettingsView()).toBe(true));
  });

  it("paints the cold start as the bare frame with no sidebar and no offline banner, then mounts the sidebar straight into the roster", async () => {
    daemon({ localStatus: "offline", local: "stopped" });
    const seen = [];
    const observer = new MutationObserver(() => {
      seen.push([!!document.querySelector("aside"), /not answering/.test(document.body.textContent)]);
    });
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });
    render(<App />);
    await waitFor(() => expect(selected("alpi")).toBe(true));
    observer.disconnect();
    expect(seen.some(([sidebar, banner]) => sidebar && banner)).toBe(false);
  });

  it("never paints the bare frame on a machine whose local daemon was online before: sidebar and welcome in the main pane", async () => {
    localStorage.setItem("alpi.localEverOnline.v1", "seen");
    daemon({ localStatus: "offline", local: "stopped", startFails: "daemon start failed (1): bad config" });
    const { container } = render(<App />);
    expect(container.firstElementChild.className).not.toMatch(/bare/);
    await waitFor(() => expect(screen.getByText("alpi didn't start")).toBeInTheDocument());
    expect(container.querySelector("aside")).not.toBeNull();
    expect(container.querySelector("main [data-drag]")).not.toBeNull();
    expect(container.firstElementChild.className).not.toMatch(/bare/);
  });

  it("writes the ever-online flag the first time the local connection answers", async () => {
    expect(localStorage.getItem("alpi.localEverOnline.v1")).toBeNull();
    daemon();
    render(<App />);
    await waitFor(() => expect(selected("alpi")).toBe(true));
    expect(localStorage.getItem("alpi.localEverOnline.v1")).toBe("seen");
  });

  it("does not write the flag while the local daemon is offline, and paints bare on a first run", async () => {
    daemon({ localStatus: "offline", local: "absent" });
    const { container } = render(<App />);
    await waitFor(() => expect(screen.getByText("Set up alpi")).toBeInTheDocument());
    expect(container.firstElementChild.className).toMatch(/bare/);
    expect(localStorage.getItem("alpi.localEverOnline.v1")).toBeNull();
  });

  it("keeps the first-run path working when localStorage throws", async () => {
    const realGet = Storage.prototype.getItem;
    const realSet = Storage.prototype.setItem;
    const get = vi.spyOn(Storage.prototype, "getItem").mockImplementation(function (key) {
      if (key === "alpi.localEverOnline.v1") throw new Error("blocked");
      return realGet.call(this, key);
    });
    const set = vi.spyOn(Storage.prototype, "setItem").mockImplementation(function (key, value) {
      if (key === "alpi.localEverOnline.v1") throw new Error("blocked");
      return realSet.call(this, key, value);
    });
    daemon({ localStatus: "offline", local: "absent" });
    const { container } = render(<App />);
    await waitFor(() => expect(screen.getByText("Set up alpi")).toBeInTheDocument());
    expect(container.firstElementChild.className).toMatch(/bare/);
    fireEvent.click(screen.getByRole("button", { name: "Install and start alpi" }));
    await waitFor(() => expect(selected("alpi")).toBe(true));
    get.mockRestore();
    set.mockRestore();
  });

  describe("cold start", () => {
    const FLAG = "alpi.localEverOnline.v1";
    const shell = (container) => ({ bare: /bare/.test(container.firstElementChild.className), aside: container.querySelector("aside") !== null });

    it.each(["unknown", "probing"])("first run with the local status %s: bare strip only, no sidebar, no banner", async (status) => {
      daemon({ localStatus: status, local: "absent" });
      const { container } = render(<App />);
      await waitFor(() => expect(invoke.mock.calls.some(([cmd]) => cmd === "host_connections")).toBe(true));
      await act(async () => { await new Promise((r) => setTimeout(r, 30)); });
      expect(shell(container)).toEqual({ bare: true, aside: false });
      expect(container.querySelectorAll("main [data-drag]")).toHaveLength(1);
      expect(screen.queryByText(/not answering/)).toBeNull();
    });

    it("first run before the connection list has loaded: bare strip only", async () => {
      invoke.mockImplementation(async (cmd) => (cmd === "host_connections" ? { active_id: "local", connections: [] } : null));
      const { container } = render(<App />);
      await act(async () => { await new Promise((r) => setTimeout(r, 30)); });
      expect(shell(container)).toEqual({ bare: true, aside: false });
    });

    it.each(["unknown", "probing"])("a returning user with the local status %s gets the sidebar and never the bare frame", async (status) => {
      localStorage.setItem(FLAG, "seen");
      daemon({ localStatus: status });
      const { container } = render(<App />);
      expect(shell(container)).toEqual({ bare: false, aside: true });
      await act(async () => { await new Promise((r) => setTimeout(r, 30)); });
      expect(shell(container)).toEqual({ bare: false, aside: true });
    });

    it("a user whose only connection is a remote one never sees the bare frame once the list loads", async () => {
      invoke.mockImplementation(async (cmd) => {
        if (cmd === "host_connections") return { active_id: "remote", connections: [{ id: "remote", kind: "remote", name: "mirai", url: "ws://mirai:7423", status: "online", role: "admin" }] };
        if (cmd === "profile_summaries") return [ALPI];
        return cmd === "workgroups" || cmd === "profiles" ? [] : null;
      });
      const { container } = render(<App />);
      await waitFor(() => expect(selected("alpi")).toBe(true));
      expect(shell(container)).toEqual({ bare: false, aside: true });
    });

    it("resolves probing to online by mounting the sidebar straight into the roster, never the welcome", async () => {
      const state = daemon({ localStatus: "probing", local: "running" });
      const { container } = render(<App />);
      await act(async () => { await new Promise((r) => setTimeout(r, 30)); });
      expect(shell(container)).toEqual({ bare: true, aside: false });
      state.localStatus = "online";
      await act(async () => { listeners["connection-status"]?.({ payload: { id: "local", status: "online" } }); });
      await waitFor(() => expect(selected("alpi")).toBe(true));
      expect(shell(container)).toEqual({ bare: false, aside: true });
      expect(screen.queryByText("Set up alpi")).toBeNull();
    });

    it("resolves probing to offline as the welcome, still bare", async () => {
      const state = daemon({ localStatus: "probing", local: "absent" });
      const { container } = render(<App />);
      await act(async () => { await new Promise((r) => setTimeout(r, 30)); });
      expect(shell(container)).toEqual({ bare: true, aside: false });
      state.localStatus = "offline";
      await act(async () => { listeners["connection-status"]?.({ payload: { id: "local", status: "offline" } }); });
      await waitFor(() => expect(screen.getByText("Set up alpi")).toBeInTheDocument());
      expect(shell(container)).toEqual({ bare: true, aside: false });
    });

    it("ignores every shell shortcut while bare and honours them as soon as it ends", async () => {
      const state = daemon({ localStatus: "probing", local: "running" });
      const { container } = render(<App />);
      await act(async () => { await new Promise((r) => setTimeout(r, 30)); });
      const press = (key, extra = {}) => act(() => { window.dispatchEvent(new KeyboardEvent("keydown", { key, metaKey: true, bubbles: true, cancelable: true, ...extra })); });
      const all = () => { press("k"); press(","); press("j"); press("o"); press("n"); press("1"); press("f"); press("s"); press("N", { shiftKey: true }); press("W", { shiftKey: true }); };
      all();
      expect(screen.queryByRole("combobox")).toBeNull();
      state.localStatus = "online";
      await act(async () => { listeners["connection-status"]?.({ payload: { id: "local", status: "online" } }); });
      await waitFor(() => expect(selected("alpi")).toBe(true));
      expect(inSettingsView()).toBe(false);
      expect(container.querySelector("aside")).not.toBeNull();
      press("k");
      expect(await screen.findByRole("combobox")).toBeInTheDocument();
      press("k");
      press(",");
      await waitFor(() => expect(inSettingsView()).toBe(true));
    });
  });

  it("keeps the welcome on screen until the daemon answers, so the sidebar never mounts with the offline banner", async () => {
    const state = daemon({ localStatus: "offline", local: "absent" });
    const base = invoke.getMockImplementation();
    invoke.mockImplementation(async (cmd, args) => {
      if (cmd === "local_daemon_start") {
        state.calls.push([cmd, args]);
        state.local = "running";
        return "started";
      }
      return base(cmd, args);
    });
    const { container } = render(<App />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Install and start alpi" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Install and start alpi" }));
    await waitFor(() => expect(state.calls.some(([cmd]) => cmd === "local_daemon_start")).toBe(true));
    await act(async () => { await new Promise((r) => setTimeout(r, 50)); });
    expect(screen.getByRole("heading", { name: "Starting alpi…" })).toBeInTheDocument();
    expect(container.querySelector("aside")).toBeNull();
    expect(screen.queryByText(/not answering/)).toBeNull();
    state.localStatus = "online";
    await act(async () => { listeners["connection-status"]?.({ payload: { id: "local", status: "online" } }); });
    await waitFor(() => expect(selected("alpi")).toBe(true));
    expect(container.querySelector("aside")).not.toBeNull();
  });

  it("installs and starts from the welcome, then opens the roster", async () => {
    const state = daemon({ localStatus: "offline", local: "absent" });
    render(<App />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Install and start alpi" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Install and start alpi" }));
    await waitFor(() => expect(selected("alpi")).toBe(true));
    expect(state.calls.filter(([cmd]) => cmd === "local_daemon_install")).toHaveLength(1);
    expect(state.calls.filter(([cmd]) => cmd === "local_daemon_start")).toHaveLength(1);
  });

  it("retries a failed install without starting an absent daemon", async () => {
    const state = daemon({ localStatus: "offline", local: "absent" });
    state.installFails = "Download failed";
    render(<App />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Install and start alpi" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Install and start alpi" }));
    await waitFor(() => expect(screen.getByText("alpi couldn't be installed")).toBeInTheDocument());
    expect(state.calls.some(([cmd]) => cmd === "local_daemon_start")).toBe(false);
    state.installFails = null;
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(selected("alpi")).toBe(true));
  });

  it("retries only the start when installation succeeded but starting failed", async () => {
    const state = daemon({ localStatus: "offline", local: "absent", startFails: "Start failed" });
    render(<App />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Install and start alpi" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Install and start alpi" }));
    await waitFor(() => expect(screen.getByText("alpi didn't start")).toBeInTheDocument());
    state.startFails = null;
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(selected("alpi")).toBe(true));
    expect(state.calls.filter(([cmd]) => cmd === "local_daemon_install")).toHaveLength(1);
    expect(state.calls.filter(([cmd]) => cmd === "local_daemon_start")).toHaveLength(2);
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

  it("names this computer in one mono line under the composer until the first message is accepted", async () => {
    daemon();
    const { unmount } = render(<App />);
    await waitFor(() => expect(screen.getByText(HINT_LINE)).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "Got it" })).toBeNull();
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("textbox")));
    unmount();
    localStorage.setItem("alpi.firstRunHint.v1", "seen");
    render(<App />);
    await waitFor(() => expect(selected("alpi")).toBe(true));
    expect(screen.queryByText(HINT_LINE)).toBeNull();
  });

  async function sendFirstMessage(verdictPayload) {
    const state = daemon();
    const chatListeners = [];
    listen.mockImplementation(async (name, cb) => {
      listeners[name] = cb;
      if (name === "chat-event") chatListeners.push(cb);
      return () => {};
    });
    window.notify = vi.fn();
    render(<App />);
    await waitFor(() => expect(screen.getByText(HINT_LINE)).toBeInTheDocument());
    const box = screen.getByPlaceholderText(/Message/);
    fireEvent.change(box, { target: { value: "hello" } });
    fireEvent.keyDown(box, { key: "Enter", metaKey: true });
    await waitFor(() => expect(state.calls.filter(([c]) => c === "chat_send_stream")).toHaveLength(1));
    const [, args] = state.calls.find(([c]) => c === "chat_send_stream");
    await act(async () => {
      chatListeners.forEach((cb) => cb({ payload: { request_id: args.requestId, ...verdictPayload } }));
    });
  }

  it("drops the hint line and remembers it once the daemon accepts the first message", async () => {
    await sendFirstMessage({ kind: "delta", text: "hi" });
    await waitFor(() => expect(screen.queryByText(HINT_LINE)).toBeNull());
    expect(localStorage.getItem("alpi.firstRunHint.v1")).toBe("seen");
  });

  it("keeps the hint line and writes nothing when the daemon refuses the first message", async () => {
    await sendFirstMessage({ kind: "error", text: "session already has a running turn" });
    await waitFor(() => expect(screen.getByPlaceholderText(/Message/).value).toBe("hello"));
    expect(screen.getByText(HINT_LINE)).toBeInTheDocument();
    expect(localStorage.getItem("alpi.firstRunHint.v1")).toBeNull();
  });

  it("shows the hint line only in a profile chat", async () => {
    daemon();
    render(<App />);
    await waitFor(() => expect(screen.getByText(HINT_LINE)).toBeInTheDocument());
    fireEvent.click(row("crew"));
    await waitFor(() => expect(selected("crew")).toBe(true));
    expect(screen.queryByText(HINT_LINE)).toBeNull();
    fireEvent.click(row("doc"));
    await waitFor(() => expect(screen.getByText(HINT_LINE)).toBeInTheDocument());
    expect(localStorage.getItem("alpi.firstRunHint.v1")).toBeNull();
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

it("refreshes pipeline status and spend on terminal events, without reloading per post", async () => {
  _resetDaemonBus();
  daemon();
  render(<App />);
  await waitFor(() => expect(selected("alpi")).toBe(true));
  await waitFor(() => expect(listeners["daemon-event"]).toBeTruthy());
  const count = () => invoke.mock.calls.filter(([cmd]) => cmd === "workgroups").length;
  const before = count();
  await act(async () => {
    for (let i = 0; i < 15; i += 1) {
      listeners["daemon-event"]({ payload: { connection_id: "local", frame: { event: "wg.post", data: { profile: "doc", wg_id: "crew" } } } });
    }
    await new Promise((resolve) => setTimeout(resolve, 650));
  });
  expect(count()).toBe(before);
  await act(async () => {
    listeners["daemon-event"]({ payload: { connection_id: "local", frame: { event: "wg.done", data: { profile: "doc", wg_id: "crew" } } } });
    await new Promise((resolve) => setTimeout(resolve, 650));
  });
  expect(count()).toBe(before + 1);
});
