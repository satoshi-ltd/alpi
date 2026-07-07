import { useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { reconstructFromEvents } from "../lib/reconstructTurn.js";

const TAIL_POLL_MS = 1200;

export function useSidecarTail({ profile, sessionId, active, onDone }) {
  const [live, setLive] = useState(null);
  const stateRef = useRef({ key: null, events: [], nextSeq: 0, done: false });
  const onDoneRef = useRef(onDone);
  useEffect(() => { onDoneRef.current = onDone; }, [onDone]);

  useEffect(() => {
    if (!active || !profile || !sessionId) {
      setLive(null);
      stateRef.current = { key: null, events: [], nextSeq: 0, done: false };
      return undefined;
    }
    const key = `${profile}/${sessionId}`;
    if (stateRef.current.key !== key) {
      stateRef.current = { key, events: [], nextSeq: 0, done: false };
      setLive(null);
    }
    let cancelled = false;
    let timer = null;
    const tick = async () => {
      const st = stateRef.current;
      if (!st.done) {
        try {
          const res = await invoke("chat_events_since", { profile, sessionId, afterSeq: st.nextSeq });
          if (!cancelled && res?.exists) {
            const fresh = Array.isArray(res.events) ? res.events : [];
            if (fresh.length) {
              st.events.push(...fresh);
              st.nextSeq = fresh.reduce((m, e) => Math.max(m, Number(e.seq) || 0), st.nextSeq);
              const rebuilt = reconstructFromEvents(st.events);
              setLive(rebuilt);
              if (rebuilt.sawDone && !st.done) {
                st.done = true;
                onDoneRef.current?.();
              }
            }
          }
        } catch { /* transient — retry next tick */ }
      }
      if (!cancelled) timer = setTimeout(tick, TAIL_POLL_MS);
    };
    tick();
    return () => { cancelled = true; if (timer) clearTimeout(timer); };
  }, [profile, sessionId, active]);

  return live;
}
