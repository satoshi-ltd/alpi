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
import { Row } from "../primitives.jsx";
import { Btn } from "../../../primitives/index.js";
import Field from "../../../primitives/Field.jsx";
import { ConfirmDelete, DialogFooter } from "../../../primitives/index.js";
import { formatLastSeen } from "../util.js";
import styles from "../Settings.module.css";

export function DevicesField() {
  const notify = useNotify();
  const [devices, setDevices] = useState(null);
  const [adding, setAdding] = useState(false);
  const [selectedTokenId, setSelectedTokenId] = useState(null);
  const [revokeTarget, setRevokeTarget] = useState(null);
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
              variant="field"
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
                onRequestRevoke={() => {
                  setRevokeTarget(selected);
                  setSelectedTokenId(null);
                }}
              />
            )}
          </span>
        )}
        <Button size="sm" onClick={() => setAdding(true)}>+ Add device</Button>
      </span>
      {adding && (
        <PairDeviceModal
          onClose={() => setAdding(false)}
          onPaired={() => { setAdding(false); reload(); }}
        />
      )}
      {revokeTarget && (
        <ConfirmDelete
          mode="typed"
          open
          onClose={() => setRevokeTarget(null)}
          onConfirm={() => revoke(revokeTarget.token_id)}
          title={`Revoke device ${revokeTarget.label || revokeTarget.token_id}?`}
          consequence={
            <>
              This invalidates the device's pairing token. The device loses
              access immediately and the user must re-pair from scratch. This
              action <strong>cannot be undone</strong>.
            </>
          }
          typeToConfirm={revokeTarget.label || revokeTarget.token_id}
          confirmLabel="Revoke device"
        />
      )}
    </Row>
  );
}

function DeviceDetailPopover({ device, anchorRef, onClose, onRename, onRequestRevoke }) {
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
        <Field
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
      <div className={styles.popoverFooter}>
        <button
          type="button"
          className="alink danger"
          onClick={onRequestRevoke}
          disabled={busy}
        >
          Revoke device…
        </button>
        <span className={styles.popoverFooterRight}>
          <Btn variant="ghost" onClick={onClose} disabled={busy}>Cancel</Btn>
          {dirty && (
            <Btn
              variant="primary"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try { await onRename(label.trim()); onClose(); }
                finally { setBusy(false); }
              }}
            >
              {busy ? "…" : "Save"}
            </Btn>
          )}
        </span>
      </div>
    </div>
  );
}

