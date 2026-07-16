import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { profileLabel } from "../../lib/profile-display.js";
import { createPortal } from "react-dom";
import { invoke } from "@tauri-apps/api/core";
import {
  Btn,
  Chip,
  ConfirmDelete,
  Dropdown,
  IconBtn,
  Tip,
  XIcon,
} from "../../primitives/index.js";
import EditableSessionTitle from "../../primitives/EditableSessionTitle.jsx";
import { removeSessionTitles } from "../../lib/session-titles.js";
import { useNotify } from "../../primitives/Notification.jsx";
import styles from "./ManageSessionsModal.module.css";

const DAY_MS = 86_400_000;
const PREVIEW_MAX = 80;
const FILTERS = [
  { key: "all", label: "All", match: () => true },
  { key: "ge30", label: "≥ 30 days", match: (s, now) => now - s.activityMs >= 30 * DAY_MS },
  { key: "ge90", label: "≥ 90 days", match: (s, now) => now - s.activityMs >= 90 * DAY_MS },
  { key: "lt3",  label: "< 3 turns",     match: (s) => (s.turn_count || 0) < 3 },
];
const SORTS = [
  { key: "activity", label: "Activity", pick: (s) => s.activityMs },
  { key: "size",     label: "Size",     pick: (s) => s.size_bytes || 0 },
  { key: "turns",    label: "Turns",    pick: (s) => s.turn_count || 0 },
  { key: "created",  label: "Created",  pick: (s) => (s.started_at || 0) * 1000 },
];

function previewOf(s) {
  const t = (s.first_user || "").trim();
  if (t) return t.length > PREVIEW_MAX ? `${t.slice(0, PREVIEW_MAX)}…` : t;
  return `(empty · ${(s.id || "").slice(0, 6)})`;
}

function activityMs(s) {
  const ts = s.updated_at ?? s.started_at ?? s.mtime ?? 0;
  return ts * 1000;
}

function formatKB(bytes) {
  if (!bytes || bytes <= 0) return "0 KB";
  const kb = bytes / 1024;
  if (kb < 1) return "< 1 KB";
  if (kb < 10) return `${kb.toFixed(1)} KB`;
  return `${Math.round(kb)} KB`;
}

function relativeActivity(ms) {
  if (!ms || ms <= 0) return "—";
  const now = Date.now();
  const diff = Math.max(0, now - ms);
  const startOfToday = new Date(); startOfToday.setHours(0, 0, 0, 0);
  if (ms >= startOfToday.getTime()) return "today";
  if (ms >= startOfToday.getTime() - DAY_MS) return "yesterday";
  const days = Math.floor(diff / DAY_MS);
  if (days < 7) return `${days}d`;
  if (days < 30) return `${Math.floor(days / 7)}w`;
  if (days < 365) return `${Math.floor(days / 30)}mo`;
  return `${Math.floor(days / 365)}y`;
}

