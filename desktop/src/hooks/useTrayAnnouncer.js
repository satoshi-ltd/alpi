import { useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { buildTraySnapshot } from "../lib/traySnapshot.js";
import { subscribeUpdater } from "../lib/updater.js";

export const TRAY_ANNOUNCE_DEBOUNCE_MS = 250;

function useUpdaterFacts() {
  const [facts, setFacts] = useState(null);
  useEffect(
    () =>
      subscribeUpdater((s) => {
        const next = s.available ? { version: s.version ?? null, busy: Boolean(s.installing) } : null;
        setFacts((prev) => (JSON.stringify(prev) === JSON.stringify(next) ? prev : next));
      }),
    [],
  );
  return facts;
}

export function reducedSnapshot(snapshot) {
  return { v: snapshot.v, state: snapshot.state, counts: snapshot.counts };
}

export function useTrayAnnouncer({ connection, daemon, activity, activitySupported, member, unread, foldByProfile, accentByProfile, otherActivity }) {
  const update = useUpdaterFacts();
  const snapshot = useMemo(
    () => buildTraySnapshot({ connection, daemon, activity, activitySupported, member, unread, update, foldByProfile, accentByProfile, otherActivity, nowMs: Date.now() }),
    [connection, daemon, activity, activitySupported, member, unread, update, foldByProfile, accentByProfile, otherActivity],
  );
  const lastSent = useRef(null);
  useEffect(() => {
    const key = JSON.stringify(snapshot);
    if (key === lastSent.current) return undefined;
    const timer = setTimeout(() => {
      lastSent.current = key;
      invoke("tray_announce_state", { snapshot }).catch(() =>
        invoke("tray_announce_state", { snapshot: reducedSnapshot(snapshot) }).catch(() => {
          lastSent.current = null;
        }),
      );
    }, TRAY_ANNOUNCE_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [snapshot]);
}
