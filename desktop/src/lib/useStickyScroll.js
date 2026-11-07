import { useEffect, useLayoutEffect, useRef } from "react";

const NEAR_BOTTOM_PX = 80;

// `transcript` counts identity changes (a new chat becoming a session is the same transcript); `key` stays the in-flight turn's id through its pending → tail phases.
export function followKey(previous, { scope, sessionId, pendingTurn, lastTurnInFlight }) {
  const promoted = !!previous && previous.sessionId == null && sessionId != null
    && pendingTurn != null && pendingTurn.requestId === previous.requestId;
  const continued = !!previous && previous.scope === scope && (previous.sessionId === sessionId || promoted);
  const transcript = continued ? previous.transcript : (previous?.transcript ?? 0) + 1;
  const requestId = pendingTurn?.requestId ?? (continued ? previous.requestId : null) ?? null;
  const key = pendingTurn ? requestId : lastTurnInFlight ? requestId ?? `tail:${transcript}` : null;
  return { scope, sessionId, transcript, requestId, key };
}

// A new non-null `stickKey` (the sent turn's id) or a changed `resetKey` (another transcript) re-engages follow after the user scrolled up.
export function useStickyScroll(deps, stickKey, resetKey) {
  const scrollRef = useRef(null);
  const stickRef = useRef(true);
  const keyRef = useRef(stickKey ?? null);
  const resetRef = useRef(resetKey);
  const boundRef = useRef({ el: null, onScroll: null });
  const rafRef = useRef(0);

  if (stickKey != null && stickKey !== keyRef.current) {
    keyRef.current = stickKey;
    stickRef.current = true;
  }
  if (resetKey !== resetRef.current) {
    resetRef.current = resetKey;
    stickRef.current = true;
  }

  useLayoutEffect(() => {
    const bound = boundRef.current;
    const el = scrollRef.current;
    if (bound.el === el) return;
    unbind(bound);
    if (!el) return;
    bound.el = el;
    bound.onScroll = () => {
      const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
      stickRef.current = distance <= NEAR_BOTTOM_PX;
    };
    el.addEventListener("scroll", bound.onScroll, { passive: true });
  });

  useEffect(() => {
    const el = scrollRef.current;
    if (!el || !stickRef.current) return;
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = 0;
      const cur = scrollRef.current;
      if (cur && stickRef.current) cur.scrollTop = cur.scrollHeight;
    });
  }, deps);

  useEffect(() => () => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    unbind(boundRef.current);
  }, []);

  return scrollRef;
}

function unbind(bound) {
  if (bound.el) bound.el.removeEventListener("scroll", bound.onScroll);
  bound.el = null;
  bound.onScroll = null;
}