export default function ManageSessionsModal({
  open,
  onClose,
  profile,
  connectionId = null,
  accent,
  currentSessionId,
  onDeleted,
}) {
  const notify = useNotify();
  const [rows, setRows] = useState([]);
  const [filterKey, setFilterKey] = useState("all");
  const [sortKey, setSortKey] = useState("activity");
  const [selected, setSelected] = useState(() => new Set());
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const lastIndexRef = useRef(null);

  const refresh = useCallback(async () => {
    if (!profile) return;
    try {
      const list = await invoke("sessions", { profile, limit: null });
      const enriched = (list || [])
        .filter((s) => s.kind === "chat")
        .map((s) => ({ ...s, activityMs: activityMs(s) }));
      setRows(enriched);
    } catch (e) {
      notify({ message: `sessions: ${String(e)}`, variant: "error", duration: 4000 });
    }
  }, [profile, notify]);

  useEffect(() => {
    if (!open) return;
    refresh();
    setSelected(new Set());
    lastIndexRef.current = null;
  }, [open, refresh]);

  useEffect(() => {
    setSelected(new Set());
    lastIndexRef.current = null;
  }, [filterKey]);

  const now = Date.now();
  const filtered = useMemo(() => {
    const matcher = (FILTERS.find((f) => f.key === filterKey) || FILTERS[0]).match;
    const filtered = rows.filter((s) => matcher(s, now));
    const pick = (SORTS.find((s) => s.key === sortKey) || SORTS[0]).pick;
    return [...filtered].sort((a, b) => pick(b) - pick(a));
  }, [rows, filterKey, sortKey, now]);

  const filterCounts = useMemo(() => {
    const counts = {};
    for (const f of FILTERS) counts[f.key] = rows.filter((s) => f.match(s, now)).length;
    return counts;
  }, [rows, now]);

  const totalBytes = useMemo(
    () => rows.reduce((acc, s) => acc + (s.size_bytes || 0), 0),
    [rows],
  );

  const selectableIds = useMemo(
    () => filtered.filter((s) => s.id !== currentSessionId).map((s) => s.id),
    [filtered, currentSessionId],
  );
  const selectedIds = useMemo(
    () => selectableIds.filter((id) => selected.has(id)),
    [selectableIds, selected],
  );
  const selectedBytes = useMemo(() => {
    const idSet = new Set(selectedIds);
    return rows
      .filter((s) => idSet.has(s.id))
      .reduce((acc, s) => acc + (s.size_bytes || 0), 0);
  }, [rows, selectedIds]);

  const selectedCount = selectedIds.length;
  const allVisibleSelected =
    selectableIds.length > 0 && selectedCount === selectableIds.length;
  const someVisibleSelected = selectedCount > 0 && !allVisibleSelected;

  const toggleOne = useCallback((id) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const handleRowClick = useCallback(
    (id, index, evt) => {
      if (id === currentSessionId) return;
      if (evt.shiftKey && lastIndexRef.current !== null) {
        const [from, to] = [lastIndexRef.current, index].sort((a, b) => a - b);
        const ids = filtered.slice(from, to + 1)
          .map((s) => s.id)
          .filter((sid) => sid !== currentSessionId);
        setSelected((prev) => {
          const next = new Set(prev);
          for (const sid of ids) next.add(sid);
          return next;
        });
      } else {
        toggleOne(id);
        lastIndexRef.current = index;
      }
    },
    [filtered, currentSessionId, toggleOne],
  );

  const toggleMaster = useCallback(() => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (allVisibleSelected) {
        for (const id of selectableIds) next.delete(id);
      } else {
        for (const id of selectableIds) next.add(id);
      }
      return next;
    });
  }, [allVisibleSelected, selectableIds]);

  useEffect(() => {
    if (!open) return undefined;
    function onKey(e) {
      const meta = e.metaKey || e.ctrlKey;
      if (meta && (e.key === "a" || e.key === "A")) {
        e.preventDefault();
        setSelected((prev) => {
          const next = new Set(prev);
          for (const id of selectableIds) next.add(id);
          return next;
        });
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, selectableIds]);

  const clearSelection = useCallback(() => {
    setSelected(new Set());
    lastIndexRef.current = null;
  }, []);

  const handleDelete = useCallback(async () => {
    if (selectedIds.length === 0) return;
    setDeleting(true);
    try {
      const result = await invoke("sessions_delete", { profile, ids: selectedIds });
      const deleted = (result?.deleted ?? []).length;
      const errors = result?.errors ?? [];
      if (deleted > 0) {
        removeSessionTitles(connectionId, profile, result.deleted);
        notify({
          message: `Deleted ${deleted} session${deleted === 1 ? "" : "s"}.`,
          duration: 2500,
        });
      }
      if (errors.length > 0) {
        const sample = errors.slice(0, 3).map((e) => `${e.id}: ${e.code}`).join(", ");
        notify({
          message: `${errors.length} skipped (${sample}${errors.length > 3 ? "…" : ""})`,
          variant: "error",
          duration: 4500,
        });
      }
      onDeleted?.(result?.deleted ?? []);
      clearSelection();
      await refresh();
    } catch (e) {
      notify({ message: `delete: ${String(e)}`, variant: "error", duration: 4000 });
    } finally {
      setDeleting(false);
    }
  }, [selectedIds, profile, connectionId, notify, onDeleted, clearSelection, refresh]);

  if (!open) return null;

  const headerActions = selectedCount === 0 ? null : (
    <>
      <Btn variant="ghost" onClick={clearSelection}>Cancel</Btn>
      <Btn
        variant="danger"
        onClick={() => setConfirmOpen(true)}
        disabled={deleting}
      >
        {deleting ? "Deleting…" : `Delete ${selectedCount}`}
      </Btn>
    </>
  );

  const sortLabel = (SORTS.find((s) => s.key === sortKey) || SORTS[0]).label;

  const body = (
    <div
      className={`anim-overlay ${styles.backdrop}`}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose?.();
      }}
    >
      <div className={`anim-dialog ${styles.modal}`} role="dialog" aria-modal="true" aria-label="Manage sessions">
        <header className={styles.header}>
          <div className={styles.headerLead}>
            <div className={styles.titleRow}>
              <h1 className={styles.title}>Sessions</h1>
              <span className={styles.meta}>
                @{profileLabel(profile)} · {rows.length} threads · {formatKB(totalBytes)}
              </span>
            </div>
            <p className={styles.subtitle}>
              Delete old or empty threads to free disk space. The active session is locked.
            </p>
          </div>
          <div className={styles.headerActions}>
            {headerActions}
            <Tip text="Close" side="down">
              <IconBtn aria-label="Close" onClick={onClose}><XIcon /></IconBtn>
            </Tip>
          </div>
        </header>

        <div className={styles.toolbar}>
          <div className={styles.filters}>
            {FILTERS.map((f) => (
              <Chip
                key={f.key}
                state={filterKey === f.key ? "on" : undefined}
                onClick={() => setFilterKey(f.key)}
              >
                <span>{f.label}</span>
                <span className={styles.chipCount}>{filterCounts[f.key]}</span>
              </Chip>
            ))}
          </div>
          <div className={styles.sort}>
            <span className={styles.sortLabel}>SORT</span>
            <Dropdown
              trigger={{ label: sortLabel }}
              direction="down"
              align="right"
              width={180}
            >
              {({ close }) => (
                <>
                  {SORTS.map((s) => (
                    <Dropdown.Row
                      key={s.key}
                      active={sortKey === s.key}
                      onClick={() => { setSortKey(s.key); close(); }}
                    >
                      {s.label}
                    </Dropdown.Row>
                  ))}
                </>
              )}
            </Dropdown>
          </div>
        </div>

        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr className={styles.headRow}>
                <th className={styles.cellCheck}>
                  <input
                    type="checkbox"
                    className={styles.checkbox}
                    aria-label="Select all visible"
                    disabled={selectableIds.length === 0}
                    checked={allVisibleSelected}
                    ref={(node) => { if (node) node.indeterminate = someVisibleSelected; }}
                    onChange={toggleMaster}
                  />
                </th>
                <th className={styles.cellSession}>SESSION</th>
                <th className={styles.cellActivity}>ACTIVITY</th>
                <th className={styles.cellTurns}>TURNS</th>
                <th className={styles.cellSize}>SIZE</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((s, index) => {
                const isCurrent = s.id === currentSessionId;
                const isSelected = selected.has(s.id);
                return (
                  <tr
                    key={s.id}
                    className={[
                      styles.row,
                      isCurrent ? styles.rowCurrent : "",
                      isSelected ? styles.rowSelected : "",
                    ].filter(Boolean).join(" ")}
                  >
                    <td className={styles.cellCheck}>
                      <input
                        type="checkbox"
                        className={styles.checkbox}
                        aria-label={isCurrent ? "Active session is locked" : `Select ${previewOf(s)}`}
                        disabled={isCurrent}
                        checked={isSelected}
                        onClick={(evt) => handleRowClick(s.id, index, evt)}
                        onChange={() => { /* handled via onClick to capture shift */ }}
                      />
                    </td>
                    <td className={styles.cellSession}>
                      <EditableSessionTitle
                        session={s}
                        profile={profile}
                        connectionId={connectionId}
                        max={PREVIEW_MAX}
                        className={styles.preview}
                        inputClassName={styles.previewInput}
                      />
                      {isCurrent && (
                        <div
                          className={styles.current}
                          style={accent ? { color: accent } : undefined}
                        >
                          <span>◆</span>
                          <span>current session</span>
                        </div>
                      )}
                    </td>
                    <td className={styles.cellActivity}>{relativeActivity(s.activityMs)}</td>
                    <td className={styles.cellTurns}>{s.turn_count ?? 0}</td>
                    <td className={styles.cellSize}>{formatKB(s.size_bytes)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <footer className={styles.footer}>
          <div className={styles.footerLeft}>
            {selectedCount === 0
              ? "Shift+click to select range · ⌘A to select all"
              : `Selected ${selectedCount} · ${formatKB(selectedBytes)} to free`}
          </div>
          <div className={styles.footerRight}>
            {filtered.length} of {rows.length}
          </div>
        </footer>
      </div>

      <ConfirmDelete
        mode="typed"
        anchored={false}
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        onConfirm={handleDelete}
        title={`Delete ${selectedCount} ${selectedCount === 1 ? "session" : "sessions"}`}
        consequence={
          <>
            This removes <strong>{formatKB(selectedBytes)}</strong> of message history from disk.{" "}
            <strong>This action cannot be undone.</strong>
          </>
        }
        typeToConfirm="DELETE"
        confirmLabel={`Delete ${selectedCount} ${selectedCount === 1 ? "session" : "sessions"}`}
      />
    </div>
  );

  return createPortal(body, document.body);
}
