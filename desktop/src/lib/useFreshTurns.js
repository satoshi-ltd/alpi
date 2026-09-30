import { useRef } from "react";

// Decided once per key and never revised: flipping the class later would replay the rise.
export function useFreshTurns(sessionKey, keys, { ready, streamKey = null }) {
  const ref = useRef(null);
  if (ref.current === null || ref.current.session !== sessionKey) {
    ref.current = { session: sessionKey, decided: new Map(), streams: new Map(), primed: false, prevStreaming: streamKey != null };
  }
  const st = ref.current;
  const streaming = streamKey != null;
  const quiet = !st.primed || st.prevStreaming || streaming;
  keys.forEach((k, i) => {
    if (!st.decided.has(k)) st.decided.set(k, !quiet && i === keys.length - 1);
  });
  if (streaming && !st.streams.has(streamKey)) st.streams.set(streamKey, st.primed);
  if (ready) st.primed = true;
  st.prevStreaming = streaming;
  return {
    freshKeys: st.decided,
    streamFresh: streaming && st.streams.get(streamKey) === true,
  };
}
