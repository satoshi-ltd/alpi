import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import Button from "../../../primitives/Button.jsx";
import Chip from "../../../primitives/Chip.jsx";
import Dropdown from "../../../primitives/Dropdown.jsx";
import Modal from "../../../primitives/Modal.jsx";
import Skeleton from "../../../primitives/Skeleton.jsx";
import { CopyIcon } from "../../../primitives/icons.jsx";
import useAutoPosition from "../../../primitives/useAutoPosition.js";
import { useNotify } from "../../../primitives/Notification.jsx";
import { useDismissOnOutside } from "../../../hooks/useDismissOnOutside.js";
import { Row, ConfirmButton } from "../primitives.jsx";
import { formatLastSeen } from "../util.js";
import styles from "../../Settings.module.css";

export function DevicesField() {
  const notify = useNotify();
  const [devices, setDevices] = useState(null);
  const [adding, setAdding] = useState(false);
  const [selectedTokenId, setSelectedTokenId] = useState(null);
  const [pairing, setPairing] = useState(null);
  const detailAnchorRef = useRef(null);

  const reload = useCallback(async () => {
    try {
      const list = await invoke("devices_list");
      setDevices(Array.isArray(list) ? list : []);
    } catch (e) {
      setDevices([]);
      notify({ message: `devices: ${String(e)}`, variant: "error" });
    }
  }, [notify]);

  useEffect(() => { reload(); }, [reload]);

  async function revoke(tokenId) {
    try {
      await invoke("devices_revoke", { tokenId });
      notify({ message: "Device revoked", variant: "success" });
      setSelectedTokenId(null);
      await reload();
    } catch (e) {
      notify({ message: `revoke: ${String(e)}`, variant: "error", duration: 4000 });
    }
  }

  async function rename(tokenId, label) {
    try {
      await invoke("devices_rename", { tokenId, label });
      await reload();
    } catch (e) {
      notify({ message: `rename: ${String(e)}`, variant: "error", duration: 4000 });
    }
  }

  if (devices === null) {
    return (
      <Row label="paired">
        <Skeleton width="180px" />
      </Row>
    );
  }

  const selected = selectedTokenId
    ? devices.find((d) => d.token_id === selectedTokenId)
    : null;
  const activeCount = devices.filter((d) => {
    if (!d.last_seen) return false;
    return Date.now() / 1000 - d.last_seen < 86400;
  }).length;

  return (
    <Row label="paired">
      <span className={styles.inlineRow}>
        {devices.length === 0 ? (
          <span className={styles.muted}>none</span>
        ) : (
          <span ref={detailAnchorRef} className={styles.popoverAnchor}>
            <Dropdown
              trigger={{
                label:
                  devices.length === 1
                    ? `1 device · ${activeCount} active`
                    : `${devices.length} devices · ${activeCount} active`,
              }}
              direction="down"
              align="left"
              width={320}
              variant="outlined"
            >
              {({ close }) => (
                <>
                  {devices.map((d) => (
                    <Dropdown.Row
                      key={d.token_id}
                      onClick={() => { close?.(); setSelectedTokenId(d.token_id); }}
                      caption={`…${d.token_id}`}
                      trailing={
                        <Chip size="sm">{formatLastSeen(d.last_seen)}</Chip>
                      }
                    >
                      {d.label || "(unnamed)"}
                    </Dropdown.Row>
                  ))}
                </>
              )}
            </Dropdown>
            {selected && (
              <DeviceDetailPopover
                device={selected}
                anchorRef={detailAnchorRef}
                onClose={() => setSelectedTokenId(null)}
                onRename={(label) => rename(selected.token_id, label)}
                onRevoke={() => revoke(selected.token_id)}
              />
            )}
          </span>
        )}
        <Button size="sm" onClick={() => setAdding(true)}>+ Add device</Button>
      </span>
      {adding && (
        <AddDeviceModal
          onClose={() => setAdding(false)}
          onPaired={(payload) => { setAdding(false); setPairing(payload); reload(); }}
        />
      )}
      {pairing && (
        <DevicePairingModal
          payload={pairing}
          onClose={() => setPairing(null)}
        />
      )}
    </Row>
  );
}

function DeviceDetailPopover({ device, anchorRef, onClose, onRename, onRevoke }) {
  const popoverRef = useRef(null);
  const [label, setLabel] = useState(device.label ?? "");
  const [busy, setBusy] = useState(false);
  const pos = useAutoPosition({
    open: true,
    anchorRef,
    popoverRef,
    direction: "down",
    align: "left",
  });
  useDismissOnOutside({ open: true, onClose, wrapRef: popoverRef });

  const dirty = label.trim() !== (device.label ?? "").trim();

  return (
    <div
      ref={popoverRef}
      className={styles.popover}
      style={{
        minWidth: 320,
        maxWidth: pos.maxWidth ?? undefined,
        position: "fixed",
        top: pos.top,
        left: pos.left,
        right: "auto",
        bottom: "auto",
        visibility: pos.ready ? "visible" : "hidden",
      }}
    >
      <div className={styles.field}>
        <label className={styles.label}>label</label>
        <input
          className={`${styles.input} ${styles.inputFull}`}
          type="text"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          spellCheck={false}
          disabled={busy}
        />
      </div>
      <div className={styles.field}>
        <label className={styles.label}>token id</label>
        <span className={styles.mono}>…{device.token_id}</span>
      </div>
      <div className={styles.field}>
        <label className={styles.label}>last seen</label>
        <span>{formatLastSeen(device.last_seen)}</span>
      </div>
      <div className={styles.actions}>
        <Button size="sm" onClick={onClose} disabled={busy}>Close</Button>
        {dirty && (
          <Button
            size="sm"
            variant="primary"
            loading={busy}
            onClick={async () => {
              setBusy(true);
              try { await onRename(label.trim()); onClose(); }
              finally { setBusy(false); }
            }}
          >
            Save
          </Button>
        )}
        <ConfirmButton
          size="sm"
          label="Revoke"
          confirmLabel="Confirm revoke"
          loading={busy}
          onConfirm={async () => {
            setBusy(true);
            try { await onRevoke(); }
            finally { setBusy(false); }
          }}
        />
      </div>
    </div>
  );
}

