import { useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { BrowseModal } from "../primitives/index.js";
import shell from "../primitives/BrowseModal.module.css";
import MarkdownBody from "../primitives/MarkdownBody.jsx";
import styles from "./MemoryModal.module.css";

const FILES = [
  { name: "AGENT.md", label: "Things alpi is" },
  { name: "MEMORY.md", label: "Things alpi has learned" },
  { name: "USER.md", label: "Things alpi knows about you" },
];

export function humanBytes(n) {
  const b = Number(n) || 0;
  if (b < 1024) return `${b}b`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)}kb`;
  return `${(b / (1024 * 1024)).toFixed(1)}mb`;
}

// `§` on its own line is alpi's v2 memory entry delimiter (alpi/memory.py).
export function stripMemoryDelimiters(text) {
  return String(text || "").replace(/^§$/gm, "").replace(/\n{3,}/g, "\n\n");
}

export function matchesFile(file, query) {
  const needle = String(query || "").trim().toLowerCase();
  if (!needle) return true;
  return [file.name, file.label, file.content].filter(Boolean).join(" ").toLowerCase().includes(needle);
}

export default function MemoryModal({ open, onClose, profile, connectionId }) {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    if (!open || !profile) return undefined;
    let cancelled = false;
    setFiles([]);
    setSelected(null);
    setError(null);
    setLoading(true);
    invoke("profile_memory", { profile, connectionId })
      .then((data) => {
        if (cancelled) return;
        setFiles(FILES.map(({ name, label }) => {
          const raw = data?.[name] || "";
          return { name, label, content: stripMemoryDelimiters(raw), size: humanBytes(raw.length) };
        }));
      })
      .catch((e) => {
        if (!cancelled) {
          setFiles([]);
          setError(String(e));
        }
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [open, profile, connectionId]);

  useEffect(() => {
    if (!files.length) { if (selected) setSelected(null); return; }
    if (!files.some((f) => f.name === selected?.name)) setSelected(files[0]);
  }, [files, selected]);

  const filtered = useMemo(() => files.filter((f) => matchesFile(f, query)), [files, query]);
  const active = files.find((f) => f.name === selected?.name) || null;

  const list = (
    <ul className={shell.list} role="listbox">
      {loading ? (
        <li className={shell.empty}>
          <span className={shell.emptyTitle}>Loading memory…</span>
        </li>
      ) : error ? (
        <li className={shell.empty}>
          <span className={shell.emptyTitle}>Could not load memory</span>
          <span className={shell.emptyHint}>{error}</span>
        </li>
      ) : files.length === 0 ? (
        <li className={shell.empty}><span className={shell.emptyTitle}>No memory files</span></li>
      ) : filtered.length === 0 ? (
        <li className={shell.empty}>
          <span className={shell.emptyTitle}>No matches</span>
          <span className={shell.emptyHint}>Try a different query, or clear it.</span>
        </li>
      ) : filtered.map((f) => (
        <li key={f.name}>
          <button
            type="button"
            className={`${shell.row} ${styles.fileRow} ${f.name === selected?.name ? shell.rowActive : ""}`}
            onClick={() => setSelected(f)}
            role="option"
            aria-selected={f.name === selected?.name}
          >
            <span className={styles.fileName}>{f.name}</span>
            <span className={shell.sizeTag}>{f.size}</span>
          </button>
        </li>
      ))}
    </ul>
  );

  return (
    <BrowseModal
      open={open}
      onClose={onClose}
      title="Memory"
      count={files.length}
      kicker="files read on every turn"
      search={{ value: query, onChange: setQuery, placeholder: "Search memory…", label: "Search memory" }}
      list={list}
      loading={loading}
      loadingLabel="Loading memory"
    >
      {active ? (
        <>
          <div className={shell.detailMeta}>
            <span className={styles.fileNameLg}>{active.name}</span>
            <span className={shell.detailMetaSpacer} />
            <span className={shell.sizeTag}>{active.size}</span>
          </div>
          <div className={shell.detailScroll}>
            {active.content ? <MarkdownBody source={active.content} mono /> : <em className={styles.emptyNote}>(empty)</em>}
          </div>
        </>
      ) : loading ? (
        <div className={shell.detailEmpty}>Loading memory…</div>
      ) : (
        <div className={shell.detailEmpty}>Select a file.</div>
      )}
    </BrowseModal>
  );
}
