import { createElement, useCallback, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

import { useRenderedMarkdown } from "../lib/markdownImages.js";
import { getImageRoots } from "../lib/imageRoots.js";
import ImageLightbox from "./ImageLightbox.jsx";

export default function Markdown({ source, as = "div", className = "", style }) {
  const html = useRenderedMarkdown(source);
  const [zoom, setZoom] = useState(null);

  const onClick = useCallback((e) => {
    const dl = e.target.closest?.(".md-figure .md-figdl");
    if (dl) {
      e.stopPropagation();
      const path = dl.closest("figure.md-figure")?.querySelector("img[data-src]")
        ?.getAttribute("data-src");
      if (path) invoke("save_file_as", { path, roots: getImageRoots() }).catch(() => {});
      return;
    }
    const img = e.target;
    if (img.tagName !== "IMG") return;
    const fig = img.closest("figure.md-figure");
    const src = img.getAttribute("src");
    if (!fig || !src) return;
    const caption = fig.querySelector(".md-figcap")?.textContent
      || fig.querySelector(".md-figcaption")?.textContent
      || img.getAttribute("alt") || "";
    setZoom({ src, caption, path: img.getAttribute("data-src") });
  }, []);

  if (!source) return null;

  return (
    <>
      {createElement(as, {
        className,
        style,
        onClick,
        dangerouslySetInnerHTML: { __html: html },
      })}
      {zoom && (
        <ImageLightbox
          src={zoom.src}
          caption={zoom.caption}
          path={zoom.path}
          onClose={() => setZoom(null)}
        />
      )}
    </>
  );
}