function AddDeviceModal({ onClose, onPaired }) {
  const notify = useNotify();
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);
  const [warn, setWarn] = useState(null);

  async function generate() {
    if (!label.trim()) {
      notify({ message: "Label is required", variant: "error" });
      return;
    }
    setWarn(null);
    setBusy(true);
    try {
      const payload = await invoke("devices_generate", { label: label.trim() });
      onPaired(payload);
    } catch (e) {
      const msg = String(e);
      if (msg.includes("no-advertised-host")) {
        const hint = msg.split("—").slice(1).join("—").trim();
        setWarn(
          "Cannot pair — no Tailscale or LAN address detected. " +
          (hint ? `Detected: ${hint}` : "") +
          " Connect to Wi-Fi / Ethernet, install Tailscale, " +
          "or set host.tcp_host in config.yaml.",
        );
      } else {
        notify({ message: `generate: ${msg}`, variant: "error", duration: 4000 });
      }
      setBusy(false);
    }
  }

  return (
    <Modal title="Pair a new device" onClose={onClose}>
      <div className={styles.field}>
        <label className={styles.label}>Label</label>
        <input
          className={`${styles.input} ${styles.inputFull}`}
          type="text"
          value={label}
          autoFocus
          onChange={(e) => setLabel(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") generate(); }}
          placeholder="iPhone, MacBook, …"
          spellCheck={false}
          disabled={busy}
        />
      </div>
      {warn && <div className={styles.warn}>{warn}</div>}
      <div className={styles.actions}>
        <Button size="sm" onClick={onClose} disabled={busy}>Close</Button>
        <Button size="sm" variant="primary" onClick={generate} loading={busy}>
          Generate QR
        </Button>
      </div>
    </Modal>
  );
}

function DevicePairingModal({ payload, onClose }) {
  const notify = useNotify();
  const [qrSvg, setQrSvg] = useState("");

  const qrPayload = useMemo(() => {
    if (!payload.host || !payload.port) return null;
    return JSON.stringify({
      v: 2,
      i: payload.host,
      p: payload.port,
      n: payload.pairing_name || "",
      t: payload.token,
    });
  }, [payload]);

  const desktopLink = useMemo(() => {
    if (!payload.host || !payload.port) return null;
    const params = new URLSearchParams({
      v: "2",
      host: payload.host,
      port: String(payload.port),
      name: payload.pairing_name || "",
      token: payload.token,
    });
    return `alpi://device?${params.toString()}`;
  }, [payload]);

  useEffect(() => {
    if (!qrPayload) return;
    let cancelled = false;
    import("qrcode").then(({ default: QRCode }) =>
      QRCode.toString(qrPayload, { type: "svg", margin: 1, errorCorrectionLevel: "L" })
    ).then((svg) => { if (!cancelled) setQrSvg(svg); })
     .catch((e) => notify({ message: `QR: ${String(e)}`, variant: "error" }));
    return () => { cancelled = true; };
  }, [qrPayload, notify]);

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(desktopLink);
      notify({ message: "Pairing link copied", variant: "success" });
    } catch (e) {
      notify({ message: `Copy failed: ${e}`, variant: "error" });
    }
  }

  if (!payload.host || !payload.port) {
    return (
      <Modal title={payload.label} onClose={onClose}>
        <div className={styles.muted}>
          Cannot pair — no advertised host. Set up Tailscale or a LAN
          address first, then run "Add device" again.
        </div>
        <div className={styles.muted} style={{ marginTop: "var(--space-2)" }}>
          Token saved as <span className={styles.mono}>…{payload.token.slice(-8)}</span>
        </div>
        <div className={styles.actions}>
          <Button size="sm" variant="primary" onClick={onClose}>Done</Button>
        </div>
      </Modal>
    );
  }

  return (
    <Modal title={payload.label} onClose={onClose}>
      <div className={styles.deviceQr} dangerouslySetInnerHTML={{ __html: qrSvg }} />

      <div className={`${styles.inlineRow} ${styles.inlineRowCenter}`}>
        <span className={styles.mono}>{payload.host}:{payload.port}</span>
        <span className={styles.muted}>·</span>
        <span className={styles.mono}>…{payload.token.slice(-8)}</span>
      </div>

      <div className={`${styles.inlineRow} ${styles.inlineRowNoWrap}`}>
        <code
          className={`${styles.mono} ${styles.muted} ${styles.truncate} ${styles.flexFill}`}
        >
          {desktopLink}
        </code>
        <Button
          size="sm"
          icon={<CopyIcon />}
          onClick={copyLink}
          title="Copy pairing link"
          tooltipAlign="end"
        />
      </div>

      <div className={styles.actions}>
        <Button size="sm" variant="primary" onClick={onClose}>Done</Button>
      </div>
    </Modal>
  );
}
