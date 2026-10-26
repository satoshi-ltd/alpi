import { useCallback, useEffect, useRef, useState } from "react";
import { copyText } from "../lib/clipboard.js";

export const COPIED_MS = 1500;

export function useCopyFeedback(onFail) {
  const [copiedKey, setCopiedKey] = useState(null);
  const timer = useRef(null);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      clearTimeout(timer.current);
    };
  }, []);
  const copy = useCallback(async (key, text) => {
    const ok = await copyText(text);
    if (!mounted.current) return;
    if (ok) {
      setCopiedKey(key);
      clearTimeout(timer.current);
      timer.current = setTimeout(() => setCopiedKey(null), COPIED_MS);
    } else {
      onFail?.();
    }
  }, [onFail]);
  return [copiedKey, copy];
}
