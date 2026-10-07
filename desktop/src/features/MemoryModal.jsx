import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { AlertBanner, IconBtn, EditIcon, I } from "../primitives/index.js";
import { useNotify } from "../primitives/Notification.jsx";
import { subscribeDaemonEvent } from "../lib/daemon-bus.js";
import CodeView from "../primitives/CodeView.jsx";
import shell from "../primitives/BrowseModal.module.css";
import { BrowseBody, BrowseShell, useBrowseCloseGuard } from "../primitives/BrowseModal.jsx";
import { PROFILE_PANELS } from "../lib/profilePanels.js";
import { SkeletonReader, SkeletonRows } from "../primitives/Skeleton.jsx";
import MarkdownBody from "../primitives/MarkdownBody.jsx";
import { shortDate } from "../lib/time.js";
import styles from "./MemoryModal.module.css";
import { EMPTY } from "../../../common/emptyCopy.mjs";
import { memoryBanner, memoryItem, memoryWord } from "../../../common/attention.mjs";
import { MEMORY_FILES, entryNote, memoryEntries } from "../../../common/memoryEntries.mjs";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function entryDate(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || ""));
  return m ? `${MONTHS[Number(m[2]) - 1]} ${Number(m[3])}` : String(iso || "");
}

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
  return [file.name, file.label, file.caption, file.content].filter(Boolean).join(" ").toLowerCase().includes(needle);
}

function Usage({ file, wide = false }) {
  if (file.used == null || !file.limit) return <span className={shell.sizeTag}>{file.size}</span>;
  const pct = Math.min(100, Math.round((file.used / file.limit) * 100));
  return (
    <span className={`${styles.usage} ${wide ? styles.usageWide : ""}`.trim()} data-over={file.over ? "" : undefined}>
      <span className={styles.meter} aria-hidden><span style={{ width: `${pct}%` }} /></span>
      <span className={styles.usageText}>{`${file.used.toLocaleString("en-US")} / ${file.limit.toLocaleString("en-US")}`}{wide ? ` · ${pct}%` : ""}</span>
    </span>
  );
}

export function MemoryPanel({ open = true, profile, connectionId, canEdit = false, owner = null, onSection = null, attention = null }) {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(null);
  const [reloadTick, setReloadTick] = useState(0);
  const [editingName, setEditingName] = useState(null);
  const [draft, setDraft] = useState("");
  const [rev, setRev] = useState(null);
  const [baseline, setBaseline] = useState("");
  const [saving, setSaving] = useState(false);
  const [conflicted, setConflicted] = useState(false);
  const ownerName = owner?.name ?? profile;
  const editingRef = useRef(false);
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
        setFiles(MEMORY_FILES.map(({ file: name, label, caption }) => {
          const raw = data?.[name] || "";
          const u = usage?.[name];
          return {
            name, label, caption: caption(ownerName), raw, content: stripMemoryDelimiters(raw), entries: memoryEntries(raw),
            size: humanBytes(raw.length), used: u?.used ?? null, limit: u?.limit ?? null,
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
  }, [open, profile, connectionId, reloadTick, ownerName]);


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
  const editing = editingName != null && editingName === active?.name;
  useEffect(() => { editingRef.current = editing; }, [editing]);
  const dirty = editing && draft !== baseline;

  const closeGuard = useCallback(() => !dirty || !!globalThis.confirm?.("Discard your unsaved edits?"), [dirty]);
  useBrowseCloseGuard(closeGuard);

  function pickFile(f) {
    if (f.name === selected?.name) return;
    if (!closeGuard()) return;
    setEditingName(null);
    setSelected(f);
  }

  async function startEdit() {
    if (!active) return;
    try {
      const res = await invoke("memory_read", { profile, name: active.name, connectionId });
      setDraft(res?.text ?? "");
      setBaseline(res?.text ?? "");
      setRev(res?.rev ?? null);
      setConflicted(false);
      setEditingName(active.name);
    } catch (e) {
      notify?.({ message: `Couldn't open ${active.name}: ${e}`, variant: "error" });
    }
  }

  function cancelEdit() {
    setEditingName(null);
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
      setEditingName(null);
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

  const flagged = active ? memoryItem(attention, active.name) : null;
  const banner = flagged ? memoryBanner(flagged) : null;

  const list = (
    <ul className={shell.list} role="listbox">
      {loading ? (
        <SkeletonRows as="li" count={3} />
      ) : error ? (
        <li className={shell.empty}>
          <span className={shell.emptyTitle}>Could not load memory</span>
          <span className={shell.emptyHint}>{error}</span>
        </li>
      ) : files.length === 0 ? (
        <li className={shell.empty}><span className={shell.emptyTitle}>{EMPTY.memory.title}</span></li>
      ) : filtered.length === 0 ? (
        <li className={shell.empty}>
          <span className={shell.emptyTitle}>{EMPTY.matches.title}</span>
          <span className={shell.emptyHint}>{EMPTY.matches.hint}</span>
        </li>
      ) : filtered.map((f) => {
        const item = memoryItem(attention, f.name);
        return (
        <li key={f.name}>
          <button
            type="button"
            className={`${shell.row} ${styles.fileRow} ${f.name === selected?.name ? shell.rowActive : ""}`}
            onClick={() => pickFile(f)}
            role="option"
            aria-selected={f.name === selected?.name}
          >
            <span className={styles.fileHead}>
              <span className={styles.fileLabel}>{f.label}</span>
              <span className={styles.fileName}>{f.name}</span>
              {item ? <span className={styles.flagWord}>{memoryWord(item)}</span> : null}
            </span>
            <Usage file={f} />
          </button>
        </li>
        );
      })}
    </ul>
  );

  return (
    <BrowseBody
      owner={owner}
      sections={owner ? PROFILE_PANELS : null}
      section="memory"
      onSection={onSection}
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
            <span className={styles.fileLabelLg}>{active.label}</span>
            <span className={styles.fileName}>{active.name}</span>
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
            {banner && !editing ? (
              <AlertBanner lead={banner.lead} detail={banner.detail} action={canEdit ? "Edit" : null} onAction={startEdit} />
            ) : null}
            {editing ? (
              <CodeView editable text={draft} onChange={setDraft} ariaLabel={`Edit ${active.name}`} />
            ) : active.entries.length ? (
              <>
                <div className={styles.caption}>
                  <span>{active.caption}</span>
                  <Usage file={active} wide />
                </div>
                <ol className={styles.entries}>
                  {active.entries.map((entry, i) => (
                    <li key={i} className={styles.entry}>
                      <MarkdownBody source={entry.text} />
                      {entryNote(entry, entryDate) ? <span className={styles.entryNote}>{entryNote(entry, entryDate)}</span> : null}
                    </li>
                  ))}
                </ol>
              </>
            ) : (
              <em className={styles.emptyNote}>(empty)</em>
            )}
          </div>
        </>
      ) : loading ? (
        <SkeletonReader />
      ) : (
        <div className={shell.detailEmpty}>Select a file.</div>
      )}
    </BrowseBody>
  );
}

export default function MemoryModal({ open, onClose, ...panel }) {
  return (
    <BrowseShell open={open} onClose={onClose} label="Memory">
      <MemoryPanel {...panel} />
    </BrowseShell>
  );
}
