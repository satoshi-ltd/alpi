import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { check } from "@tauri-apps/plugin-updater";
import { relaunch } from "@tauri-apps/plugin-process";

const SIX_HOURS_MS = 6 * 60 * 60 * 1000;

let pending = null;

async function announce(available, version) {
  try {
    await invoke("tray_announce_update", { available, version: version ?? null });
  } catch {
    // Tray not ready yet — non-fatal; the next tick will retry.
  }
}

async function poll() {
  try {
    const update = await check();
    if (update?.available) {
      pending = update;
      await announce(true, update.version);
    } else {
      pending = null;
      await announce(false, null);
    }
  } catch (e) {
    // Network errors, missing manifest, signature mismatch — all silent.
    // The user retries by relaunching or clicking a future "Check now".
    console.warn("updater check failed:", e);
  }
}

async function applyUpdate() {
  if (!pending) return;
  try {
    await pending.downloadAndInstall();
    await relaunch();
  } catch (e) {
    console.error("update install failed:", e);
  }
}

export function installUpdater() {
  poll();
  const id = setInterval(poll, SIX_HOURS_MS);
  const off = listen("tray:update-clicked", () => {
    applyUpdate();
  });
  return () => {
    clearInterval(id);
    off.then((fn) => fn());
  };
}
