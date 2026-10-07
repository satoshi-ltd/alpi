import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import {
  BrowseModal,
  Button,
  Chip,
  CopyIcon,
  Fold,
  DownloadIcon,
  Icon,
  IconBtn,
  Kbd,
  Mono,
  Popover,
  SpinnerIcon as DSSpinnerIcon,
  Tip,
  VolumeIcon,
  XIcon,
} from "../primitives/index.js";
import NotificationBody, { ErrorCard } from "./NotificationBody.jsx";
import WaveBars from "../primitives/WaveBars.jsx";
import { SkeletonRows } from "../primitives/Skeleton.jsx";
import Eyebrow from "../primitives/Eyebrow.jsx";
import { playTts, subscribeTts, VOICE_POOL } from "../lib/tts.js";
import { useOnline } from "../lib/useOnline.js";
import { useNotify } from "../primitives/Notification.jsx";
import { notificationTime } from "../lib/time.js";
import { profileLabel } from "../lib/profile-display.js";
import {
  pendingDeleteKeys,
  rowKey,
  useAllOutputs,
  useDeleteOutput,
  useMarkAllOutputsRead,
  useOutput,
} from "../hooks/useOutputs.js";
import { useProfileDetail } from "../hooks/useProfileDetail.js";
import { isMissingVerb } from "../hooks/useActivity.js";
import styles from "./NotificationsModal.module.css";
import { copyText } from "../lib/clipboard.js";
import { headlineParts } from "../lib/notificationHeadline.js";
import { EMPTY } from "../../../common/emptyCopy.mjs";
import {
  NOTIFICATION_FILTERS,
  filterNotifications,
  groupNotifications,
  isNeedsYou,
  triageCounts,
} from "../../../common/notificationTriage.mjs";


