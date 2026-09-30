import { useCallback, useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

// Cold-start recovery: the event stream anchors at next_seq, so requests emitted before mount only exist in the daemon's pending list. The queue is dropped and refetched on every connection switch — a stale entry would route the response through the wrong daemon.
export function usePendingQueue({ command, connectionId, enqueue }) {
  const [queue, setQueue] = useState([]);

  const resolve = useCallback((requestId) => {
    setQueue((q) => q.filter((r) => r.request_id !== requestId));
  }, []);

  const merge = useCallback((req) => {
    setQueue((q) => enqueue(q, req));
  }, [enqueue]);

  const promote = useCallback((requestId) => {
    setQueue((q) => {
      const i = q.findIndex((r) => r.request_id === requestId);
      if (i <= 0) return q;
      return [q[i], ...q.slice(0, i), ...q.slice(i + 1)];
    });
  }, []);

  const refetch = useCallback(
    () =>
      invoke(command)
        .then((res) => {
          for (const it of res?.requests || []) merge(it);
        })
        .catch(() => {}),
    [command, merge],
  );

  useEffect(() => {
    setQueue([]);
    let cancelled = false;
    invoke(command)
      .then((res) => {
        if (cancelled) return;
        for (const it of res?.requests || []) merge(it);
      })
      .catch(() => { /* daemon may be offline / older */ });
    return () => { cancelled = true; };
  }, [command, connectionId, merge]);

  return { queue, merge, resolve, promote, refetch };
}
