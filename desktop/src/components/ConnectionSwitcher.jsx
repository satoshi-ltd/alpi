import { useState } from "react";
import Button from "../primitives/Button.jsx";
import Dropdown from "../primitives/Dropdown.jsx";
import {
  LocalConnectionIcon,
  RemoteConnectionIcon,
} from "../primitives/icons.jsx";
import styles from "./ConnectionSwitcher.module.css";

export default function ConnectionSwitcher({
  className = "",
  state,
  onSetActive,
  onAddRemote,
  onForget,
  onOpen,
}) {
  const [payload, setPayload] = useState("");
  const connections = state?.connections ?? [];
  const activeId = state?.active_id ?? "local";
  const active =
    connections.find((c) => c.id === activeId) ??
    connections.find((c) => c.kind === "local");
  const label = active?.kind === "remote" ? active.name : "Local";

  const addRemote = (close) => {
    const text = payload.trim();
    if (!text) return;
    onAddRemote?.(text);
    setPayload("");
    close();
  };

  return (
    <div className={`${styles.root} ${className}`}>
      <Dropdown
        width={340}
        align="left"
        variant="list"
        portal
        onOpenChange={(open) => {
          if (open) onOpen?.().catch(() => {});
        }}
        trigger={{
          leading:
            active?.kind === "remote" ? (
              <RemoteConnectionIcon />
            ) : (
              <LocalConnectionIcon />
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
                  if (c.revoked) return;
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

function ConnectionRow({ connection, active, onSelect, onForget }) {
  const caption =
    connection.kind === "remote"
      ? connection.revoked
        ? `revoked · ${connection.host}:${connection.port}`
        : `${connection.host}:${connection.port}`
      : "host.sock";

  if (connection.kind !== "remote") {
    return (
      <Dropdown.Row
        active={active}
        caption={caption}
        leading={<LocalConnectionIcon />}
        onClick={onSelect}
      >
        {connection.name}
      </Dropdown.Row>
    );
  }

  return (
    <div className={`${styles.row} ${active ? styles.rowActive : ""}`}>
      <span className={styles.rowLead}>
        <RemoteConnectionIcon />
      </span>
      <button
        className={styles.rowMain}
        disabled={!!connection.revoked}
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
