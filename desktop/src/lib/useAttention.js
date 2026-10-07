import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { subscribeDaemonEvent } from "./daemon-bus.js";

const EVENTS = new Set(["attention.changed", "memory_changed", "schedule.changed", "schedule.failed", "schedule.done"]);
const UNSUPPORTED = /-32601|method.not.found|forbidden/i;
export const ATTENTION_DEBOUNCE_MS = 300;

export function useAttention({ open, profile, connectionId }) {
  const conn = connectionId ?? "";
  const key = `${profile}|${conn}`;
  const [state, setState] = useState({ key: null, value: null });

  useEffect(() => {
    if (!open || !profile) return undefined;
    let alive = true;
    let off = false;
    let timer = null;
    let inFlight = false;
    let again = false;
    const load = () => {
      if (off) return;
      if (inFlight) { again = true; return; }
      inFlight = true;
      invoke("profile_attention", { profile, connectionId })
        .then((res) => {
          if (alive) setState({ key, value: res && typeof res === "object" ? res : null });
        })
        .catch((e) => {
          if (!alive || !UNSUPPORTED.test(String(e))) return;
          off = true;
          setState({ key, value: null });
        })
        .finally(() => {
          inFlight = false;
          if (alive && again) { again = false; load(); }
        });
    };
    load();
    const unsubscribe = subscribeDaemonEvent((event) => {
      const payload = event?.payload ?? {};
      const frame = payload.frame ?? payload;
      if (!EVENTS.has(frame?.event) || frame?.data?.profile !== profile) return;
      if (connectionId && payload.connection_id && payload.connection_id !== connectionId) return;
      clearTimeout(timer);
      timer = setTimeout(load, ATTENTION_DEBOUNCE_MS);
    });
    return () => {
      alive = false;
      clearTimeout(timer);
      unsubscribe?.();
      setState({ key: null, value: null });
    };
  }, [open, profile, conn]);

  return state.key === key ? state.value : null;
}
