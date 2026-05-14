import { useEffect, useRef, useState } from "react";
import Button from "../primitives/Button.jsx";
import Dropdown from "../primitives/Dropdown.jsx";
import Tooltip from "../primitives/Tooltip.jsx";
import {
  LocalConnectionIcon,
  RemoteConnectionIcon,
} from "../primitives/icons.jsx";
import styles from "./ConnectionSwitcher.module.css";

const STATUS_LABEL = {
  online: "Online",
  offline: "Offline",
  probing: "Probing…",
  "auth-failed": "Auth failed",
  unverified: "Unverified",
  unknown: "Unknown",
};

function tooltipFor(connection, status) {
  const label = STATUS_LABEL[status] ?? status;
  if (connection?.error && status !== "online") {
    return `${label} · ${connection.error}`;
  }
  return label;
}

export default function ConnectionSwitcher({
  className = "",
  state,
  onSetActive,
  onAddRemote,
  onForget,
  onOpen,
}) {
  const [payload, setPayload] = useState("");
  const probeTimerRef = useRef(null);
  const connections = state?.connections ?? [];
  const activeId = state?.active_id ?? "local";
  const active =
    connections.find((c) => c.id === activeId) ??
    connections.find((c) => c.kind === "local");
  const label = active?.kind === "remote" ? active.name : "Local";
  const activeStatus = active?.status ?? "unknown";

  const addRemote = (close) => {
    const text = payload.trim();
    if (!text) return;
    onAddRemote?.(text);
    setPayload("");
    close();
  };

  useEffect(
    () => () => {
      if (probeTimerRef.current != null) {
        cancelAnimationFrame(probeTimerRef.current);
      }
    },
    [],
  );

  return (
    <div className={`${styles.root} ${className}`}>
      <div className={styles.label}>Connection</div>
      <Dropdown
        width={340}
        align="left"
        variant="list"
        portal
        onOpenChange={(open) => {
          if (!open) return;
          if (activeStatus === "offline" || activeStatus === "auth-failed") return;
          if (probeTimerRef.current != null) {
            cancelAnimationFrame(probeTimerRef.current);
          }
          probeTimerRef.current = requestAnimationFrame(() => {
            probeTimerRef.current = null;
            onOpen?.().catch(() => {});
          });
        }}
        trigger={{
          leading: (
            <IconBadge status={activeStatus} connection={active}>
              {active?.kind === "remote" ? (
                <RemoteConnectionIcon />
              ) : (
                <LocalConnectionIcon />
              )}
            </IconBadge>
          ),
          label,
        }}
      >
        {({ close }) => (
          <>
            {connections.map((c) => (
              <ConnectionRow
                key={c.id}
                connection={c}
                active={c.id === activeId}
                onSelect={() => {
                  if (isConnectionDisabled(c)) return;
                  onSetActive?.(c.id);
                  close();
                }}
                onForget={() => {
                  onForget?.(c.id);
                  close();
                }}
              />
            ))}
            <Dropdown.Group label="Add remote">
              <textarea
                className={styles.payload}
                value={payload}
                onChange={(e) => setPayload(e.target.value)}
                placeholder="alpi://device?v=2&host=100.64.0.1&port=49200&name=home&token=..."
                rows={4}
              />
              <button
                className={styles.add}
                onClick={() => addRemote(close)}
                disabled={!payload.trim()}
              >
                Pair remote
              </button>
            </Dropdown.Group>
          </>
        )}
      </Dropdown>
    </div>
  );
}

function IconBadge({ status, connection, children }) {
  const badge = (
    <span className={styles.iconWrap}>
      {children}
      <span className={styles.statusBadge} data-status={status} aria-hidden />
    </span>
  );
  if (!connection) return badge;
  return (
    <Tooltip text={tooltipFor(connection, status)} direction="right">
      {badge}
    </Tooltip>
  );
}

function isConnectionDisabled(connection) {
  return (
    !!connection.revoked ||
    connection.status === "offline" ||
    connection.status === "auth-failed"
  );
}

function ConnectionRow({ connection, active, onSelect, onForget }) {
  const status = connection.status ?? "unknown";
  const disabled = isConnectionDisabled(connection);
  const baseCaption =
    connection.kind === "remote"
      ? connection.revoked
        ? `revoked · ${connection.host}:${connection.port}`
        : `${connection.host}:${connection.port}`
      : "host.sock";
  const caption = baseCaption;

  if (connection.kind !== "remote") {
    return (
      <Dropdown.Row
        active={active}
        caption={caption}
        leading={
          <IconBadge status={status} connection={connection}>
            <LocalConnectionIcon />
          </IconBadge>
        }
        disabled={disabled}
        onClick={onSelect}
      >
        {connection.name}
      </Dropdown.Row>
    );
  }

  return (
    <div
      className={`${styles.row} ${active ? styles.rowActive : ""} ${disabled ? styles.rowDisabled : ""}`}
      aria-disabled={disabled}
    >
      <span className={styles.rowLead}>
        <IconBadge status={status} connection={connection}>
          <RemoteConnectionIcon />
        </IconBadge>
      </span>
      <button
        className={styles.rowMain}
        disabled={disabled}
        aria-disabled={disabled}
        onClick={onSelect}
      >
        <span className={styles.rowName}>{connection.name}</span>
        <span className={styles.rowCaption}>{caption}</span>
      </button>
      <Button
        variant="danger"
        size="xs"
        onClick={onForget}
        title="Forget connection"
      >
        Forget
      </Button>
    </div>
  );
}
