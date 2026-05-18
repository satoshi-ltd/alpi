import { useEffect, useRef } from "react";
import { invoke } from "@tauri-apps/api/core";

const BURST_INTERVAL_MS = 500;
const BURST_TOTAL_MS = 6000;

export function useDaemonAutostart({ activeConnection, onAttempt }) {
  const attemptedKeyRef = useRef(null);

  useEffect(() => {
    if (!activeConnection) return;
    if (activeConnection.kind !== "local") return;
    if (activeConnection.status !== "offline") return;

    const key = activeConnection.id;
    if (attemptedKeyRef.current === key) return;
    attemptedKeyRef.current = key;

    let cancelled = false;
    let burstTimer = null;
    let elapsed = 0;

    onAttempt?.("starting");

    invoke("service_action", { profile: "default", action: "start" })
      .catch(() => {})
      .finally(() => {
        if (cancelled) return;
        const tick = () => {
          if (cancelled) return;
          invoke("host_connections_probe_active").catch(() => {});
          elapsed += BURST_INTERVAL_MS;
          if (elapsed < BURST_TOTAL_MS) {
            burstTimer = setTimeout(tick, BURST_INTERVAL_MS);
          } else {
            onAttempt?.("gave-up");
          }
        };
        burstTimer = setTimeout(tick, BURST_INTERVAL_MS);
      });

    return () => {
      cancelled = true;
      if (burstTimer) clearTimeout(burstTimer);
    };
  }, [activeConnection?.id, activeConnection?.kind, activeConnection?.status, onAttempt]);

  // Reset memory when the user manually transitions back to online — next offline can re-attempt.
  useEffect(() => {
    if (activeConnection?.status === "online") {
      attemptedKeyRef.current = null;
    }
  }, [activeConnection?.status]);
}
