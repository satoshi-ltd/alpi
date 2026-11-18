import { useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { subscribe } from "../lib/daemon-bus.js";

const _listeners = new Set();

export function announceActiveConnection(state) {
  const id = state?.active_id ?? null;
  const role = state?.connections?.find((c) => c.id === id)?.role ?? null;
  for (const fn of Array.from(_listeners)) fn(id, role);
}

export function useActiveRole() {
  const [role, setRole] = useState(null);
  const announcedId = useRef(null);

  useEffect(() => {
    let cancelled = false;

    const refresh = async () => {
      try {
        const state = await invoke("host_connections");
        if (cancelled) return;
        // Until Rust has taken a switch its answer still describes the connection the app just left.
        if (announcedId.current != null && state?.active_id !== announcedId.current) return;
        const active = state?.connections?.find((c) => c.id === state.active_id);
        setRole(active?.role ?? null);
      } catch {
        if (!cancelled) setRole(null);
      }
    };
    const onAnnounced = (id, nextRole) => {
      announcedId.current = id;
      setRole(nextRole);
    };

    refresh();
    const unsub = subscribe("connection-status", refresh);
    _listeners.add(onAnnounced);

    return () => {
      cancelled = true;
      unsub();
      _listeners.delete(onAnnounced);
    };
  }, []);

  return role;
}
