import { formatCrash, installGlobalCrashHandlers, recordCrash } from "./crashLog.js";

function setStyle(element, value) {
  element.setAttribute("style", value);
}

async function copyReport(text, button) {
  try {
    if (!navigator.clipboard?.writeText) throw new Error("Clipboard unavailable");
    await navigator.clipboard.writeText(text);
    button.textContent = "Copied to clipboard";
  } catch {
    button.textContent = "Copy failed — select details";
  }
}

export function renderBootstrapFailure(error) {
  const entry = recordCrash(error, {
    phase: "bootstrap",
    url: typeof window !== "undefined" ? window.location?.href : "",
  });
  const root = document.getElementById("root");
  if (!root) return;
  root.textContent = "";

  const box = document.createElement("div");
  setStyle(box, "display:flex;flex-direction:column;gap:16px;padding:40px;font:13px/1.5 ui-sans-serif,system-ui;color:#111;background:#fff;height:100vh;box-sizing:border-box;overflow:auto");
  const title = document.createElement("div");
  setStyle(title, "font-size:15px;font-weight:600");
  title.textContent = "Alpi failed to start";
  const lede = document.createElement("div");
  lede.textContent = "The daemon and running agents are separate from this window and may still be working.";
  const pre = document.createElement("pre");
  setStyle(pre, "white-space:pre-wrap;word-break:break-word;font:11px/1.5 ui-monospace,SFMono-Regular,monospace;background:#f6f6f6;border:1px solid #ddd;border-radius:8px;padding:16px;margin:0");
  pre.textContent = formatCrash(entry);
  const actions = document.createElement("div");
  setStyle(actions, "display:flex;gap:8px");
  const reload = document.createElement("button");
  setStyle(reload, "padding:8px 20px;border-radius:8px;border:1px solid #111;background:#111;color:#fff;cursor:pointer");
  reload.textContent = "Reload";
  reload.onclick = () => window.location.reload();
  const copy = document.createElement("button");
  setStyle(copy, "padding:8px 20px;border-radius:8px;border:1px solid #ccc;background:#fff;cursor:pointer");
  copy.textContent = "Copy details";
  copy.onclick = () => void copyReport(pre.textContent, copy);
  actions.append(reload, copy);
  box.append(title, lede, pre, actions);
  root.append(box);
}

export async function startApp(loadBootstrap) {
  installGlobalCrashHandlers();
  try {
    const loaded = await loadBootstrap();
    await loaded.bootstrap();
  } catch (error) {
    renderBootstrapFailure(error);
  }
}
