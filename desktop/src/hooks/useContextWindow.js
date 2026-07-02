import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

const DEFAULT_CTX = 200_000;

// Cache-first: ctx windows are static per model, so a hit skips the RPC entirely.
const _cache = new Map();

export function useContextWindow(profile, model, connectionId) {
  const key = `${connectionId || "local"}|${profile}|${model}`;
  const [ctx, setCtx] = useState(() => _cache.get(key) ?? DEFAULT_CTX);
  useEffect(() => {
    if (!profile || !model) {
      setCtx(DEFAULT_CTX);
      return undefined;
    }
    if (_cache.has(key)) {
      setCtx(_cache.get(key));
      return undefined;
    }
    let cancelled = false;
    setCtx(DEFAULT_CTX);
    invoke("resolve_ctx_window", { profile, model, connectionId })
      .then((n) => {
        const value = Number(n) > 0 ? Number(n) : DEFAULT_CTX;
        _cache.set(key, value);
        if (!cancelled) setCtx(value);
      })
      .catch(() => {
        if (!cancelled) setCtx(DEFAULT_CTX);
      });
    return () => {
      cancelled = true;
    };
  }, [profile, model, connectionId, key]);
  return ctx;
}

// Test-only.
export function _clearCtxWindowCache() {
  _cache.clear();
}
