import { useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { normalizeActivity } from "./useActivity.js";
import { connectionCanManage } from "../lib/connection-access.js";

export const OTHER_SCHEDULES_POLL_MS = 300000;

export function useOtherSchedules({ connections, activeId }) {
  const key = useMemo(
    () => JSON.stringify((connections ?? []).filter((c) => c.id !== activeId && c.status === "online" && connectionCanManage(connections, c.id)).map((c) => [c.id, c.name ?? c.id])),
    [connections, activeId],
  );
  const [rows, setRows] = useState([]);
  const last = useRef(new Map());
  useEffect(() => {
    const targets = JSON.parse(key);
    if (!targets.length) {
      setRows([]);
      return undefined;
    }
    let cancelled = false;
    const load = () =>
      Promise.all(
        targets.map(([id, name]) =>
          invoke("activity_list", { connectionId: id })
            .then((res) => ({ id, name, scheduled: normalizeActivity(res).scheduled }))
            .then((row) => {
              last.current.set(id, row);
              return row;
            })
            .catch(() => last.current.get(id) ?? null),
        ),
      ).then((next) => {
        if (!cancelled) setRows(next.filter(Boolean));
      });
    load();
    const timer = setInterval(load, OTHER_SCHEDULES_POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [key]);
  const current = useMemo(() => new Set(JSON.parse(key).map(([id]) => id)), [key]);
  return useMemo(() => rows.filter((r) => current.has(r.id)), [rows, current]);
}
