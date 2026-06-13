import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  Btn,
  CopyIcon,
  Diamond,
  GearIcon,
  IconBtn,
  MarkdownBody,
  Mono,
  SearchIcon,
  Tip,
  XIcon,
} from "../primitives/index.js";
import { useNotify } from "../primitives/Notification.jsx";
import { relativeTime } from "../lib/time.js";
import { profileLabel } from "../lib/profile-display.js";
import {
  pendingDeleteKeys,
  rowKey,
  useAllOutputs,
  useDeleteOutput,
  useMarkAllOutputsRead,
  useOutput,
} from "../hooks/useOutputs.js";
import styles from "./NotificationsModal.module.css";
import { copyText } from "../lib/clipboard.js";


function fmtAbsolute(ts) {
  if (!ts) return "";
  const d = new Date(ts * 1000);
  return d.toLocaleString(undefined, {
    day: "numeric", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}


function typeTag(row) {
  const t = row?.type;
  if (!t || t === "info") return null;
  return t;
}


function contextAction(row) {
  if (!row) return null;
  if (row.session_id) {
    return { label: "Open chat", target: { kind: "chat", profile: row.profile, sessionId: row.session_id } };
  }
  return null;
}


function stripPreviewMarkdown(text) {
  return String(text || "")
    .replace(/!\[([^\]]*)\]\([^)]+\)/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/`{1,3}/g, "")
    .replace(/[*_~>#-]+/g, "")
    .replace(/\s+/g, " ")
    .trim();
}


function bodyPreview(row) {
  const line = row?.body?.split("\n").find((it) => stripPreviewMarkdown(it));
  return stripPreviewMarkdown(line) || "—";
}


export default function NotificationsModal({
  open,
  onClose,
  connections = [],
  selectedId,
  selectedProfile,
  selectedConnectionId,
  onSelect,
  onOpenChat,
}) {
  const notify = useNotify();
  const multi = connections.length > 1;
  const { rows, refresh } = useAllOutputs({ connections });
  const markAll = useMarkAllOutputsRead();
  const { schedule: scheduleDelete, cancel: cancelDelete } = useDeleteOutput();
  const [pendingId, setPendingId] = useState(null);
  const [pendingProfile, setPendingProfile] = useState(null);
  const [pendingConnectionId, setPendingConnectionId] = useState(null);
  const [query, setQuery] = useState("");
  const [hiddenIds, setHiddenIds] = useState(() => new Set());
  const wrapRef = useRef(null);

  const activeId = pendingId ?? selectedId ?? rows[0]?.id ?? null;
  const activeProfile = pendingProfile ?? selectedProfile ?? rows[0]?.profile ?? null;
  const activeConnId = pendingConnectionId ?? selectedConnectionId ?? rows[0]?.connectionId ?? null;
  const activeRow = useMemo(
    () =>
      rows.find(
        (r) => r.id === activeId && r.profile === activeProfile && r.connectionId === activeConnId,
      ) ?? null,
    [rows, activeId, activeProfile, activeConnId],
  );

  useEffect(() => {
    if (!open) {
      setPendingId(null);
      setPendingProfile(null);
      setPendingConnectionId(null);
      setQuery("");
      return;
    }
    // hiddenIds reseeds from in-flight pending deletes so a row in its undo window stays hidden across modal reopens.
    setHiddenIds(() => new Set(pendingDeleteKeys()));
  }, [open]);

  useEffect(() => {
    if (selectedId) {
      setPendingId(selectedId);
      setPendingProfile(selectedProfile);
      setPendingConnectionId(selectedConnectionId ?? null);
    }
  }, [selectedId, selectedProfile, selectedConnectionId]);

  const { row: detail, markRead } = useOutput(activeProfile, activeId, activeConnId);

  // Only EXPLICIT selection marks read — passive default to rows[0] must not silently consume the topmost unread on mere modal open.
  const explicitlySelected = pendingId !== null || selectedId !== undefined;
  useEffect(() => {
    if (!explicitlySelected) return;
    if (detail && detail.status === "unread") markRead();
  }, [detail, markRead, explicitlySelected]);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === "Escape") { e.preventDefault(); onClose?.(); } };
    const onClick = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) onClose?.();
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
  }, [open, onClose]);

  const unread = useMemo(() => rows.filter((r) => r.status === "unread").length, [rows]);

  const visibleRows = useMemo(
    () => rows.filter((r) => !hiddenIds.has(rowKey(r))),
    [rows, hiddenIds],
  );

  const filteredRows = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return visibleRows;
    return visibleRows.filter((row) => {
      const hay = [
        row.body,
        row.title,
        row.profile,
        row.type,
      ].filter(Boolean).join(" ").toLowerCase();
      return hay.includes(q);
    });
  }, [visibleRows, query]);

  const onSelectRow = useCallback((row) => {
    setPendingId(row.id);
    setPendingProfile(row.profile);
    setPendingConnectionId(row.connectionId ?? null);
    onSelect?.(row);
  }, [onSelect]);

  const onMarkAll = useCallback(async () => {
    const pairs = new Map();
    for (const r of rows) {
      const key = `${r.connectionId}:${r.profile}`;
      if (!pairs.has(key)) pairs.set(key, { connectionId: r.connectionId, profile: r.profile });
    }
    await Promise.all(
      Array.from(pairs.values()).map(({ connectionId, profile }) => markAll(profile, connectionId)),
    );
    refresh();
  }, [rows, markAll, refresh]);

  const onDeleteRow = useCallback((row) => {
    const key = rowKey(row);
    setHiddenIds((prev) => {
      const next = new Set(prev);
      next.add(key);
      return next;
    });
    if (row.id === activeId && row.profile === activeProfile && row.connectionId === activeConnId) {
      setPendingId(null);
      setPendingProfile(null);
      setPendingConnectionId(null);
    }
    scheduleDelete(row.profile, row.id, { connectionId: row.connectionId });
    notify({
      message: "Notification deleted",
      action: "Undo",
      onAction: () => {
        cancelDelete(row.profile, row.id, row.connectionId);
        setHiddenIds((prev) => {
          if (!prev.has(key)) return prev;
          const next = new Set(prev);
          next.delete(key);
          return next;
        });
      },
    });
  }, [scheduleDelete, cancelDelete, notify, activeId, activeProfile, activeConnId]);

  const onCopy = useCallback(async () => {
    if (!detail) return;
    if (await copyText(detail.body || "")) notify({ message: "Copied" });
    else notify({ message: "Copy failed", variant: "error" });
  }, [detail, notify]);

  const onAction = useCallback(() => {
    const action = contextAction(detail);
    if (!action) return;
    if (action.target.kind === "chat") {
      onOpenChat?.(action.target.profile, action.target.sessionId);
    }
    onClose?.();
  }, [detail, onClose, onOpenChat]);

  if (!open) return null;

  return createPortal(
    <div className={`anim-overlay ${styles.backdrop}`}>
      <div ref={wrapRef} className={`anim-dialog ${styles.modal}`} role="dialog" aria-modal="true">
        <header className={styles.header}>
          <span className={styles.headerLead}>
            <span className={styles.title}>Notifications</span>
          </span>
          {unread > 0 ? (
            <span className={styles.headerMeta}>
              <Mono className={styles.metaPiece}>· {unread} UNREAD</Mono>
            </span>
          ) : null}
          <span className={styles.headerSpacer} />
          {unread > 0 ? (
            <Btn variant="ghost" onClick={onMarkAll}>Mark all read</Btn>
          ) : null}
          <Tip text="Close" side="down">
            <IconBtn aria-label="Close" onClick={() => onClose?.()}>
              <XIcon />
            </IconBtn>
          </Tip>
        </header>

        <div className={styles.body}>
          <div className={styles.sidebar}>
            <div className={styles.searchWrap}>
              <SearchIcon className={styles.searchIcon} />
              <input
                type="text"
                className={styles.searchInput}
                placeholder="Search notifications…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                aria-label="Search notifications"
              />
            </div>
            <ul className={styles.list} role="listbox">
              {rows.length === 0 ? (
                <li className={styles.empty}>
                  <span className={styles.emptyTitle}>Inbox zero</span>
                  <span className={styles.emptyHint}>
                    Notifications land here when an agent notifies you or a scheduled job fails.
                  </span>
                </li>
              ) : filteredRows.length === 0 ? (
                <li className={styles.empty}>
                  <span className={styles.emptyTitle}>No matches</span>
                  <span className={styles.emptyHint}>
                    Try a different query, or clear it to see everything.
                  </span>
                </li>
              ) : (
                filteredRows.map((row) => (
                  <NotificationRow
                    key={`${row.connectionId}:${row.profile}:${row.id}`}
                    row={row}
                    accent={row.accent}
                    multi={multi}
                    active={row.id === activeId && row.profile === activeProfile && row.connectionId === activeConnId}
                    onSelect={onSelectRow}
                    onDelete={onDeleteRow}
                  />
                ))
              )}
            </ul>
          </div>

          <div className={styles.detail}>
            {detail ? (
              <DetailPane
                row={detail}
                accent={activeRow?.accent}
                multi={multi}
                onCopy={onCopy}
                onAction={onAction}
                action={contextAction(detail)}
              />
            ) : (
              <div className={styles.detailEmpty}>Select a notification.</div>
            )}
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}


function NotificationRow({ row, accent, multi, active, onSelect, onDelete }) {
  const unread = row.status === "unread";
  const label = profileLabel(row.profile);
  const handleDelete = (e) => {
    e.stopPropagation();
    onDelete?.(row);
  };
  return (
    <li
      role="option"
      aria-selected={active}
      className={`${styles.row} ${active ? styles.rowActive : ""} ${unread ? styles.rowUnread : ""}`}
      onClick={() => onSelect?.(row)}
    >
      <div className={styles.rowBody}>
        <div className={styles.rowMeta}>
          <span className={styles.rowMetaLead}>
            <Diamond color={accent} />
            <Mono>@{label}</Mono>
            {multi && row.connectionName ? <Mono>· {row.connectionName}</Mono> : null}
          </span>
          <span className={styles.rowSlot}>
            <Mono className={styles.rowTs}>{relativeTime(row.created_at)}</Mono>
            <span className={styles.rowDelete}>
              <Tip text="Delete" side="up">
                <IconBtn aria-label="Delete notification" onClick={handleDelete}>
                  <XIcon />
                </IconBtn>
              </Tip>
            </span>
          </span>
        </div>
        <div className={styles.rowTitle}>{bodyPreview(row)}</div>
      </div>
    </li>
  );
}


function DetailPane({ row, accent, multi, onCopy, onAction, action }) {
  const label = profileLabel(row.profile);
  const tag = typeTag(row);
  const externalDelivery = (row.delivered_to || []).filter((c) => c !== "alpi");

  return (
    <article className={styles.article}>
      <div className={styles.detailMeta}>
        {tag ? (
          <span className={tag === "error" ? styles.detailMetaError : styles.detailMetaWarning}>
            <Mono>{tag.toUpperCase()}</Mono>
            <span className={styles.detailMetaDot}>·</span>
          </span>
        ) : null}
        <span className={styles.detailMetaProfile}>
          <Diamond color={accent} />
          <Mono>@{label.toUpperCase()}</Mono>
        </span>
        {multi && row.connectionName ? (
          <>
            <span className={styles.detailMetaDot}>·</span>
            <Mono className={styles.detailMetaPart}>{row.connectionName.toUpperCase()}</Mono>
          </>
        ) : null}
        <span className={styles.detailMetaDot}>·</span>
        <Mono className={styles.detailMetaPart}>{fmtAbsolute(row.created_at)}</Mono>
        <span className={styles.detailMetaSpacer} />
        <Tip text="Copy" side="l">
          <IconBtn aria-label="Copy notification" onClick={onCopy}>
            <CopyIcon />
          </IconBtn>
        </Tip>
      </div>

      <div className={styles.detailBody}>
        <MarkdownBody source={row.body || ""} />
      </div>

      {externalDelivery.length ? (
        <div className={styles.detailMetaSecondary}>
          <Mono>delivered: {externalDelivery.join(", ")}</Mono>
        </div>
      ) : null}

      {action ? (
        <div className={styles.actions}>
          <Btn variant="ghost" onClick={onAction}>
            <GearIcon />
            <span>{action.label}</span>
          </Btn>
        </div>
      ) : null}
    </article>
  );
}
