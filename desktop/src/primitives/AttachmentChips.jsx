import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { FileIcon, FileTextIcon, FileCodeIcon, XIcon, SpinnerIcon } from "./icons.jsx";
import { useNotify } from "./Notification.jsx";
import Tip from "./Tip.jsx";
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

function MessageChip({ a, profile, connectionId }) {
  const notify = useNotify();
  const [busy, setBusy] = useState(false);
  const kind = fileKind(a.name, a.mime);
  const subtitle = `${fileTypeLabel(a.name, a.mime)} · ${fmtSize(a.size ?? 0)}`;

  async function onDownload() {
    if (busy) return;
    setBusy(true);
    try {
      const saved = await invoke("download_attachment", {
        profile, path: a.path, connectionId: connectionId ?? null,
      });
      if (saved) {
        notify?.({
          message: `Saved ${a.name}`,
          variant: "success",
          action: "Reveal",
          onAction: () => invoke("reveal_in_finder", { path: saved }).catch(() => {}),
        });
      }
    } catch (e) {
      notify?.({ message: `Couldn't download ${a.name}: ${e}`, variant: "error" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      className={`${styles.card} ${styles.cardMessage}`}
      style={{ cursor: busy ? "default" : "pointer", font: "inherit", textAlign: "left" }}
      title={busy ? `Downloading ${a.name}…` : `Download ${a.name}`}
      onClick={onDownload}
      disabled={busy}
    >
      {busy ? (
        <span className={styles.iconBox} aria-hidden>
          <SpinnerIcon style={{ width: 16, height: 16 }} />
        </span>
      ) : (
        <Thumb kind={kind} path={a.path} mime={a.mime} name={a.name} />
      )}
      <span className={styles.meta}>
        <span className={styles.name} title={a.name}>{a.name}</span>
        <span className={styles.size}>{subtitle}</span>
      </span>
    </button>
  );
}

const MESSAGE_MAX = 4;

export default function AttachmentChips({ items, onRemove, variant = "composer", profile, connectionId }) {
  if (!items?.length) return null;
  const message = variant === "message";
  const shown = message ? items.slice(0, MESSAGE_MAX) : items;
  const hidden = items.length - shown.length;
  return (
    <div className={message ? styles.list : styles.row}>
      {shown.map((a, i) => {
        if (message && a.path) {
          return <MessageChip key={a.path || i} a={a} profile={profile} connectionId={connectionId} />;
        }
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
              <Tip text="Remove attachment" side="up">
                <button
                  type="button"
                  className={styles.remove}
                  aria-label={`Remove ${a.name}`}
                  onClick={() => onRemove(i)}
                >
                  <XIcon />
                </button>
              </Tip>
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
