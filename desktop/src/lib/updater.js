import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { check } from "@tauri-apps/plugin-updater";
import { exit, relaunch } from "@tauri-apps/plugin-process";
import { safeUnlisten } from "./tauri-listen.js";

const SIX_HOURS_MS = 6 * 60 * 60 * 1000;

let pending = null;
let installRun = null;
let state = {
  checking: false,
  available: false,
  version: null,
  error: null,
  errorPhase: null,
  installing: false,
  phase: "idle",
  progress: null,
};
const listeners = new Set();

function emit() {
  for (const listener of listeners) listener(state);
}

function setState(patch) {
  state = { ...state, ...patch };
  emit();
  return state;
}

export function subscribeUpdater(listener) {
  listeners.add(listener);
  listener(state);
  return () => listeners.delete(listener);
}

export function describeUpdaterError(raw, phase = "check") {
  const s = String(raw || "").toLowerCase();
  if (phase === "restart") return "Update installed — quit and reopen Alpi to finish";
  if (s.includes("404") || s.includes("not found")) {
    return phase === "install" ? "The update file is missing on the server" : "No update manifest on the server";
  }
  if (s.includes("platform") || s.includes("fallback")) {
    return "No build available for your platform yet";
  }
  if (s.includes("signature") || s.includes("signing")) {
    return "Update signature check failed";
  }
  if (s.includes("network") || s.includes("fetch") || s.includes("dns") || s.includes("timeout") || s.includes("connection")) {
    return phase === "install" ? "Download interrupted — check your connection" : "Couldn't reach update server";
  }
  return phase === "install" ? "Couldn't install the update" : "Couldn't check for updates";
}

async function announce(available, version) {
  try {
    await invoke("tray_announce_update", { available, version: version ?? null });
  } catch {
    // Tray not ready yet — non-fatal; the next tick will retry.
  }
}

export async function checkForUpdates() {
  if (state.installing) return state;
  if (typeof navigator !== "undefined" && navigator.onLine === false) {
    return setState({ checking: false, error: null, errorPhase: null });
  }
  setState({ checking: true, error: null, errorPhase: null });
  try {
    const update = await check();
    if (update?.available) {
      pending = update;
      const next = setState({ checking: false, available: true, version: update.version, error: null, errorPhase: null });
      await announce(true, update.version);
      return next;
    }
    pending = null;
    const next = setState({ checking: false, available: false, version: null, error: null, errorPhase: null });
    await announce(false, null);
    return next;
  } catch (e) {
    // A failed check does not forget an update already found; the download may still work.
    return setState({
      checking: false,
      available: !!pending,
      version: pending?.version ?? null,
      error: String(e),
      errorPhase: "check",
    });
  }
}

function downloadTracker() {
  let total = 0;
  let got = 0;
  return (event) => {
    if (event?.event === "Started") {
      total = Number(event.data?.contentLength) || 0;
      got = 0;
      setState({ phase: "downloading", progress: total ? 0 : null });
    } else if (event?.event === "Progress") {
      got += Number(event.data?.chunkLength) || 0;
      setState({ progress: total ? Math.min(1, got / total) : null });
    } else if (event?.event === "Finished") {
      setState({ phase: "installing", progress: 1 });
    }
  };
}

export function applyPendingUpdate() {
  if (!pending) return Promise.resolve(false);
  if (installRun) return installRun;
  if (state.installing) return Promise.resolve(false);
  installRun = (async () => {
    setState({ installing: true, phase: "downloading", progress: null, error: null, errorPhase: null });
    try {
      await pending.downloadAndInstall(downloadTracker());
      setState({ phase: "restarting", progress: 1 });
    } catch (e) {
      setState({ installing: false, phase: "idle", progress: null, available: true, error: String(e), errorPhase: "install" });
      throw e;
    } finally {
      installRun = null;
    }
    try {
      await relaunch();
    } catch (e) {
      setState({ installing: false, phase: "installed", progress: null, error: String(e), errorPhase: "restart" });
      throw e;
    }
    return true;
  })();
  return installRun;
}

// The bundle on disk is already the new version; quitting lets the OS start it fresh.
export async function quitForUpdate() {
  try {
    await exit(0);
  } catch {
    return;
  }
}

export function installUpdater() {
  checkForUpdates();
  const id = setInterval(checkForUpdates, SIX_HOURS_MS);
  const onOnline = () => checkForUpdates();
  if (typeof window !== "undefined") {
    window.addEventListener("online", onOnline);
  }
  let cancelled = false;
  let unlisten = null;
  listen("tray:update-clicked", () => {
    applyPendingUpdate().catch(() => {});
  })
    .then((fn) => {
      if (cancelled) safeUnlisten(fn);
      else unlisten = fn;
    })
    .catch(() => {});
  return () => {
    cancelled = true;
    clearInterval(id);
    if (typeof window !== "undefined") {
      window.removeEventListener("online", onOnline);
    }
    safeUnlisten(unlisten);
  };
}

export function _resetUpdaterForTests() {
  pending = null;
  installRun = null;
  state = { checking: false, available: false, version: null, error: null, errorPhase: null, installing: false, phase: "idle", progress: null };
  listeners.clear();
}
