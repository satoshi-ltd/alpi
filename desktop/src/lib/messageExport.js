import { invoke } from "@tauri-apps/api/core";
import { exportArticle, exportCss, exportFileName, exportMarkdown } from "../../../common/messageExport.mjs";

export const PRINT_ROOT_CLASS = "alpi-print-root";

const PRINT_RULES = `@media screen { .${PRINT_ROOT_CLASS} { display: none !important; } }
@media print {
  html, body { background: #ffffff !important; height: auto !important; overflow: visible !important; }
  body > *:not(.${PRINT_ROOT_CLASS}) { display: none !important; }
}`;

const PRINT_ROOT_TTL_MS = 10 * 60 * 1000;
let release = null;

export function clearPrintSheet() {
  release?.();
}

export function mountPrintSheet(message, accent) {
  clearPrintSheet();
  const root = document.createElement("div");
  root.className = PRINT_ROOT_CLASS;
  root.innerHTML = `<style>${PRINT_RULES}${exportCss(accent)}</style>${exportArticle(message)}`;
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
