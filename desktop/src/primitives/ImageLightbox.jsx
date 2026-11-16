import { OverlayScope, useOverlay } from "../hooks/useOverlay.js";
import { useRef } from "react";
import useExit from "../hooks/useExit.js";
import { createPortal } from "react-dom";
import { invoke } from "@tauri-apps/api/core";

import IconBtn from "./IconBtn.jsx";
import { XIcon, DownloadIcon } from "./icons.jsx";
import { getImageRoots } from "../lib/imageRoots.js";
import styles from "./ImageLightbox.module.css";

export default function ImageLightbox({ src, caption, path, onClose }) {
  const ref = useRef(null);
  const isTop = useOverlay({ open: !!src, onClose, ref, modal: true });
  const { mounted, closing } = useExit(!!src);
  const last = useRef({ src, caption, path });
  if (src) last.current = { src, caption, path };
  if (!mounted) return null;
  const shown = last.current;

  return createPortal(
    <OverlayScope overlay={isTop}>
      <div ref={ref} tabIndex={-1} role="dialog" aria-modal="true" aria-label={shown.caption || "Image preview"} className={`${closing ? "anim-overlay-out " : ""}${styles.backdrop}`} inert={closing || undefined} onClick={onClose}>
        <div className={`${closing ? "anim-overlay-out" : "anim-fade"} ${styles.actions}`} onClick={(e) => e.stopPropagation()}>
          {shown.path && (
            <IconBtn
              aria-label="Download image"
              tip="Download image"
              className={styles.action}
              onClick={() => invoke("save_file_as", { path: shown.path, roots: getImageRoots() }).catch(() => {})}
            >
              <DownloadIcon />
            </IconBtn>
          )}
          <IconBtn aria-label="Close" tip="Close" className={styles.action} onClick={onClose}>
            <XIcon />
          </IconBtn>
        </div>
        <figure className={`${closing ? "anim-dialog-out" : "anim-dialog"} ${styles.figure}`} onClick={(e) => e.stopPropagation()}>
          <img className={styles.img} src={shown.src} alt={shown.caption || ""} />
          {shown.caption && <figcaption className={styles.caption}>{shown.caption}</figcaption>}
        </figure>
      </div>
    </OverlayScope>,
    document.body,
  );
}
