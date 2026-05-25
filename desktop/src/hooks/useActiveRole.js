import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

export function useActiveRole() {
  const [role, setRole] = useState(null);

  useEffect(() => {
    let cancelled = false;

    const refresh = async () => {
      try {
        const state = await invoke("host_connections");
        const active = state?.connections?.find((c) => c.id === state.active_id);
        if (!cancelled) setRole(active?.role ?? null);
      } catch {
        if (!cancelled) setRole(null);
      }
    };

    refresh();
    const off = listen("connection-status", refresh);

    return () => {
      cancelled = true;
      off.then((f) => f()).catch(() => {});
    };
  }, []);

  return role;
}
