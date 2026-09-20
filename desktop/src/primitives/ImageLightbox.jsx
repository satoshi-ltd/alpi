import { OverlayScope, useOverlay } from "../hooks/useOverlay.js";
import { useRef } from "react";
import { createPortal } from "react-dom";
import { invoke } from "@tauri-apps/api/core";

import IconBtn from "./IconBtn.jsx";
import { XIcon, DownloadIcon } from "./icons.jsx";
import { getImageRoots } from "../lib/imageRoots.js";
import styles from "./ImageLightbox.module.css";

export default function ImageLightbox({ src, caption, path, onClose }) {
  const ref = useRef(null);
  const isTop = useOverlay({ open: !!src, onClose, ref, modal: true });

  if (!src) return null;

  return createPortal(
    <OverlayScope overlay={isTop}>
      <div ref={ref} tabIndex={-1} role="dialog" aria-modal="true" aria-label={caption || "Image preview"} className={styles.backdrop} onClick={onClose}>
        <div className={`anim-fade ${styles.actions}`} onClick={(e) => e.stopPropagation()}>
          {path && (
            <IconBtn
              aria-label="Download image"
              tip="Download image"
              className={styles.action}
              onClick={() => invoke("save_file_as", { path, roots: getImageRoots() }).catch(() => {})}
            >
              <DownloadIcon />
            </IconBtn>
          )}
          <IconBtn aria-label="Close" tip="Close" className={styles.action} onClick={onClose}>
            <XIcon />
          </IconBtn>
        </div>
        <figure className={`anim-pop ${styles.figure}`} onClick={(e) => e.stopPropagation()}>
          <img className={styles.img} src={src} alt={caption || ""} />
          {caption && <figcaption className={styles.caption}>{caption}</figcaption>}
        </figure>
      </div>
    </OverlayScope>,
    document.body,
  );
}
