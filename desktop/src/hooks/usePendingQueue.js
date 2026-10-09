import { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

// Cold-start recovery: the event stream anchors at next_seq, so requests emitted before mount only exist in the daemon's pending list. The queue is dropped and refetched on every connection switch — a stale entry would route the response through the wrong daemon.
export function usePendingQueue({ command, connectionId, enqueue }) {
  const [queue, setQueue] = useState([]);
  const queueRef = useRef(queue);
  queueRef.current = queue;
  const connectionRef = useRef(connectionId);
  connectionRef.current = connectionId;

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

  const refetch = useCallback(() => {
    const askedOn = connectionRef.current;
    const known = new Set(queueRef.current.map((r) => r.request_id));
    return invoke(command)
      .then((res) => {
        if (connectionRef.current !== askedOn) return;
        const fresh = res?.requests || [];
        const live = new Set(fresh.map((r) => r.request_id));
        setQueue((q) => fresh.reduce((acc, it) => enqueue(acc, it), q.filter((r) => live.has(r.request_id) || !known.has(r.request_id))));
      })
      .catch(() => {});
  }, [command, enqueue]);

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
