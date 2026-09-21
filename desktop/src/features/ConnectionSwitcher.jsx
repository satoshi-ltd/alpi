import { useEffect, useRef, useState } from "react";
import { orderConnections, readLastActive } from "../lib/connection-recency.js";
import { ConnPill } from "../primitives/index.js";
import { ConnectionPanel } from "../primitives/Panels.jsx";
import { Eyebrow } from "../primitives/index.js";
import { useNotify } from "../primitives/Notification.jsx";
import {
  RATE_LIMITED,
  RATE_LIMITED_MESSAGE,
  isRateLimitedError,
} from "../lib/connection-status.js";
import styles from "./ConnectionSwitcher.module.css";

export function pairingFailureNotice(error) {
  const text = String(error);
  if (isRateLimitedError(text)) {
    return { message: RATE_LIMITED_MESSAGE, variant: "warning", duration: 5000 };
  }
  return { message: `Pairing failed: ${text}`, variant: "error", duration: 5000 };
}

function tooltipFor(_connection, status) {
  if (status === "disabled") return "Connection disabled by host";
  if (status === RATE_LIMITED) return RATE_LIMITED_MESSAGE;
  return status === "offline" || status === "auth-failed"
    ? "Daemon offline — click to retry"
    : "Switch connection";
}

export function connectionEndpoint(connection) {
  if (connection?.kind !== "remote") return "host.sock";
  if (connection.url) return connection.url;
  if (connection.host && connection.port) return `${connection.host}:${connection.port}`;
  if (connection.host) return connection.host;
  return "endpoint unavailable";
}

export function useFireOnce(signal, onTrigger) {
  const firedRef = useRef(false);
  useEffect(() => {
    if (!signal || firedRef.current) return;
    firedRef.current = true;
    onTrigger();
  }, [signal, onTrigger]);
}

export default function ConnectionSwitcher({
  className = "",
  state,
  onSetActive,
  onAddRemote,
  onForget,
  onRename,
  onOpen,
  autoOpenSignal = false,
  locked = false,
}) {
  const [open, setOpen] = useState(false);
  const probeTimerRef = useRef(null);
  const notify = useNotify();
  const closePanel = () => {
    if (!locked) setOpen(false);
  };

  useFireOnce(autoOpenSignal, () => {
    setOpen(true);
    onOpen?.().catch(() => {});
  });
  const connections = state?.connections ?? [];
  const activeId = state?.active_id ?? "local";
  const active =
    connections.find((c) => c.id === activeId) ??
    connections.find((c) => c.kind === "local");
  const label = active?.kind === "remote" ? active.name : "Local";
  const caption = connectionEndpoint(active);
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
    if (
      activeStatus !== "offline" &&
      activeStatus !== "disabled" &&
      activeStatus !== "auth-failed"
    ) {
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
      <Eyebrow className={styles.label}>Connection</Eyebrow>
      <ConnPill
        kind={active?.kind === "remote" ? "remote" : "local"}
        name={label}
        host={caption}
        status={activeStatus}
        onClick={handleOpen}
        tipText={tooltipFor(active, activeStatus)}
      />
      <ConnectionPanel
        open={open || locked}
        locked={locked}
        onClose={closePanel}
        connections={orderConnections(connections, readLastActive()).map((c) => ({
          id: c.id,
          kind: c.kind,
          name: c.kind === "remote" ? c.name : "Local daemon",
          host: connectionEndpoint(c),
          status: c.status,
          revoked: c.revoked ?? false,
          alpi_version: c.alpi_version ?? null,
        }))}
        activeId={activeId}
        onPick={(r) => {
          onSetActive?.(r.id);
          closePanel();
        }}
        onForget={(r) => onForget?.(r.id)}
        onRename={
          onRename
            ? async (r, name) => {
                try {
                  await onRename(r.id, name);
                } catch (e) {
                  notify({ message: e?.message || String(e), variant: "danger" });
                }
              }
            : undefined
        }
        onPair={async (payload) => {
          try {
            const { name } = (await onAddRemote?.(payload)) ?? {};
            notify({
              message: name ? `Paired ${name}` : "Device paired",
              variant: "success",
            });
            closePanel();
            return true;
          } catch (e) {
            notify(pairingFailureNotice(e));
            return false;
          }
        }}
      />
    </div>
  );
}
