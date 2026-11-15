import { useEffect, useRef, useState } from "react";

export const DONE_MS = 2400;

export const turnLive = (turn) => !!turn && !turn.error && !turn.ended && !turn.settling && !turn.interrupted;

export function sessionMarkState({ paused = false, needs = false, turn = null, after = null }) {
  if (paused) return "paused";
  if (needs) return "needs";
  if (turnLive(turn)) return "working";
  return after ?? "idle";
}

const moved = (prev, scope, session) => prev.scope !== scope || (prev.session != null && prev.session !== session);

export function useSessionMark({ turn = null, needs = false, paused = false, scope = "", session = null }) {
  const [after, setAfter] = useState(null);
  const runningRef = useRef(null);
  const scopeRef = useRef({ scope, session });
  const live = turnLive(turn);
  const id = turn?.requestId ?? turn?.at ?? null;
  const failed = !!turn?.error;
  const interrupted = !!turn?.interrupted;
  const moving = moved(scopeRef.current, scope, session);

  useEffect(() => {
    const prev = scopeRef.current;
    scopeRef.current = { scope, session };
    if (moved(prev, scope, session)) {
      runningRef.current = live ? id : null;
      setAfter(failed ? "failed" : null);
      return undefined;
    }
    if (live) {
      runningRef.current = id;
      setAfter(null);
      return undefined;
    }
    if (interrupted) {
      runningRef.current = null;
      setAfter(null);
      return undefined;
    }
    if (failed) {
      runningRef.current = null;
      setAfter("failed");
      return undefined;
    }
    if (runningRef.current == null) return undefined;
    runningRef.current = null;
    setAfter("done");
    return undefined;
  }, [scope, session, live, id, failed, interrupted]);

  useEffect(() => {
    if (after !== "done") return undefined;
    const timer = setTimeout(() => setAfter((cur) => (cur === "done" ? null : cur)), DONE_MS);
    return () => clearTimeout(timer);
  }, [after]);

  return sessionMarkState({ paused, needs, turn, after: moving ? (failed ? "failed" : null) : after });
}
