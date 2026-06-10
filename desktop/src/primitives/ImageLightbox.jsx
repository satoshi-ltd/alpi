import { useEffect } from "react";
import { createPortal } from "react-dom";
import { invoke } from "@tauri-apps/api/core";

import IconBtn from "./IconBtn.jsx";
import { XIcon, DownloadIcon } from "./icons.jsx";
import { getImageRoots } from "../lib/imageRoots.js";
import styles from "./ImageLightbox.module.css";

export default function ImageLightbox({ src, caption, path, onClose }) {
  useEffect(() => {
    function onKey(e) {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose?.();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (!src) return null;

  return createPortal(
    <div className={styles.backdrop} onClick={onClose}>
      <div className={`anim-fade ${styles.actions}`} onClick={(e) => e.stopPropagation()}>
        {path && (
          <IconBtn
            aria-label="Download image"
            className={styles.action}
            onClick={() => invoke("save_file_as", { path, roots: getImageRoots() }).catch(() => {})}
          >
            <DownloadIcon />
          </IconBtn>
        )}
        <IconBtn aria-label="Close" className={styles.action} onClick={onClose}>
          <XIcon />
        </IconBtn>
      </div>
      <figure className={`anim-pop ${styles.figure}`} onClick={(e) => e.stopPropagation()}>
        <img className={styles.img} src={src} alt={caption || ""} />
        {caption && <figcaption className={styles.caption}>{caption}</figcaption>}
      </figure>
    </div>,
    document.body,
  );
}
