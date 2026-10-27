import { useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { normalizeActivity } from "./useActivity.js";
import { subscribeDaemonEvent } from "../lib/daemon-bus.js";
import { defaultAsAlpaca } from "../../../common/folds.mjs";
import { connectionCanManage } from "../lib/connection-access.js";

export const OTHER_ACTIVITY_POLL_MS = 300000;
export const OTHER_ACTIVITY_DEBOUNCE_MS = 500;

const REVOKED = /forbidden|-32601|method-not-found/i;

function profileLooks(profiles) {
  const folds = {};
  const accents = {};
  for (const p of Array.isArray(profiles) ? profiles.map(defaultAsAlpaca("var(--accent)")) : []) {
    folds[p.name] = p.fold ?? null;
    accents[p.name] = p.accent ?? null;
  }
  return { folds, accents };
}

export function useOtherActivity({ connections, activeId }) {
  const key = useMemo(
    () => JSON.stringify((connections ?? []).filter((c) => c.id !== activeId && c.status === "online").map((c) => [c.id, c.name ?? c.id, connectionCanManage(connections, c.id)])),
    [connections, activeId],
  );
  const [rows, setRows] = useState([]);
  const last = useRef(new Map());
  useEffect(() => {
    const targets = JSON.parse(key);
    const ids = new Set(targets.map((t) => t[0]));
    for (const id of last.current.keys()) if (!ids.has(id)) last.current.delete(id);
    if (!targets.length) {
      setRows([]);
      return undefined;
    }
    setRows(targets.map((t) => last.current.get(t[0])).filter(Boolean));
    let cancelled = false;
    const version = new Map();
    const fetchOne = ([id, name, admin]) => {
      const mine = (version.get(id) ?? 0) + 1;
      version.set(id, mine);
      return Promise.all([
        invoke("activity_list", { connectionId: id }),
        invoke("profile_summaries", { connectionId: id }).catch(() => []),
      ])
        .then(([res, profiles]) => ({ id, name, member: !admin, activity: normalizeActivity(res), ...profileLooks(profiles) }))
        .then((row) => {
          if (version.get(id) !== mine) return last.current.get(id) ?? row;
          last.current.set(id, row);
          return row;
        })
        .catch((error) => {
          if (REVOKED.test(String(error?.message ?? error))) {
            last.current.delete(id);
            return null;
          }
          return last.current.get(id) ?? null;
        });
    };
    const load = (only) =>
      Promise.all(targets.map((t) => (only && only !== t[0] ? (last.current.get(t[0]) ?? null) : fetchOne(t)))).then((next) => {
        if (!cancelled) setRows(next.filter(Boolean));
      });
    load();
    const timer = setInterval(() => load(), OTHER_ACTIVITY_POLL_MS);
    const pending = new Map();
    const unsub = subscribeDaemonEvent((e) => {
      const payload = e?.payload ?? {};
      const id = payload.connection_id;
      if (!id || !targets.some((t) => t[0] === id)) return;
      const frame = payload.frame ?? payload;
      if (!payload.replay && frame?.event !== "activity.changed") return;
      if (pending.has(id)) clearTimeout(pending.get(id));
      pending.set(id, setTimeout(() => {
        pending.delete(id);
        load(id);
      }, OTHER_ACTIVITY_DEBOUNCE_MS));
    });
    return () => {
      cancelled = true;
      clearInterval(timer);
      unsub();
      for (const t of pending.values()) clearTimeout(t);
    };
  }, [key]);
  const current = useMemo(() => new Set(JSON.parse(key).map(([id]) => id)), [key]);
  return useMemo(() => rows.filter((r) => current.has(r.id)), [rows, current]);
}
