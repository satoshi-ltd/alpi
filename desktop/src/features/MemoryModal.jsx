import { useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { BrowseModal, IconBtn, EditIcon, I } from "../primitives/index.js";
import { useNotify } from "../primitives/Notification.jsx";
import { subscribeDaemonEvent } from "../lib/daemon-bus.js";
import CodeView from "../primitives/CodeView.jsx";
import shell from "../primitives/BrowseModal.module.css";
import MarkdownBody from "../primitives/MarkdownBody.jsx";
import { shortDate } from "../lib/time.js";
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

export default function MemoryModal({ open, onClose, profile, connectionId, canEdit = false }) {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(null);
  const [reloadTick, setReloadTick] = useState(0);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [rev, setRev] = useState(null);
  const [baseline, setBaseline] = useState("");
  const [saving, setSaving] = useState(false);
  const [conflicted, setConflicted] = useState(false);
  const editingRef = useRef(false);
  useEffect(() => { editingRef.current = editing; }, [editing]);
  const notify = useNotify();

  useEffect(() => {
    if (!open || !profile) return undefined;
    let cancelled = false;
    setFiles([]);
    setError(null);
    setLoading(true);
    Promise.all([
      invoke("profile_memory", { profile, connectionId }),
      invoke("memory_usage", { profile, connectionId }).catch(() => null),
    ])
      .then(([data, usage]) => {
        if (cancelled) return;
        setFiles(FILES.map(({ name, label }) => {
          const raw = data?.[name] || "";
          const u = usage?.[name];
          return {
            name, label, raw, content: stripMemoryDelimiters(raw), size: humanBytes(raw.length),
            pct: u?.pct ?? null, over: u?.over ?? false, updatedAt: u?.updated_at ?? null,
          };
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
  }, [open, profile, connectionId, reloadTick]);

  useEffect(() => { setEditing(false); }, [selected?.name, open]);

  useEffect(() => {
    if (!open || !profile) return undefined;
    return subscribeDaemonEvent((event) => {
      const payload = event?.payload ?? {};
      const frame = payload.frame ?? payload;
      if (frame?.event !== "memory_changed" || frame?.data?.profile !== profile) return;
      if (connectionId && payload.connection_id && payload.connection_id !== connectionId) return;
      if (!editingRef.current) setReloadTick((t) => t + 1);
    });
  }, [open, profile, connectionId]);

  useEffect(() => {
    if (!files.length) { if (selected) setSelected(null); return; }
    if (!files.some((f) => f.name === selected?.name)) setSelected(files[0]);
  }, [files, selected]);

  const filtered = useMemo(() => files.filter((f) => matchesFile(f, query)), [files, query]);
  const active = files.find((f) => f.name === selected?.name) || null;
  const dirty = editing && draft !== baseline;

  function requestClose() {
    if (dirty && !globalThis.confirm?.("Discard your unsaved edits?")) return;
    onClose?.();
  }

  async function startEdit() {
    if (!active) return;
    try {
      const res = await invoke("memory_read", { profile, name: active.name, connectionId });
      setDraft(res?.text ?? "");
      setBaseline(res?.text ?? "");
      setRev(res?.rev ?? null);
      setConflicted(false);
      setEditing(true);
    } catch (e) {
      notify?.({ message: `Couldn't open ${active.name}: ${e}`, variant: "error" });
    }
  }

  function cancelEdit() {
    setEditing(false);
    setConflicted(false);
    setReloadTick((t) => t + 1);
  }

  async function save() {
    if (!active || saving) return;
    setSaving(true);
    try {
      let useRev = rev;
      if (conflicted) {
        const r = await invoke("memory_read", { profile, name: active.name, connectionId });
        useRev = r?.rev ?? null;
        setRev(useRev);
      }
      await invoke("memory_write", { profile, name: active.name, text: draft, rev: useRev, connectionId });
      setEditing(false);
      setConflicted(false);
      setReloadTick((t) => t + 1);
      notify?.({ message: `Saved ${active.name} — live next message`, variant: "success" });
    } catch (e) {
      if (String(e).includes("conflict")) {
        setConflicted(true);
        notify?.({
          message: `${active.name} changed elsewhere — your edits are kept. Save again to overwrite, or Cancel to reopen the latest.`,
          variant: "error",
        });
      } else {
        notify?.({ message: `Couldn't save ${active.name}: ${e}`, variant: "error" });
      }
    } finally {
      setSaving(false);
    }
  }

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
            <span className={`${shell.sizeTag} ${f.over ? styles.over : ""}`}>
              {f.pct != null ? `${f.pct}%` : f.size}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );

  return (
    <BrowseModal
      open={open}
      onClose={requestClose}
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
            <span className={shell.sizeTag}>{active.size}</span>
            <span className={shell.detailMetaSpacer} />
            {editing ? (
              <>
                <IconBtn tip={conflicted ? "Overwrite" : "Save"} onClick={save} disabled={saving}><I.Check /></IconBtn>
                <IconBtn tip="Cancel" onClick={cancelEdit} disabled={saving}><I.X /></IconBtn>
              </>
            ) : (
              <>
                {active.updatedAt ? (
                  <span className={styles.detailInfo}>{shortDate(active.updatedAt)}</span>
                ) : null}
                {canEdit ? <IconBtn tip="Edit" onClick={startEdit}><EditIcon /></IconBtn> : null}
              </>
            )}
          </div>
          <div className={shell.detailScroll}>
            {editing ? (
              <CodeView editable text={draft} onChange={setDraft} ariaLabel={`Edit ${active.name}`} />
            ) : active.content ? (
              <MarkdownBody source={active.content} mono />
            ) : (
              <em className={styles.emptyNote}>(empty)</em>
            )}
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
