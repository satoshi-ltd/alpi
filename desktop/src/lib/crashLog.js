const KEY = "alpi:lastCrash:v1";
const MAX_STACK = 4000;

function clip(value) {
  const text = String(value ?? "");
  return text.length > MAX_STACK ? `${text.slice(0, MAX_STACK)}…` : text;
}

export function describeError(error) {
  if (error instanceof Error) {
    return { name: error.name, message: error.message, stack: clip(error.stack) };
  }
  return { name: "Error", message: clip(error), stack: "" };
}

export function recordCrash(error, extra = {}) {
  const entry = {
    at: new Date().toISOString(),
    ...describeError(error),
    ...extra,
  };
  try {
    localStorage.setItem(KEY, JSON.stringify(entry));
  } catch {
    // storage unavailable: the in-page fallback still shows the crash
  }
  return entry;
}

export function readCrash() {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function clearCrash() {
  try {
    localStorage.removeItem(KEY);
  } catch {}
}

export function formatCrash(entry) {
  if (!entry) return "";
  const lines = [
    `when: ${entry.at}`,
    `phase: ${entry.phase || "render"}`,
    `${entry.name}: ${entry.message}`,
  ];
  if (entry.stack) lines.push("", "stack:", entry.stack);
  if (entry.componentStack) lines.push("", "component stack:", entry.componentStack);
  if (entry.url) lines.push("", `url: ${entry.url}`);
  return lines.join("\n");
}

export function installGlobalCrashHandlers() {
  if (typeof window === "undefined" || window.__alpiCrashHandlers) return;
  window.__alpiCrashHandlers = true;
  window.addEventListener("error", (event) => {
    if (event?.error) recordCrash(event.error, { phase: "window.error" });
  });
  window.addEventListener("unhandledrejection", (event) => {
    recordCrash(event?.reason, { phase: "unhandledrejection" });
  });
}