function PairDeviceModal({ onClose, onPaired }) {
  const notify = useNotify();
  const [label, setLabel] = useState("");
  const [payload, setPayload] = useState(null);
  const [qrSvg, setQrSvg] = useState("");
  const [warn, setWarn] = useState(null);
  const [busy, setBusy] = useState(false);
  const generatedRef = useRef(false);

  useEffect(() => {
    if (generatedRef.current) return;
    generatedRef.current = true;
    invoke("devices_generate", { label: "" })
      .then((p) => {
        const token = p?.token || "";
        setPayload({ ...p, token_id: token.slice(-8) });
      })
      .catch((e) => {
        const msg = String(e);
        if (msg.includes("no-advertised-host")) {
          const hint = msg.split("—").slice(1).join("—").trim();
          setWarn(
            "Cannot pair — no Tailscale or LAN address detected. " +
            (hint ? `Detected: ${hint}. ` : "") +
            "Connect to Wi-Fi / Ethernet, install Tailscale, " +
            "or set host.tcp_host in config.yaml.",
          );
        } else {
          notify({ message: `generate: ${msg}`, variant: "error", duration: 4000 });
        }
      });
  }, [notify]);

  const trimmed = label.trim();
  const ready = Boolean(payload?.host && payload?.port);

  const desktopLink = useMemo(() => {
    if (!ready) return "";
    const params = new URLSearchParams({
      v: "2",
      host: payload.host,
      port: String(payload.port),
      name: trimmed || "device",
      token: payload.token,
    });
    return `alpi://device?${params.toString()}`;
  }, [ready, payload, trimmed]);

  useEffect(() => {
    if (!ready || !trimmed) { setQrSvg(""); return; }
    let cancelled = false;
    const qrPayload = JSON.stringify({
      v: 2, i: payload.host, p: payload.port, n: trimmed, t: payload.token,
    });
    import("qrcode").then(({ default: QRCode }) =>
      QRCode.toString(qrPayload, { type: "svg", margin: 1, errorCorrectionLevel: "L" })
    ).then((svg) => { if (!cancelled) setQrSvg(svg); })
     .catch((e) => notify({ message: `QR: ${String(e)}`, variant: "error" }));
    return () => { cancelled = true; };
  }, [ready, payload, trimmed, notify]);

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(desktopLink);
      notify({ message: "Pairing link copied", variant: "success" });
    } catch (e) {
      notify({ message: `Copy failed: ${e}`, variant: "error" });
    }
  }

  async function pair() {
    if (!ready || !trimmed || busy) return;
    setBusy(true);
    try {
      await invoke("devices_rename", { tokenId: payload.token_id, label: trimmed });
      notify({ message: `Device "${trimmed}" paired`, variant: "success" });
      onPaired?.();
    } catch (e) {
      notify({ message: `pair: ${String(e)}`, variant: "error", duration: 4000 });
      setBusy(false);
    }
  }

  async function cancel() {
    if (payload?.token_id) {
      invoke("devices_revoke", { tokenId: payload.token_id }).catch(() => {});
    }
    onClose?.();
  }

  if (warn) {
    return (
      <Modal title="Pair a new device" onClose={onClose}>
        <div className={styles.warn}>{warn}</div>
        <DialogFooter onCancel={onClose} cancelLabel="Close" />
      </Modal>
    );
  }

  return (
    <Modal title="Pair a new device" onClose={cancel}>
      <div className={styles.field}>
        <label className={styles.label}>Label</label>
        <Field
          className={`${styles.input} ${styles.inputFull}`}
          type="text"
          value={label}
          autoFocus
          onChange={(e) => setLabel(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") pair(); }}
          placeholder="MacBook Pro · Phone · …"
          spellCheck={false}
          disabled={busy}
        />
      </div>

      <div className={`${styles.inlineRow} ${styles.devicePairBody}`}>
        <div className={`${styles.deviceQr} ${trimmed ? "" : styles.deviceQrEmpty}`}>
          {trimmed && qrSvg
            ? <span dangerouslySetInnerHTML={{ __html: qrSvg }} />
            : <span className={styles.deviceQrHint}>Type a label to generate</span>}
        </div>
        <div
          className={`${styles.devicePairMeta} ${trimmed ? "" : styles.muted}`}
          aria-hidden={!trimmed}
        >
          <div className={styles.label}>Host</div>
          <div className={styles.mono}>
            {ready && payload.scope ? (
              <span className={scopeChipClass(payload.scope, styles)}>{payload.scope}</span>
            ) : null}
            {ready ? `${payload.host}:${payload.port}` : "…"}
          </div>
          <div className={styles.label} style={{ marginTop: "var(--space-3)" }}>
            Token
          </div>
          <div className={styles.mono}>
            {payload?.token ? `…${payload.token.slice(-8)}` : "…"}
          </div>
          <div className={styles.muted} style={{ marginTop: "var(--space-3)" }}>
            {scopeHint(payload?.scope)}
          </div>
        </div>
      </div>

      <div className={`${styles.inlineRow} ${styles.inlineRowNoWrap}`}>
        <code
          className={`${styles.mono} ${styles.muted} ${styles.truncate} ${styles.flexFill}`}
        >
          {desktopLink || "alpi://device?…"}
        </code>
        <Button
          size="sm"
          icon={<CopyIcon />}
          onClick={copyLink}
          disabled={!desktopLink}
          title="Copy pairing link"
          tooltipAlign="end"
        />
      </div>

      <DialogFooter
        onCancel={cancel}
        primaryLabel="Pair"
        primaryDisabled={!ready || !trimmed}
        primaryLoading={busy}
        onPrimary={pair}
      />
    </Modal>
  );
}

function scopeChipClass(scope, styles) {
  if (scope === "tailscale") return styles.scopeChipTailscale;
  if (scope === "lan") return styles.scopeChipLan;
  if (scope === "custom") return styles.scopeChipConfigured;
  return styles.scopeChip;
}

const SCOPE_HINTS = {
  tailscale:
    "Reachable on any network the other device is on. " +
    "Scan with the Alpi app on the other device, or copy the link below.",
  lan:
    "Same Wi-Fi only — the other device must share this network. " +
    "Switch to Tailscale in Settings → Devices → Network for remote pairing.",
  custom:
    "Using your custom advertised hostname. " +
    "Scan with the Alpi app on the other device, or copy the link below.",
  umbrel:
    "Reachable at the Umbrel hostname. " +
    "Scan with the Alpi app on the other device, or copy the link below.",
};

function scopeHint(scope) {
  return (
    SCOPE_HINTS[scope] ||
    "Scan with the Alpi app on the other device, or copy the link below."
  );
}
