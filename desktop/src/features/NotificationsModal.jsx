import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import {
  BrowseModal,
  Btn,
  Chip,
  CopyIcon,
  Diamond,
  DownloadIcon,
  GearIcon,
  IconBtn,
  Mono,
  SendToChatIcon,
  SpinnerIcon as DSSpinnerIcon,
  Tip,
  VolumeIcon,
  XIcon,
} from "../primitives/index.js";
import NotificationBody from "./NotificationBody.jsx";
import WaveBars from "../primitives/WaveBars.jsx";
import Eyebrow from "../primitives/Eyebrow.jsx";
import { playTts, subscribeTts, VOICE_POOL } from "../lib/tts.js";
import { useOnline } from "../lib/useOnline.js";
import { useNotify } from "../primitives/Notification.jsx";
import { groupByDate, notificationTime } from "../lib/time.js";
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
import styles from "./NotificationsModal.module.css";
import { copyText } from "../lib/clipboard.js";
import { headlineParts } from "../lib/notificationHeadline.js";


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


function contextAction(row) {
  if (!row) return null;
  if (row.session_id) {
    return { label: "Open chat", target: { kind: "chat", profile: row.profile, sessionId: row.session_id } };
  }
  return null;
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
  onSendToChat: onSendToChatProp,
}) {
  const notify = useNotify();
  const multi = connections.length > 1;
  // deferMs 0: opening the inbox is explicit user intent — every connection starts syncing immediately (bounded concurrency, no boot stagger).
  const { rows, refresh, loading } = useAllOutputs({
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

  const { row: fetchedDetail, markRead } = useOutput(activeProfile, activeId, activeConnId);
  const detail = activeRow ?? fetchedDetail;

  // Only EXPLICIT selection marks read — passive default to rows[0] must not silently consume the topmost unread on mere modal open.
  const explicitlySelected = pendingId !== null || selectedId !== undefined;
  useEffect(() => {
    if (!explicitlySelected) return;
    if (detail && detail.status === "unread") {
      const key = rowKey({ connectionId: activeConnId, profile: activeProfile, id: activeId });
      setReadIds((prev) => (prev.has(key) ? prev : new Set(prev).add(key)));
      markRead();
    }
  }, [detail, markRead, explicitlySelected, activeConnId, activeProfile, activeId]);

  const unreadCount = useMemo(
    () => rows.filter(
      (r) => r.status === "unread" && !readIds.has(rowKey(r)) && !hiddenIds.has(rowKey(r)),
    ).length,
    [rows, readIds, hiddenIds],
  );

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

  const grouped = useMemo(
    () => groupByDate(filteredRows, (r) => r.created_at),
    [filteredRows],
  );

  const onSelectRow = useCallback((row) => {
    const key = rowKey(row);
    setReadIds((prev) => (prev.has(key) ? prev : new Set(prev).add(key)));
    setPendingId(row.id);
    setPendingProfile(row.profile);
    setPendingConnectionId(row.connectionId ?? null);
    onSelect?.(row);
  }, [onSelect]);

  const onMarkAll = useCallback(async () => {
    setReadIds((prev) => {
      const next = new Set(prev);
      for (const r of rows) if (r.status === "unread") next.add(rowKey(r));
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

  const buildMarkdown = useCallback(() => {
    const title = (detail?.title || "").trim() || "Notification";
    const conn = activeConnId === "local" ? "local" : (activeRow?.connectionName || activeConnId || "");
    const meta = [`@${profileLabel(detail.profile)}`, conn, fmtAbsolute(detail.created_at)]
      .filter(Boolean)
      .join(" · ");
    return `# ${title}\n_${meta}_\n\n${detail.body || ""}\n`;
  }, [detail, activeConnId, activeRow]);

  const onSendToChat = useCallback(async () => {
    if (!detail) return;
    const name = `${slugify(detail.title)}.md`;
    try {
      const meta = await invoke("save_text_file", { name, content: buildMarkdown(), dest: "temp" });
      onSendToChatProp?.(detail.profile, activeConnId, { path: meta.path, name, size: meta.size, mime: "text/markdown" });
      notify({ message: `Attached to @${profileLabel(detail.profile)}` });
      onClose?.();
    } catch (e) {
      notify({ message: `Send to chat failed: ${e}`, variant: "error" });
    }
  }, [detail, activeConnId, buildMarkdown, onSendToChatProp, notify, onClose]);

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

  const onAction = useCallback(() => {
    const action = contextAction(detail);
    if (!action) return;
    if (action.target.kind === "chat") {
      onOpenChat?.(action.target.profile, action.target.sessionId);
    }
    onClose?.();
  }, [detail, onClose, onOpenChat]);

  const list = (
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
        grouped.map((group) => (
          <Fragment key={group.label}>
            <Eyebrow as="li" className={styles.groupHeader} role="presentation">{group.label}</Eyebrow>
            {group.rows.map((row) => (
              <NotificationRow
                key={`${row.connectionId}:${row.profile}:${row.id}`}
                row={row}
                accent={row.accent}
                multi={multi}
                unread={row.status === "unread" && !readIds.has(rowKey(row))}
                active={row.id === activeId && row.profile === activeProfile && row.connectionId === activeConnId}
                onSelect={onSelectRow}
                onDelete={onDeleteRow}
              />
            ))}
          </Fragment>
        ))
      )}
    </ul>
  );

  return (
    <BrowseModal
      open={open}
      onClose={onClose}
      title="Notifications"
      loading={loading}
      loadingLabel="Syncing notifications"
      kicker={unreadCount > 0 ? `${unreadCount} unread` : null}
      actions={unreadCount > 0 ? <Btn variant="ghost" onClick={onMarkAll}>Mark all read</Btn> : null}
      search={{ value: query, onChange: setQuery, placeholder: "Search notifications…", label: "Search notifications" }}
      list={list}
    >
      {detail ? (
        <DetailPane
          row={detail}
          accent={activeRow?.accent}
          connId={activeConnId}
          connectionName={activeRow?.connectionName}
          voiceId={activeVoiceId}
          onCopy={onCopy}
          onSendToChat={onSendToChat}
          onDownload={onDownload}
          onAction={onAction}
          action={contextAction(detail)}
        />
      ) : (
        <div className={styles.detailEmpty}>Select a notification.</div>
      )}
    </BrowseModal>
  );
}


function NotificationRow({ row, accent, multi, unread, active, onSelect, onDelete }) {
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
      className={`${styles.row} ${active ? styles.rowActive : ""} ${unread ? styles.rowUnread : ""}`}
      onClick={() => onSelect?.(row)}
    >
      <div className={styles.rowBody}>
        <div className={styles.rowMeta}>
          <span className={styles.rowMetaLead}>
            <span className={styles.rowDiamond}><Diamond color={accent} /></span>
            <Mono className={styles.rowProfile}>@{label}</Mono>
            {multi && row.connectionName ? <Mono className={styles.rowConn}>· {row.connectionName}</Mono> : null}
          </span>
          <span className={styles.rowSlot}>
            {sev ? <span className={`${styles.rowSev} ${sev === "error" ? styles.rowSevError : styles.rowSevWarning}`} aria-hidden /> : null}
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


function DetailPane({ row, accent, connId, connectionName, voiceId, onCopy, onSendToChat, onDownload, onAction, action }) {
  const label = profileLabel(row.profile);
  const tag = typeTag(row);
  const isHost = connId === "local";
  const externalDelivery = (row.delivered_to || []).filter((c) => c !== "alpi");

  const [ttsState, setTtsState] = useState(null);
  useEffect(() => subscribeTts(setTtsState), []);
  const online = useOnline();
  const ttsKey = `notif:${connId}:${row.profile}:${row.id}`;
  const ttsKind = ttsState?.key === ttsKey ? ttsState.kind : null;
  const isLoading = ttsKind === "loading";
  const isPlaying = ttsKind === "playing";
  const ttsDisabled = (!online && !isPlaying) || !row.body;
  const speakTip = !online && !isPlaying
    ? "Offline — TTS unavailable"
    : isLoading ? "Loading…" : isPlaying ? "Stop" : "Read aloud";
  const onSpeak = () => {
    if (!row.body) return;
    playTts({ key: ttsKey, profile: row.profile, voice: voiceId ?? row.voice_id ?? VOICE_POOL[0], text: row.body, accent });
  };

  return (
    <article className={styles.article}>
      <div className={styles.detailMeta}>
        <span className={styles.detailMetaProfile}>
          {!isHost && connectionName ? <span className={styles.detailMetaConn}>{connectionName}/</span> : null}
          <Diamond color={accent} />
          <span className={styles.detailMetaName}>@{label}</span>
          <span className={styles.detailMetaDot}>·</span>
          <span className={styles.detailMetaDate}>{fmtAbsolute(row.created_at)}</span>
        </span>
        {tag ? <Chip state={tag === "error" ? "error" : "warn"} size="sm">{tag}</Chip> : null}
        <span className={styles.detailMetaSpacer} />
        <Tip text={speakTip} side="l" escape>
          <IconBtn aria-label={speakTip} disabled={ttsDisabled} onClick={onSpeak}>
            {isLoading ? (
              <DSSpinnerIcon />
            ) : isPlaying ? (
              <WaveBars accent={accent} active />
            ) : (
              <VolumeIcon />
            )}
          </IconBtn>
        </Tip>
        <Tip text="Send to chat" side="l" escape>
          <IconBtn aria-label="Send to chat" onClick={onSendToChat}>
            <SendToChatIcon />
          </IconBtn>
        </Tip>
        <Tip text="Download .md" side="l" escape>
          <IconBtn aria-label="Download as markdown" onClick={onDownload}>
            <DownloadIcon />
          </IconBtn>
        </Tip>
        <Tip text="Copy" side="l" escape>
          <IconBtn aria-label="Copy notification" onClick={onCopy}>
            <CopyIcon />
          </IconBtn>
        </Tip>
      </div>

      {(row.title || "").trim() ? (
        <h2 className={styles.detailTitle}>{row.title}</h2>
      ) : null}

      <NotificationBody body={row.body || ""} lead={!(row.title || "").trim()} />

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
