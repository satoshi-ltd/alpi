import { invoke } from "@tauri-apps/api/core";
import { exportArticle, exportCss, exportFileName, exportMarkdown } from "../../../common/messageExport.mjs";
import { PAGE_CSS, PAGE_WIDTH, renderPrintPages } from "./printPages.js";

export const PRINT_ROOT_CLASS = "alpi-print-root";

const PRINT_RULES = `@media screen { .${PRINT_ROOT_CLASS} { display: none !important; } }
@media print {
  html, body { background: #ffffff !important; height: auto !important; overflow: visible !important; margin: 0 !important; padding: 0 !important; }
  body > *:not(.${PRINT_ROOT_CLASS}) { display: none !important; }
}`;

const PRINT_ROOT_TTL_MS = 10 * 60 * 1000;
export const FONT_WAIT_MS = 2000;
let release = null;

export function clearPrintSheet() {
  release?.();
}

function mountProbe(css) {
  const probe = document.createElement("div");
  probe.style.cssText = `position: absolute; left: -100000px; top: 0; width: ${PAGE_WIDTH}px; visibility: hidden;`;
  const style = document.createElement("style");
  style.textContent = css;
  probe.append(style);
  const host = document.createElement("div");
  host.className = "alpi-export";
  probe.append(host);
  document.body.appendChild(probe);
  return { probe, host };
}

async function settleFonts(message, css) {
  if (!document.fonts?.ready) return;
  const { probe, host } = mountProbe(css);
  let timer;
  try {
    host.innerHTML = exportArticle(message);
    void probe.offsetHeight;
    await Promise.race([document.fonts.ready, new Promise((resolve) => { timer = setTimeout(resolve, FONT_WAIT_MS); })]);
  } finally {
    clearTimeout(timer);
    probe.remove();
  }
}

function measuredPages(message, css, rectOf) {
  const { probe, host } = mountProbe(css);
  try {
    return renderPrintPages(message, host, rectOf);
  } finally {
    probe.remove();
  }
}

const printCss = (accent) => `${exportCss(accent)}${PAGE_CSS}`;

export function mountPrintSheet(message, accent, { rectOf } = {}) {
  clearPrintSheet();
  const css = printCss(accent);
  const pages = measuredPages(message, css, rectOf);
  const root = document.createElement("div");
  root.className = PRINT_ROOT_CLASS;
  root.innerHTML = `<style>${PRINT_RULES}${css}</style>`;
  root.append(pages);
  document.body.appendChild(root);
  const title = document.title;
  document.title = exportFileName(message, "pdf").replace(/\.pdf$/, "");
  const timer = setTimeout(clearPrintSheet, PRINT_ROOT_TTL_MS);
  const done = () => {
    clearTimeout(timer);
    window.removeEventListener("afterprint", done);
    root.remove();
    document.title = title;
    release = null;
  };
  window.addEventListener("afterprint", done);
  release = done;
  return root;
}

export async function printMessage(message, accent) {
  await settleFonts(message, printCss(accent));
  mountPrintSheet(message, accent);
  try {
    await window.print();
  } catch (e) {
    clearPrintSheet();
    throw e;
  }
}

export function downloadMarkdown(message) {
  return invoke("save_text_file", { name: exportFileName(message, "md"), content: exportMarkdown(message), dest: "download" });
}
