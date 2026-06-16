import { useEffect, useReducer } from "react";
import { invoke } from "@tauri-apps/api/core";
import { renderMarkdown } from "./markdown.js";
import { getImageRoots } from "./imageRoots.js";

const IMG_MIME = {
  png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg",
  webp: "image/webp", gif: "image/gif",
};

// Module-level so a remount is instant and the baked src survives re-renders.
const cache = new Map();
const DATA_SRC = /<img\b[^>]*\bdata-src="([^"]+)"/g;

function pendingPaths(html) {
  const out = [];
  let m;
  while ((m = DATA_SRC.exec(html))) {
    if (!cache.has(m[1])) out.push(m[1]);
  }
  return out;
}

export function useRenderedMarkdown(source) {
  const [, force] = useReducer((x) => x + 1, 0);
  const base = source ? renderMarkdown(source) : "";
  useEffect(() => {
    if (!base) return undefined;
    const paths = pendingPaths(base);
    if (!paths.length) return undefined;
    let alive = true;
    Promise.all(paths.map((p) => {
      const mime = IMG_MIME[p.toLowerCase().split(".").pop()];
      if (!mime) { cache.set(p, null); return Promise.resolve(); }
      return invoke("attachment_thumb", { path: p, mime, roots: getImageRoots() })
        .then((url) => { if (url) cache.set(p, url); })
        .catch(() => {});
    })).then(() => { if (alive) force(); });
    return () => { alive = false; };
  }, [base]);
  if (!base) return "";
  return base.replace(DATA_SRC, (full, path) => {
    const url = cache.get(path);
    return url ? `${full} src="${url}"` : full;
  });
}
