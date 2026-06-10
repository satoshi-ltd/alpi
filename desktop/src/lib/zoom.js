import { getCurrentWebview } from "@tauri-apps/api/webview";

const KEY = "alpi.ui.zoom";
const MIN = 0.7;
const MAX = 1.5;
const STEP = 0.1;

export function clampZoom(value) {
  const v = Number(value);
  if (!Number.isFinite(v)) return 1;
  return Math.min(MAX, Math.max(MIN, Math.round(v * 10) / 10));
}

export function nextZoom(current, direction) {
  if (direction === 0) return 1;
  return clampZoom(clampZoom(current) + direction * STEP);
}

export function storedZoom() {
  try {
    return clampZoom(localStorage.getItem(KEY) ?? 1);
  } catch {
    return 1;
  }
}

async function apply(zoom) {
  try {
    await getCurrentWebview().setZoom(zoom);
  } catch {
    /* zoom is cosmetic — never break the app over it */
  }
}

// Keydown instead of menu accelerators: e.key is layout-independent ("+" is unshifted on ES keyboards, Shift+= on US).
export function installZoomShortcuts() {
  apply(storedZoom());
  window.addEventListener("keydown", (e) => {
    if (!(e.metaKey || e.ctrlKey) || e.altKey) return;
    let direction = null;
    if (e.key === "+" || e.key === "=") direction = 1;
    else if (e.key === "-") direction = -1;
    else if (e.key === "0") direction = 0;
    if (direction === null) return;
    e.preventDefault();
    const zoom = nextZoom(storedZoom(), direction);
    try {
      localStorage.setItem(KEY, String(zoom));
    } catch {
      /* */
    }
    apply(zoom);
  });
}