function fmtAbsolute(ts) {
  if (!ts) return "";
  const d = new Date(ts * 1000);
  return d.toLocaleString(undefined, {
    day: "numeric", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}


function slugify(s) {
  const out = String(s || "")
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
  return out || "notification";
}


function typeTag(row) {
  const t = row?.type;
  if (!t || t === "info") return null;
  return t;
}


export const READ_DWELL_MS = 600;

const FILTERS = NOTIFICATION_FILTERS.map((f, i) => ({ ...f, key: String(i + 1) }));

const KEYS = [["↑↓", "move"], ["⏎", "open"], ["R", "reply"], ["U", "unread"], ["⌫", "delete"], ["/", "search"], ["1–3", "filter"]];

const clip = (text, max) => (text.length > max ? `${text.slice(0, max - 1).trimEnd()}…` : text);

export function unreachableTitle(names) {
  const shown = names.slice(0, 3).join(", ");
  const rest = names.length > 3 ? ` and ${names.length - 3} more` : "";
  return `Couldn't reach ${shown}${rest}`;
}

export default function NotificationsModal({
  open,
  onClose,
  connections = [],
  activeConnectionId = null,
  selectedId,
  selectedProfile,
  selectedConnectionId,
  onSelect,
  onOpenChat,
  onOpenJob,
  onSendToChat: onReplyProp,
}) {
  const notify = useNotify();
  const multi = connections.length > 1;
  // deferMs 0: opening the inbox is explicit user intent — every connection starts syncing immediately (bounded concurrency, no boot stagger).
  const { rows, refresh, loading, unreachable = [] } = useAllOutputs({
    connections, activeId: activeConnectionId, enabled: open, deferMs: 0,
  });
  const markAll = useMarkAllOutputsRead();
  const { schedule: scheduleDelete, cancel: cancelDelete } = useDeleteOutput();
  const [pendingId, setPendingId] = useState(null);
  const [pendingProfile, setPendingProfile] = useState(null);
  const [pendingConnectionId, setPendingConnectionId] = useState(null);
  const [query, setQuery] = useState("");
  const [hiddenIds, setHiddenIds] = useState(() => new Set());
  const [readIds, setReadIds] = useState(() => new Set());
  const [unreadIds, setUnreadIds] = useState(() => new Set());
  const [heldUnread, setHeldUnread] = useState(null);
  const [filter, setFilter] = useState("all");
  const [unreadMissing, setUnreadMissing] = useState(() => new Set());
  const [frozen, setFrozen] = useState(null);
  const listRef = useRef(null);

  const isUnread = useCallback((r) => {
    const key = rowKey(r);
    return unreadIds.has(key) || (r.status === "unread" && !readIds.has(key));
  }, [unreadIds, readIds]);
  const needsYou = useCallback((r) => isNeedsYou(r, isUnread(r)), [isUnread]);

  const visibleRows = useMemo(
    () => rows.filter((r) => !hiddenIds.has(rowKey(r))),
    [rows, hiddenIds],
  );
  const unreadCount = useMemo(() => visibleRows.filter(isUnread).length, [visibleRows, isUnread]);

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

  const counts = useMemo(() => triageCounts(filteredRows, isUnread), [filteredRows, isUnread]);
  const shownRows = useMemo(
    () => filterNotifications(filteredRows, filter, { isUnread, frozen }),
    [filteredRows, filter, isUnread, frozen],
  );

  const grouped = useMemo(
    () => groupNotifications(shownRows, { filter, isUnread, frozen }),
    [shownRows, filter, isUnread, frozen],
  );
  const orderedRows = useMemo(() => grouped.flatMap((g) => g.rows), [grouped]);

  const chosen = pendingId !== null
    ? { id: pendingId, profile: pendingProfile, connectionId: pendingConnectionId }
    : selectedId ? { id: selectedId, profile: selectedProfile, connectionId: selectedConnectionId ?? null } : null;
  const picked = chosen && !hiddenIds.has(rowKey(chosen)) ? chosen : null;
  const fallback = orderedRows[0] ?? null;
  const activeId = picked?.id ?? fallback?.id ?? null;
  const activeProfile = picked?.profile ?? fallback?.profile ?? null;
  const activeConnId = picked?.connectionId ?? fallback?.connectionId ?? null;
  const activeRow = useMemo(
    () =>
      rows.find(
        (r) => r.id === activeId && r.profile === activeProfile && r.connectionId === activeConnId,
      ) ?? null,
    [rows, activeId, activeProfile, activeConnId],
  );

  const voiceByProfile = useMemo(() => {
    const map = new Map();
    for (const r of rows) {
      const key = `${r.connectionId}:${r.profile}`;
      if (r.voice_id != null && !map.has(key)) map.set(key, r.voice_id);
    }
    return map;
  }, [rows]);
  const { detail: profileDetail } = useProfileDetail(activeConnId, activeProfile);
  const activeVoiceId = profileDetail?.voice_id
    ?? voiceByProfile.get(`${activeConnId}:${activeProfile}`)
    ?? activeRow?.voice_id
    ?? null;

  useEffect(() => {
    if (!open) {
      setPendingId(null);
      setPendingProfile(null);
      setPendingConnectionId(null);
      setQuery("");
      setReadIds(new Set());
      setUnreadIds(new Set());
      setHeldUnread(null);
      setFilter("all");
      setFrozen(null);
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

  const { row: fetchedDetail, markRead, markUnread } = useOutput(activeProfile, activeId, activeConnId);
  const detail = activeRow ?? (activeId ? fetchedDetail : null);
  const activeKey = rowKey({ connectionId: activeConnId, profile: activeProfile, id: activeId });
  const detailUnread = detail ? isUnread({ ...detail, connectionId: activeConnId, profile: activeProfile, id: activeId }) : false;
  const canMarkUnread = !unreadMissing.has(activeConnId ?? "local");

  // Only EXPLICIT selection marks read — passive default to the first row must not silently consume it on mere modal open.
  const explicitlySelected = picked !== null;

  useEffect(() => {
    if (!explicitlySelected || !activeRow) return;
    setFrozen((cur) => (cur?.key === activeKey ? cur : { key: activeKey, pinned: needsYou(activeRow), unread: isUnread(activeRow) }));
  }, [explicitlySelected, activeRow, activeKey, needsYou, isUnread]);

  const commitRead = useCallback((acted = false) => {
    if (!(explicitlySelected || acted) || !detailUnread || heldUnread === activeKey) return;
    setReadIds((prev) => (prev.has(activeKey) ? prev : new Set(prev).add(activeKey)));
    setUnreadIds((prev) => {
      if (!prev.has(activeKey)) return prev;
      const next = new Set(prev);
      next.delete(activeKey);
      return next;
    });
    markRead();
  }, [explicitlySelected, detailUnread, heldUnread, activeKey, markRead]);

  useEffect(() => {
    if (!explicitlySelected || !detailUnread || heldUnread === activeKey) return undefined;
    const timer = setTimeout(() => commitRead(), READ_DWELL_MS);
    return () => clearTimeout(timer);
  }, [commitRead, explicitlySelected, detailUnread, heldUnread, activeKey]);

  const onSelectRow = useCallback((row) => {
    if (rowKey(row) !== heldUnread) setHeldUnread(null);
    setPendingId(row.id);
    setPendingProfile(row.profile);
    setPendingConnectionId(row.connectionId ?? null);
    onSelect?.(row);
  }, [onSelect, heldUnread]);

  const onMarkAll = useCallback(async () => {
    setUnreadIds(new Set());
    setHeldUnread(null);
    setReadIds((prev) => {
      const next = new Set(prev);
      for (const r of rows) next.add(rowKey(r));
      return next;
    });
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
      message: `Deleted “${clip(headlineParts(row).title || "notification", 48)}”`,
      action: "Undo",
      onAction: () => {
        // The toast outlives the 5 s delete while hovered; a row the daemon already dropped must not come back.
        if (!cancelDelete(row.profile, row.id, row.connectionId)) {
          notify({ message: "Already deleted" });
          return;
        }
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

  const buildMarkdown = useCallback(() => {
    const title = (detail?.title || "").trim() || "Notification";
    const conn = activeConnId === "local" ? "local" : (activeRow?.connectionName || activeConnId || "");
    const meta = [`@${profileLabel(detail.profile)}`, conn, fmtAbsolute(detail.created_at)]
      .filter(Boolean)
      .join(" · ");
    return `# ${title}\n_${meta}_\n\n${detail.body || ""}\n`;
  }, [detail, activeConnId, activeRow]);

  const onReply = useCallback(async () => {
    if (!detail) return;
    commitRead(true);
    const name = `${slugify(detail.title)}.md`;
    try {
      const meta = await invoke("save_text_file", { name, content: buildMarkdown(), dest: "temp" });
      onReplyProp?.(detail.profile, activeConnId, { path: meta.path, name, size: meta.size, mime: "text/markdown" });
      onClose?.();
    } catch (e) {
      notify({ message: `Reply failed: ${e}`, variant: "error" });
    }
  }, [detail, activeConnId, buildMarkdown, onReplyProp, notify, onClose, commitRead]);

  const onDownload = useCallback(async () => {
    if (!detail) return;
    const name = `${slugify(detail.title)}.md`;
    try {
      const meta = await invoke("save_text_file", { name, content: buildMarkdown(), dest: "download" });
      notify({ message: `Downloaded ${meta.name}` });
    } catch (e) {
      notify({ message: `Download failed: ${e}`, variant: "error" });
    }
  }, [detail, buildMarkdown, notify]);

  const onOpenChatRow = useCallback(() => {
    if (!detail?.session_id) return;
    commitRead(true);
    onOpenChat?.(detail.profile, detail.session_id, activeConnId);
    onClose?.();
  }, [detail, onClose, onOpenChat, activeConnId, commitRead]);

  const onMarkUnread = useCallback(async () => {
    if (!detail) return;
    if (detailUnread) {
      setHeldUnread(activeKey);
      return;
    }
    if (!canMarkUnread) return;
    const connKey = activeConnId ?? "local";
    try {
      await markUnread();
      setReadIds((prev) => {
        if (!prev.has(activeKey)) return prev;
        const next = new Set(prev);
        next.delete(activeKey);
        return next;
      });
      setUnreadIds((prev) => new Set(prev).add(activeKey));
      setHeldUnread(activeKey);
    } catch (e) {
      if (isMissingVerb(e)) setUnreadMissing((prev) => new Set(prev).add(connKey));
      else notify({ message: `Mark unread failed: ${e}`, variant: "error" });
    }
  }, [detail, canMarkUnread, detailUnread, markUnread, activeKey, activeConnId, notify]);

  const jobOf = (row) => (row?.job_id ? String(row.job_id) : null);

  const [runningJob, setRunningJob] = useState(null);
  const runningRef = useRef(false);
  const onRunAgain = useCallback(async () => {
    const jobId = jobOf(detail);
    if (!jobId || runningRef.current) return;
    runningRef.current = true;
    setRunningJob(jobId);
    try {
      await invoke("schedule_fire", { profile: detail.profile, ...(activeConnId ? { connectionId: activeConnId } : {}), id: jobId });
      notify({ message: "Running again", variant: "success", duration: 2000 });
    } catch (e) {
      notify({ message: `Run failed: ${e}`, variant: "error", duration: 4000 });
    } finally {
      runningRef.current = false;
      setRunningJob(null);
    }
  }, [detail, activeConnId, notify]);

  const canOpenJob = Boolean(onOpenJob && jobOf(detail) && (!activeConnectionId || activeConnId === activeConnectionId));
  const onOpenJobRow = useCallback(() => {
    const jobId = jobOf(detail);
    if (!jobId) return;
    commitRead(true);
    onOpenJob?.(detail.profile, jobId);
    onClose?.();
  }, [detail, onOpenJob, onClose, commitRead]);

  const focusRow = useCallback((row) => {
    requestAnimationFrame(() => {
      listRef.current?.querySelector(`[data-key="${CSS.escape(rowKey(row))}"]`)?.focus();
    });
  }, []);

  const onListKey = useCallback((e) => {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.repeat) {
      if (e.key.length === 1 || e.key === "Backspace" || e.key === "Delete") e.preventDefault();
      return;
    }
    if (e.target !== e.currentTarget && e.target.getAttribute?.("role") !== "option") return;
    const filterKey = FILTERS.find((f) => f.key === e.key);
    if (filterKey) setFilter(filterKey.id);
    else if (e.key === "/") e.currentTarget.closest('[role="dialog"]')?.querySelector('input[type="text"]')?.focus();
    else if (e.key === "r" || e.key === "R") onReply();
    else if (e.key === "u" || e.key === "U") onMarkUnread();
    else if ((e.key === "Backspace" || e.key === "Delete") && activeRow) {
      const at = orderedRows.findIndex((r) => rowKey(r) === rowKey(activeRow));
      const next = orderedRows[at + 1] ?? orderedRows[at - 1] ?? null;
      onDeleteRow(activeRow);
      if (next) {
        onSelectRow(next);
        focusRow(next);
      }
    } else return;
    e.preventDefault();
  }, [onReply, onMarkUnread, activeRow, orderedRows, onDeleteRow, onSelectRow, focusRow]);

  const filters = visibleRows.length > 0 ? (
    <div className={styles.filters}>
      <div className={styles.filterRow} role="group" aria-label="Show">
        {FILTERS.map((f) => (
          <Button
            key={f.id}
            size="sm"
            variant={filter === f.id ? "primary" : "ghost"}
            aria-pressed={filter === f.id}
            onClick={() => setFilter(f.id)}
          >
            {f.label}
            <span className={styles.filterCount}>{counts[f.id]}</span>
          </Button>
        ))}
      </div>
    </div>
  ) : null;

  const keys = visibleRows.length > 0 ? (
    <div className={styles.keys} aria-hidden="true">
      {KEYS.map(([k, what]) => <span key={k} className={styles.keyItem}><Kbd>{k}</Kbd>{what}</span>)}
    </div>
  ) : null;

  const list = (
    <>
    {filters}
    <ul ref={listRef} className={styles.list} role="listbox" aria-label="Notifications" onKeyDown={onListKey}>
      {rows.length > 0 && unreachable.length > 0 && (
        <li className={styles.partial} role="presentation">
          {unreachableTitle(unreachable)}. Their notifications are missing from this list.
        </li>
      )}
      {rows.length === 0 && loading ? (
        <SkeletonRows as="li" />
      ) : rows.length === 0 && unreachable.length > 0 ? (
        <li className={styles.empty}>
          <span className={styles.emptyTitle}>{unreachableTitle(unreachable)}</span>
          <span className={styles.emptyHint}>
            Their notifications show up here once the daemon answers again.
          </span>
        </li>
      ) : visibleRows.length === 0 ? (
        <li className={styles.empty}>
          <span className={styles.emptyTitle}>{EMPTY.notifications.title}</span>
          <span className={styles.emptyHint}>{EMPTY.notifications.hint}</span>
        </li>
      ) : shownRows.length === 0 ? (
        <li className={styles.empty}>
          <span className={styles.emptyTitle}>{EMPTY.matches.title}</span>
          <span className={styles.emptyHint}>{EMPTY.matches.hint}</span>
        </li>
      ) : (
        grouped.flatMap((group) => [
          <Eyebrow key={`h:${group.id}`} as="li" className={styles.groupHeader} role="presentation">{group.label}</Eyebrow>,
          ...group.rows.map((row) => (
            <NotificationRow
              key={rowKey(row)}
              row={row}
              accent={row.accent}
              fold={row.fold}
              multi={multi}
              unread={isUnread(row)}
              active={row.id === activeId && row.profile === activeProfile && row.connectionId === activeConnId}
              onSelect={onSelectRow}
              onDelete={onDeleteRow}
            />
          )),
        ])
      )}
    </ul>
    {keys}
    </>
  );

  return (
    <BrowseModal
      open={open}
      onClose={onClose}
      title="Notifications"
      loading={loading}
      loadingLabel="Syncing notifications"
      kicker={unreadCount > 0 ? `${unreadCount} unread` : null}
      actions={unreadCount > 0 ? <Button variant="ghost" onClick={onMarkAll}>Mark all read</Button> : null}
      search={{ value: query, onChange: setQuery, placeholder: "Search notifications…", label: "Search notifications" }}
      list={list}
    >
      {detail ? (
        <DetailPane
          row={detail}
          accent={activeRow?.accent}
          fold={activeRow?.fold}
          connId={activeConnId}
          connectionName={activeRow?.connectionName}
          voiceId={activeVoiceId}
          onCopy={onCopy}
          onReply={onReply}
          onDownload={onDownload}
          onOpenChat={detail.session_id ? onOpenChatRow : null}
          onMarkUnread={canMarkUnread && !detailUnread ? onMarkUnread : null}
          onRunAgain={jobOf(detail) ? onRunAgain : null}
          running={runningJob !== null && runningJob === jobOf(detail)}
          onOpenJob={canOpenJob ? onOpenJobRow : null}
        />
      ) : (
        <div className={styles.detailEmpty}>Select a notification.</div>
      )}
    </BrowseModal>
  );
}


function NotificationRow({ row, accent, fold, multi, unread, active, onSelect, onDelete }) {
  const label = profileLabel(row.profile);
  const { title, preview } = headlineParts(row);
  const sev = typeTag(row);
  const handleDelete = (e) => {
    e.stopPropagation();
    onDelete?.(row);
  };
  return (
    <li
      role="option"
      aria-selected={active}
      tabIndex={0}
      data-key={rowKey(row)}
      className={`${styles.row} ${active ? styles.rowActive : ""} ${unread ? styles.rowUnread : ""}`}
      onClick={() => onSelect?.(row)}
      onFocus={(e) => { if (e.target === e.currentTarget) onSelect?.(row); }}
      onKeyDown={(e) => {
        if (e.target !== e.currentTarget || (e.key !== "Enter" && e.key !== " ")) return;
        e.preventDefault();
        onSelect?.(row);
      }}
    >
      <span className={styles.rowGutter}>
        {unread ? <span className={styles.unreadDot} role="img" aria-label="Unread" /> : null}
      </span>
      <span className={styles.rowFold}><Fold fold={fold} color={accent} /></span>
      <div className={styles.rowBody}>
        <div className={styles.rowMeta}>
          <span className={styles.rowMetaLead}>
            <Mono className={styles.rowProfile}>@{label}</Mono>
            {multi && row.connectionName ? <Mono className={styles.rowConn}>· {row.connectionName}</Mono> : null}
          </span>
          <span className={styles.rowSlot}>
            {sev ? <span className={`${styles.rowSev} ${sev === "error" ? styles.rowSevError : styles.rowSevWarning}`}>{sev}</span> : null}
            <Mono className={styles.rowTs}>{notificationTime(row.created_at)}</Mono>
            <span className={styles.rowDelete}>
              <Tip text="Delete" side="up">
                <IconBtn aria-label="Delete notification" onClick={handleDelete}>
                  <XIcon />
                </IconBtn>
              </Tip>
            </span>
          </span>
        </div>
        <div className={styles.rowTitle}>{title}</div>
        {preview ? <div className={styles.rowPreview}>{preview}</div> : null}
      </div>
    </li>
  );
}


function DetailPane({ row, accent, fold, connId, connectionName, voiceId, onCopy, onReply, onDownload, onOpenChat, onMarkUnread, onRunAgain, onOpenJob, running = false }) {
  const label = profileLabel(row.profile);
  const failure = row.type === "error";
  const tag = failure ? null : typeTag(row);
  const isHost = connId === "local";
  const externalDelivery = (row.delivered_to || []).filter((c) => c !== "alpi");
  const [menuOpen, setMenuOpen] = useState(false);

  const [ttsState, setTtsState] = useState(null);
  useEffect(() => subscribeTts(setTtsState), []);
  const online = useOnline();
  const ttsKey = `notif:${connId}:${row.profile}:${row.id}`;
  const ttsKind = ttsState?.key === ttsKey ? ttsState.kind : null;
  const isLoading = ttsKind === "loading";
  const isPlaying = ttsKind === "playing";
  const ttsDisabled = (!online && !isPlaying) || !row.body;
  const speakLabel = !online && !isPlaying
    ? "Offline — TTS unavailable"
    : isPlaying ? "Stop reading" : "Read aloud";
  const speakName = isLoading ? "Read aloud, preparing audio" : speakLabel;
  const onSpeak = () => {
    if (!row.body) return;
    playTts({ key: ttsKey, profile: row.profile, voice: voiceId ?? row.voice_id ?? VOICE_POOL[0], text: row.body, accent });
  };
  const run = (fn) => () => {
    setMenuOpen(false);
    fn?.();
  };

  return (
    <article className={styles.article}>
      <div className={styles.detailMeta}>
        <span className={styles.detailMetaProfile}>
          {!isHost && connectionName ? <span className={styles.detailMetaConn}>{connectionName}/</span> : null}
          <Fold fold={fold} color={accent} />
          <span className={styles.detailMetaName}>@{label}</span>
          <span className={styles.detailMetaDot}>·</span>
          <span className={styles.detailMetaDate}>{fmtAbsolute(row.created_at)}</span>
        </span>
        {tag ? <Chip state={tag === "error" ? "error" : "warn"} size="sm">{tag}</Chip> : null}
        <span className={styles.detailMetaSpacer} />
        {isLoading || isPlaying ? (
          <Tip text={speakLabel} side="l" escape>
            <IconBtn aria-label={speakName} onClick={onSpeak}>
              {isLoading ? <DSSpinnerIcon /> : <WaveBars accent={accent} active />}
            </IconBtn>
          </Tip>
        ) : null}
        <span className={styles.overflow}>
          <IconBtn tip="More" tipSide="l" aria-label="More" aria-expanded={menuOpen} onClick={() => setMenuOpen((o) => !o)}>
            <Icon name="ellipsis" />
          </IconBtn>
          <Popover open={menuOpen} onClose={() => setMenuOpen(false)} align="right" navigable role="menu">
            <div className={styles.menu}>
              <Button role="menuitem" fullWidth className={styles.menuItem} disabled={ttsDisabled} onClick={run(onSpeak)} aria-label={isLoading ? speakName : undefined}>
                {isLoading ? <DSSpinnerIcon className={styles.menuIcon} /> : <VolumeIcon className={styles.menuIcon} />}
                <span className={styles.menuLabel}>{speakLabel}</span>
              </Button>
              <Button role="menuitem" fullWidth className={styles.menuItem} onClick={run(onCopy)}>
                <CopyIcon className={styles.menuIcon} />
                <span className={styles.menuLabel}>Copy</span>
              </Button>
              <Button role="menuitem" fullWidth className={styles.menuItem} onClick={run(onDownload)}>
                <DownloadIcon className={styles.menuIcon} />
                <span className={styles.menuLabel}>Download .md</span>
              </Button>
            </div>
          </Popover>
        </span>
      </div>

      <div className={styles.actions}>
        <Button variant={failure ? "secondary" : "primary"} onClick={onReply}>Reply</Button>
        {onOpenChat ? <Button variant="secondary" onClick={onOpenChat}>Open chat</Button> : null}
        {onOpenJob && !failure ? <Button variant="secondary" onClick={onOpenJob}>Open job</Button> : null}
        {onMarkUnread ? <Button variant="ghost" onClick={onMarkUnread}>Mark unread</Button> : null}
      </div>

      {failure ? (
        <ErrorCard
          title={(row.title || "").trim()}
          body={row.body || ""}
          actions={onRunAgain || onOpenJob ? (
            <>
              {onRunAgain ? <Button variant="primary" onClick={onRunAgain} disabled={running}>Run again</Button> : null}
              {onOpenJob ? <Button variant="secondary" onClick={onOpenJob}>Open job</Button> : null}
            </>
          ) : null}
        />
      ) : (
        <>
          {(row.title || "").trim() ? (
            <h2 className={styles.detailTitle}>{row.title}</h2>
          ) : null}
          <NotificationBody body={row.body || ""} lead={!(row.title || "").trim()} />
        </>
      )}

      {externalDelivery.length ? (
        <div className={styles.detailMetaSecondary}>
          <Mono>delivered: {externalDelivery.join(", ")}</Mono>
        </div>
      ) : null}
    </article>
  );
}
