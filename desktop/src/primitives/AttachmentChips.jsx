import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { FileIcon, FileTextIcon, FileCodeIcon, XIcon } from "./icons.jsx";
import { fileKind, fileTypeLabel, fmtSize } from "../lib/fileKind.js";
import styles from "./AttachmentChips.module.css";

const ICON = { code: FileCodeIcon, text: FileTextIcon, file: FileIcon, image: FileIcon };

function Thumb({ kind, path, mime, name }) {
  const [src, setSrc] = useState(null);
  useEffect(() => {
    let alive = true;
    setSrc(null);
    if (kind !== "image" || !path) return;
    // User-picked file: its own directory is the allowed root (the user chose it).
    const dir = path.replace(/[/\\][^/\\]*$/, "");
    (async () => {
      try {
        const url = await invoke("attachment_thumb", { path, mime: mime || "", roots: dir ? [dir] : [] });
        if (alive) setSrc(url || null);
      } catch {
        if (alive) setSrc(null);
      }
    })();
    return () => { alive = false; };
  }, [kind, path, mime]);

  if (src) return <img className={styles.thumb} src={src} alt={name} />;
  const Glyph = ICON[kind] || FileIcon;
  return (
    <span className={styles.iconBox} aria-hidden>
      <Glyph />
    </span>
  );
}

const MESSAGE_MAX = 4;

export default function AttachmentChips({ items, onRemove, variant = "composer" }) {
  if (!items?.length) return null;
  const message = variant === "message";
  const shown = message ? items.slice(0, MESSAGE_MAX) : items;
  const hidden = items.length - shown.length;
  return (
    <div className={message ? styles.list : styles.row}>
      {shown.map((a, i) => {
        const kind = fileKind(a.name, a.mime);
        const subtitle = message
          ? `${fileTypeLabel(a.name, a.mime)} · ${fmtSize(a.size ?? 0)}`
          : fmtSize(a.size ?? 0);
        return (
          <div key={a.path || i} className={`${styles.card} ${message ? styles.cardMessage : ""}`}>
            <Thumb kind={kind} path={a.path} mime={a.mime} name={a.name} />
            <span className={styles.meta}>
              <span className={styles.name} title={a.name}>{a.name}</span>
              <span className={styles.size}>{subtitle}</span>
            </span>
            {!message && onRemove && (
              <button
                type="button"
                className={styles.remove}
                aria-label={`Remove ${a.name}`}
                onClick={() => onRemove(i)}
              >
                <XIcon />
              </button>
            )}
          </div>
        );
      })}
      {hidden > 0 && (
        <div className={styles.more}>+{hidden} more file{hidden > 1 ? "s" : ""}</div>
      )}
    </div>
  );
}
