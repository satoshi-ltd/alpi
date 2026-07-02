import { useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import {
  Btn,
  ChevDownIcon,
  Eyebrow,
  Kbd,
  Mono,
  Pill,
  PlusIcon,
  Tip,
} from "./index.js";
import { Popover } from "./index.js";
import ManageSessionsModal from "../features/sessions/ManageSessionsModal.jsx";
import styles from "./SessionsButton.module.css";

const DAY_MS = 86400000;
const RECENT_LIMIT = 30;

function startOfDay(ms) {
  const d = new Date(ms);
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

function bucketFor(ms) {
  const today = startOfDay(Date.now());
  if (ms >= today) return "today";
  if (ms >= today - DAY_MS) return "yesterday";
  if (ms >= today - 7 * DAY_MS) return "this week";
  return "earlier";
}

function previewOf(s) {
  const t = (s.first_user || "").trim();
  if (t) return t.length > 56 ? `${t.slice(0, 56)}…` : t;
  return `(empty · ${(s.id || "").slice(0, 6)})`;
}

const _sessionsCache = new Map();

// Keyed by profile name only — App must call this on connection switch so a same-named profile on another daemon can't serve a stale list.
export function invalidateSessionsButtonCache() {
  _sessionsCache.clear();
}

export default function SessionsButton({
  profile,
  accent,
  activeSessionId,
  onChange,
  onNew,
}) {
  const [open, setOpen] = useState(false);
  const [manageOpen, setManageOpen] = useState(false);
  const [sessions, setSessions] = useState(() => (profile ? _sessionsCache.get(profile) ?? [] : []));
  const [loadedProfile, setLoadedProfile] = useState(() => (profile && _sessionsCache.has(profile) ? profile : null));
  const [reloadTick, setReloadTick] = useState(0);
  const [openTick, setOpenTick] = useState(0);

  // Revalidate on OPEN only — `open` as a raw dep also refired the fetch on every close.
  useEffect(() => {
    if (open) setOpenTick((t) => t + 1);
  }, [open]);

  useEffect(() => {
    if (!profile) {
      setSessions([]);
      setLoadedProfile(null);
      return undefined;
    }
    const cached = _sessionsCache.get(profile);
    if (cached) {
      setSessions(cached);
      setLoadedProfile(profile);
    }
    let cancelled = false;
    invoke("sessions", { profile, limit: RECENT_LIMIT })
      .then((all) => {
        if (cancelled) return;
        const chats = (all || []).filter((s) => s.kind === "chat");
        _sessionsCache.set(profile, chats);
        setSessions(chats);
        setLoadedProfile(profile);
      })
      .catch(() => {
        if (cancelled) return;
        setSessions(_sessionsCache.get(profile) ?? []);
        setLoadedProfile(profile);
      });
    return () => {
      cancelled = true;
    };
  }, [profile, openTick, reloadTick]);

  // Never show a prior profile's list while a switch is still loading (stale on remote).
  const isFresh = loadedProfile === profile;
  const shownSessions = isFresh ? sessions : [];

  const grouped = useMemo(() => {
    const m = new Map();
    for (const s of shownSessions) {
      // mtime is unreliable post-checkout/rsync; prefer updated_at from session content.
      const ts = (s.updated_at ?? s.started_at ?? s.mtime ?? 0) * 1000;
      const k = bucketFor(ts);
      if (!m.has(k)) m.set(k, []);
      m.get(k).push(s);
    }
    return [...m.entries()];
  }, [sessions]);

  if (!isFresh) return null;

  return (
    <span className={styles.root}>
      <Tip text="Sessions — switch, start or browse" side="r">
        <Btn variant="ghost" onClick={() => setOpen((o) => !o)}>
          <span>Sessions</span>
          <ChevDownIcon className={styles.chev} />
        </Btn>
      </Tip>
      <Popover open={open} onClose={() => setOpen(false)} width="var(--pop-lg)" align="right">
        <button
          type="button"
          className={styles.newRow}
          onClick={() => {
            onNew?.();
            setOpen(false);
          }}
        >
          <PlusIcon className={styles.newIcon} />
          <span className={styles.newLabel}>New session</span>
          <span className={styles.kbd}><Kbd>⌘</Kbd><Kbd>N</Kbd></span>
        </button>
        <div className={styles.scroll}>
          {shownSessions.length === 0 && (
            <div className={styles.empty}>No sessions yet</div>
          )}
          {grouped.map(([day, items]) => (
            <div key={day}>
              <Eyebrow className={styles.bucket}>{day}</Eyebrow>
              {items.map((s) => {
                const isCurrent = s.id === activeSessionId;
                return (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => {
                      onChange?.(s.id);
                      setOpen(false);
                    }}
                    className={`row ${styles.row} ${isCurrent ? styles.rowCurrent : ""}`}
                  >
                    <span className={styles.preview}>{previewOf(s)}</span>
                    <Mono className="tnum">
                      {s.turn_count} turn{s.turn_count === 1 ? "" : "s"}
                    </Mono>
                  </button>
                );
              })}
            </div>
          ))}
        </div>
        {sessions.length > 0 && (
          <div className={styles.popFooter}>
            <Mono className={styles.popCount}>
              {sessions.length} session{sessions.length === 1 ? "" : "s"}
            </Mono>
            <Btn
              variant="ghost"
              onClick={() => {
                setOpen(false);
                setManageOpen(true);
              }}
            >
              Manage sessions →
            </Btn>
          </div>
        )}
      </Popover>
      <ManageSessionsModal
        open={manageOpen}
        onClose={() => setManageOpen(false)}
        profile={profile}
        accent={accent}
        currentSessionId={activeSessionId}
        onDeleted={(deletedIds) => {
          if (!deletedIds?.length) return;
          if (deletedIds.includes(activeSessionId)) onChange?.(null);
          setReloadTick((n) => n + 1);
        }}
      />
    </span>
  );
}
