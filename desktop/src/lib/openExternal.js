import { openUrl } from "@tauri-apps/plugin-opener";

export const EXTERNAL_HREF = /^(https?:|mailto:)/i;

export function openExternal(href) {
  if (!EXTERNAL_HREF.test(String(href || ""))) return Promise.resolve(false);
  return openUrl(href).then(() => true);
}

export function onExternalClick(event, href) {
  event.preventDefault();
  openExternal(href).catch(() => {});
}

export function installExternalLinkGuard(doc = document) {
  const onClick = (event) => {
    const anchor = event.target?.closest?.("a[href]");
    if (!anchor || anchor.dataset.externalHandled != null) return;
    const href = anchor.getAttribute("href") || "";
    if (!EXTERNAL_HREF.test(href)) return;
    onExternalClick(event, href);
  };
  doc.addEventListener("click", onClick);
  return () => doc.removeEventListener("click", onClick);
}
