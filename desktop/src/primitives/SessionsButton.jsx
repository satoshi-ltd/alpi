import { useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import {
  Btn,
  ChevDownIcon,
  Eyebrow,
  IconBtn,
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

export default function SessionsButton({
  profile,
  accent,
  activeSessionId,
  onChange,
  onNew,
}) {
  const [open, setOpen] = useState(false);
  const [manageOpen, setManageOpen] = useState(false);
  const [sessions, setSessions] = useState([]);
  const [loaded, setLoaded] = useState(false);
  const [reloadTick, setReloadTick] = useState(0);

  useEffect(() => {
    if (!profile) {
      setSessions([]);
      setLoaded(false);
      return undefined;
    }
    let cancelled = false;
    invoke("sessions", { profile, limit: RECENT_LIMIT })
      .then((all) => {
        if (cancelled) return;
        setSessions((all || []).filter((s) => s.kind === "chat"));
        setLoaded(true);
      })
      .catch(() => {
        if (cancelled) return;
        setSessions([]);
        setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, [profile, open, reloadTick]);

  const grouped = useMemo(() => {
    const m = new Map();
    for (const s of sessions) {
      // mtime is unreliable post-checkout/rsync; prefer updated_at from session content.
      const ts = (s.updated_at ?? s.started_at ?? s.mtime ?? 0) * 1000;
      const k = bucketFor(ts);
      if (!m.has(k)) m.set(k, []);
      m.get(k).push(s);
    }
    return [...m.entries()];
  }, [sessions]);

  if (!loaded || sessions.length === 0) return null;

  return (
    <span className={styles.root}>
      <Tip text="Sessions — switch or browse history" side="r">
        <Btn variant="ghost" onClick={() => setOpen((o) => !o)}>
          <span>Sessions</span>
          <ChevDownIcon className={styles.chev} />
        </Btn>
      </Tip>
      <Tip text="New session" side="r">
        <IconBtn aria-label="New session" onClick={onNew}>
          <PlusIcon />
        </IconBtn>
      </Tip>
      <Popover open={open} onClose={() => setOpen(false)} width="var(--pop-lg)" align="right">
        <div className={styles.scroll}>
          {sessions.length === 0 && (
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
