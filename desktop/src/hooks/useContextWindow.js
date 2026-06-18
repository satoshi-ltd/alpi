import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

const DEFAULT_CTX = 200_000;

export function useContextWindow(profile, model, connectionId) {
  const [ctx, setCtx] = useState(DEFAULT_CTX);
  useEffect(() => {
    if (!profile || !model) {
      setCtx(DEFAULT_CTX);
      return undefined;
    }
    let cancelled = false;
    setCtx(DEFAULT_CTX);
    invoke("resolve_ctx_window", { profile, model, connectionId })
      .then((n) => {
        if (!cancelled) setCtx(Number(n) > 0 ? Number(n) : DEFAULT_CTX);
      })
      .catch(() => {
        if (!cancelled) setCtx(DEFAULT_CTX);
      });
    return () => {
      cancelled = true;
    };
  }, [profile, model, connectionId]);
  return ctx;
}
