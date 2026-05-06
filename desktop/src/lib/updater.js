import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { check } from "@tauri-apps/plugin-updater";
import { relaunch } from "@tauri-apps/plugin-process";

const SIX_HOURS_MS = 6 * 60 * 60 * 1000;

let pending = null;
let state = {
  checking: false,
  available: false,
  version: null,
  error: null,
  installing: false,
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

async function announce(available, version) {
  try {
    await invoke("tray_announce_update", { available, version: version ?? null });
  } catch {
    // Tray not ready yet — non-fatal; the next tick will retry.
  }
}

export async function checkForUpdates() {
  setState({ checking: true, error: null });
  try {
    const update = await check();
    if (update?.available) {
      pending = update;
      const next = setState({
        checking: false,
        available: true,
        version: update.version,
        error: null,
      });
      await announce(true, update.version);
      return next;
    } else {
      pending = null;
      const next = setState({
        checking: false,
        available: false,
        version: null,
        error: null,
      });
      await announce(false, null);
      return next;
    }
  } catch (e) {
    // Network errors, missing manifest, signature mismatch — all silent.
    // The user retries by relaunching or clicking a future "Check now".
    console.warn("updater check failed:", e);
    pending = null;
    return setState({
      checking: false,
      available: false,
      version: null,
      error: String(e),
    });
  }
}

export async function applyPendingUpdate() {
  if (!pending) return false;
  setState({ installing: true, error: null });
  try {
    await pending.downloadAndInstall();
    await relaunch();
    return true;
  } catch (e) {
    console.error("update install failed:", e);
    setState({ installing: false, error: String(e) });
    throw e;
  }
}

export function installUpdater() {
  checkForUpdates();
  const id = setInterval(checkForUpdates, SIX_HOURS_MS);
  const off = listen("tray:update-clicked", () => {
    applyPendingUpdate();
  });
  return () => {
    clearInterval(id);
    off.then((fn) => fn());
  };
}
