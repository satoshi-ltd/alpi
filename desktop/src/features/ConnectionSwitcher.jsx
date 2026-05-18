import { useEffect, useRef, useState } from "react";
import { ConnPill } from "../primitives/index.js";
import { ConnectionPanel } from "../primitives/Panels.jsx";
import { Eyebrow } from "../primitives/index.js";
import { useNotify } from "../primitives/Notification.jsx";
import styles from "./ConnectionSwitcher.module.css";

function tooltipFor(_connection, status) {
  return status === "offline" || status === "auth-failed"
    ? "Daemon offline — click to retry"
    : "Switch connection";
}

export default function ConnectionSwitcher({
  className = "",
  state,
  onSetActive,
  onAddRemote,
  onForget,
  onOpen,
}) {
  const [open, setOpen] = useState(false);
  const probeTimerRef = useRef(null);
  const notify = useNotify();
  const connections = state?.connections ?? [];
  const activeId = state?.active_id ?? "local";
  const active =
    connections.find((c) => c.id === activeId) ??
    connections.find((c) => c.kind === "local");
  const label = active?.kind === "remote" ? active.name : "Local";
  const caption =
    active?.kind === "remote"
      ? `${active.host}:${active.port}`
      : "host.sock";
  const activeStatus = active?.status ?? "unknown";

  useEffect(
    () => () => {
      if (probeTimerRef.current != null) {
        cancelAnimationFrame(probeTimerRef.current);
      }
    },
    [],
  );

  const handleOpen = () => {
    setOpen(true);
    if (activeStatus !== "offline" && activeStatus !== "auth-failed") {
      if (probeTimerRef.current != null) {
        cancelAnimationFrame(probeTimerRef.current);
      }
      probeTimerRef.current = requestAnimationFrame(() => {
        probeTimerRef.current = null;
        onOpen?.().catch(() => {});
      });
    }
  };

  return (
    <div className={`${styles.root} ${className}`}>
      <Eyebrow style={{ padding: "var(--space-6) var(--space-4) var(--space-2) var(--space-1)" }}>
        Connection
      </Eyebrow>
      <ConnPill
        kind={active?.kind === "remote" ? "remote" : "local"}
        name={label}
        host={caption}
        status={activeStatus}
        onClick={handleOpen}
        tipText={tooltipFor(active, activeStatus)}
      />
      <ConnectionPanel
        open={open}
        onClose={() => setOpen(false)}
        connections={connections.map((c) => ({
          id: c.id,
          kind: c.kind,
          name: c.kind === "remote" ? c.name : "Local daemon",
          host:
            c.kind === "remote" ? `${c.host}:${c.port}` : "host.sock",
          status: c.status,
          alpi_version: c.alpi_version ?? null,
        }))}
        activeId={activeId}
        onPick={(r) => {
          onSetActive?.(r.id);
          setOpen(false);
        }}
        onForget={(r) => onForget?.(r.id)}
        onPair={async (payload) => {
          try {
            const { name } = (await onAddRemote?.(payload)) ?? {};
            notify({
              message: name ? `Paired ${name}` : "Device paired",
              variant: "success",
            });
            setOpen(false);
            return true;
          } catch (e) {
            notify({
              message: `Pairing failed: ${String(e)}`,
              variant: "error",
              duration: 5000,
            });
            return false;
          }
        }}
      />
    </div>
  );
}
