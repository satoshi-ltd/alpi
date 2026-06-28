import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import Button from "../../../primitives/Button.jsx";
import Eyebrow from "../../../primitives/Eyebrow.jsx";
import Chip from "../../../primitives/Chip.jsx";
import Dropdown from "../../../primitives/Dropdown.jsx";
import Modal from "../../../primitives/Modal.jsx";
import Skeleton from "../../../primitives/Skeleton.jsx";
import { CopyIcon } from "../../../primitives/icons.jsx";
import { Checkbox, Diamond, Radio } from "../../../primitives/index.js";
import Tip from "../../../primitives/Tip.jsx";
import useAutoPosition from "../../../primitives/useAutoPosition.js";
import { useNotify } from "../../../primitives/Notification.jsx";
import { useDismissOnOutside } from "../../../hooks/useDismissOnOutside.js";
import { Row } from "../primitives.jsx";
import { Btn } from "../../../primitives/index.js";
import Field from "../../../primitives/Field.jsx";
import { ConfirmDelete, DialogFooter } from "../../../primitives/index.js";
import { formatLastSeen } from "../util.js";
import styles from "../Settings.module.css";
import { copyText } from "../../../lib/clipboard.js";

function cacheKey(connectionId) {
  return connectionId || "local";
}

const _devicesCache = new Map();

export function _clearDevicesCache() {
  _devicesCache.clear();
}

export function DevicesField({
  connectionId = null,
  role = null,
  onLoadingChange = null,
}) {
  const notify = useNotify();
  const key = cacheKey(connectionId);
  const [devices, setDevices] = useState(() => _devicesCache.get(key) ?? null);
  const [adding, setAdding] = useState(false);
  const [selectedTokenId, setSelectedTokenId] = useState(null);
  const [revokeTarget, setRevokeTarget] = useState(null);
  const detailAnchorRef = useRef(null);
  const requestRef = useRef(0);
  const canManage = role === "admin" || role == null;
  const connectionArg = useMemo(
    () => (connectionId ? { connectionId } : {}),
    [connectionId],
  );

  const reload = useCallback(async () => {
    const requestId = ++requestRef.current;
    onLoadingChange?.(true);
    try {
      const list = await invoke("devices_list", connectionArg);
      if (requestRef.current !== requestId) return;
      const next = Array.isArray(list) ? list : [];
      _devicesCache.set(key, next);
      setDevices(next);
    } catch (e) {
      if (requestRef.current !== requestId) return;
      setDevices(_devicesCache.get(key) ?? []);
      notify({ message: `devices: ${String(e)}`, variant: "error" });
    } finally {
      if (requestRef.current === requestId) onLoadingChange?.(false);
    }
  }, [connectionArg, key, notify, onLoadingChange]);

  useEffect(() => {
    setDevices(_devicesCache.get(key) ?? null);
    setAdding(false);
    setSelectedTokenId(null);
    setRevokeTarget(null);
    reload();
    return () => {
      requestRef.current += 1;
      onLoadingChange?.(false);
    };
  }, [key, reload, onLoadingChange]);

  async function revoke(tokenId) {
    try {
      await invoke("devices_revoke", { tokenId, ...connectionArg });
      notify({ message: "Device revoked", variant: "success" });
      setSelectedTokenId(null);
      await reload();
    } catch (e) {
      notify({ message: `revoke: ${String(e)}`, variant: "error", duration: 4000 });
    }
  }

  async function rename(tokenId, label) {
    try {
      await invoke("devices_rename", { tokenId, label, ...connectionArg });
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
                canManage={canManage}
                anchorRef={detailAnchorRef}
                onClose={() => setSelectedTokenId(null)}
                onRename={(label) => rename(selected.token_id, label)}
                onRequestRevoke={() => {
                  setRevokeTarget(selected);
                  setSelectedTokenId(null);
                }}
                onPromote={async () => {
                  try {
                    await invoke("devices_promote", { tokenId: selected.token_id, ...connectionArg });
                    notify({ message: "Device promoted to admin", variant: "success" });
                    setSelectedTokenId(null);
                    await reload();
                  } catch (e) {
                    notify({ message: `promote: ${String(e)}`, variant: "error" });
                  }
                }}
                onDemote={async () => {
                  try {
                    await invoke("devices_demote", { tokenId: selected.token_id, ...connectionArg });
                    notify({ message: "Device demoted to member", variant: "success" });
                    setSelectedTokenId(null);
                    await reload();
                  } catch (e) {
                    notify({ message: `demote: ${String(e)}`, variant: "error" });
                  }
                }}
              />
            )}
          </span>
        )}
        {canManage ? (
          <Button size="sm" onClick={() => setAdding(true)}>+ Add device</Button>
        ) : (
          <span className={styles.muted}>member device — admin-only</span>
        )}
      </span>
      {adding && (
        <PairDeviceModal
          connectionId={connectionId}
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

function DeviceDetailPopover({
  device,
  canManage,
  anchorRef,
  onClose,
  onRename,
  onRequestRevoke,
  onPromote,
  onDemote,
}) {
  const popoverRef = useRef(null);
  const [label, setLabel] = useState(device.label ?? "");
  const [busy, setBusy] = useState(false);
  const role = device.role ?? "member";
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
      className={`${pos.ready ? "anim-pop " : ""}${styles.popover}`}
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
        <Eyebrow as="label">label</Eyebrow>
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
        <Eyebrow as="label">role</Eyebrow>
        <span>
          <Chip size="sm">{role}</Chip>
          {canManage && (
            <Btn
              variant="ghost"
              size="sm"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  if (role === "admin") await onDemote?.();
                  else await onPromote?.();
                } finally { setBusy(false); }
              }}
            >
              {role === "admin" ? "Demote to member" : "Promote to admin"}
            </Btn>
          )}
        </span>
      </div>
      <div className={styles.field}>
        <Eyebrow as="label">token id</Eyebrow>
        <span className={styles.mono}>…{device.token_id}</span>
      </div>
      <div className={styles.field}>
        <Eyebrow as="label">last seen</Eyebrow>
        <span>{formatLastSeen(device.last_seen)}</span>
      </div>
      <div className={styles.popoverFooter}>
        <button
          type="button"
          className="alink danger"
          onClick={onRequestRevoke}
          disabled={busy || !canManage}
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

function PairDeviceModal({ connectionId, onClose, onPaired }) {
  const notify = useNotify();
  const connectionArg = useMemo(
    () => (connectionId ? { connectionId } : {}),
    [connectionId],
  );
  const [label, setLabel] = useState("");
  const [payload, setPayload] = useState(null);
  const [qrSvg, setQrSvg] = useState("");
  const [warn, setWarn] = useState(null);
  const [busy, setBusy] = useState(false);
  const [grantAdmin, setGrantAdmin] = useState(false);
  const [profiles, setProfiles] = useState([]);
  const [scope, setScope] = useState([]);
  const [scopeMode, setScopeMode] = useState("all");
  const [scopeQuery, setScopeQuery] = useState("");
  const generatedRef = useRef(false);
  const pendingTokenIdRef = useRef(null);
  const pairedRef = useRef(false);

  useEffect(() => {
    invoke("profile_summaries", connectionArg)
      .then((rows) => setProfiles(
        Array.isArray(rows)
          ? rows.filter((r) => r && r.name).map((r) => ({
              name: r.name,
              accent: r.accent || null,
            }))
          : [],
      ))
      .catch(() => setProfiles([]));
  }, [connectionArg]);

  const filteredProfiles = useMemo(() => {
    const q = scopeQuery.trim().toLowerCase();
    if (!q) return profiles;
    return profiles.filter((p) => p.name.toLowerCase().includes(q));
  }, [profiles, scopeQuery]);

  function toggleScope(name) {
    setScope((curr) =>
      curr.includes(name) ? curr.filter((x) => x !== name) : [...curr, name],
    );
  }

  function selectMode(mode) {
    setScopeMode(mode);
    if (mode === "all") setScope([]);
  }

  const effectiveScope = scopeMode === "restrict" ? scope : [];
  const scopeTriggerLabel = scopeMode === "all"
    ? "All profiles"
    : `Restrict · ${scope.length} of ${profiles.length}`;

  useEffect(() => {
    if (grantAdmin) {
      setScopeMode("all");
      setScope([]);
      setScopeQuery("");
    }
  }, [grantAdmin]);

  useEffect(() => () => {
    const tokenId = pendingTokenIdRef.current;
    if (tokenId && !pairedRef.current) {
      invoke("devices_revoke", { tokenId, ...connectionArg }).catch(() => {});
    }
  }, [connectionArg]);

  const scopeValid = grantAdmin || scopeMode === "all" || scope.length > 0;
  const canGenerate = (
    label.trim().length > 0
    && !busy
    && scopeValid
    && !payload
  );

  async function generate() {
    if (!canGenerate || generatedRef.current) return;
    generatedRef.current = true;
    setBusy(true);
    try {
      const p = await invoke("devices_generate", {
        label: label.trim(),
        role: grantAdmin ? "admin" : "member",
        profiles: grantAdmin ? [] : (scopeMode === "restrict" ? scope : []),
        ...connectionArg,
      });
      const token = p?.token || "";
      const tokenId = token.slice(-8);
      pendingTokenIdRef.current = tokenId;
      setPayload({ ...p, token_id: tokenId });
    } catch (e) {
      generatedRef.current = false;
      const msg = String(e);
      if (msg.includes("no-advertised-host")) {
        const hint = msg.split("—").slice(1).join("—").trim();
        setWarn(
          "Cannot pair — no Tailscale or LAN address detected. " +
          (hint ? `Detected: ${hint}. ` : "") +
          "Connect to Wi-Fi / Ethernet, install Tailscale, " +
          "or set network.host in config.yaml.",
        );
      } else {
        notify({ message: `generate: ${msg}`, variant: "error", duration: 4000 });
      }
    } finally {
      setBusy(false);
    }
  }

  const trimmed = label.trim();
  const ready = Boolean(payload?.host && payload?.port);

  const desktopLink = useMemo(() => {
    if (!ready) return "";
    const params = new URLSearchParams({
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
      i: payload.host, p: payload.port, n: trimmed, t: payload.token,
    });
    import("qrcode").then(({ default: QRCode }) =>
      QRCode.toString(qrPayload, { type: "svg", margin: 1, errorCorrectionLevel: "L" })
    ).then((svg) => { if (!cancelled) setQrSvg(svg); })
     .catch((e) => notify({ message: `QR: ${String(e)}`, variant: "error" }));
    return () => { cancelled = true; };
  }, [ready, payload, trimmed, notify]);

  async function copyLink() {
    if (await copyText(desktopLink)) notify({ message: "Pairing link copied", variant: "success" });
    else notify({ message: "Copy failed", variant: "error" });
  }

  async function pair() {
    if (!payload || busy) return;
    pairedRef.current = true;
    const roleSuffix = grantAdmin ? " (admin)" : "";
    notify({ message: `Device "${trimmed}"${roleSuffix} paired`, variant: "success" });
    onPaired?.();
  }

  async function cancel() {
    if (payload?.token_id) {
      try {
        const list = await invoke("devices_list", connectionArg);
        const row = (Array.isArray(list) ? list : [])
          .find((d) => d && d.token_id === payload.token_id);
        if (row && row.last_seen) {
          pairedRef.current = true;
          notify({
            message: `Device "${row.label || trimmed}" paired`,
            variant: "success",
          });
          onPaired?.();
          return;
        }
      } catch {
        // list rpc failed — fall through to revoke; on revoke failure unmount cleanup retries.
      }
      try {
        await invoke("devices_revoke", { tokenId: payload.token_id, ...connectionArg });
        pairedRef.current = true;
      } catch {
        // leave pairedRef false so unmount cleanup retries the revoke.
      }
    }
    onClose?.();
  }

  if (warn) {
    return (
      <Modal title="Pair a new device" onClose={onClose} width="var(--modal-md)">
        <div className={styles.warn}>{warn}</div>
        <DialogFooter onCancel={onClose} cancelLabel="Close" />
      </Modal>
    );
  }

  return (
    <Modal title="Pair a new device" onClose={cancel} width="var(--modal-md)">
      <div className={styles.field}>
        <Eyebrow as="label">Label</Eyebrow>
        <Field
          className={`${styles.input} ${styles.inputFull}`}
          type="text"
          value={label}
          autoFocus
          onChange={(e) => setLabel(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !payload) generate(); }}
          placeholder="MacBook Pro · Phone · …"
          spellCheck={false}
          disabled={busy || Boolean(payload)}
        />
      </div>

      <label className={styles.adminBanner}>
        <input
          type="checkbox"
          className={styles.visuallyHidden}
          checked={grantAdmin}
          onChange={(e) => setGrantAdmin(e.target.checked)}
          disabled={busy || Boolean(payload)}
        />
        <Checkbox on={grantAdmin} />
        <span className={styles.adminBannerBody}>
          <span className={styles.adminBannerTitle}>
            Grant admin access
            <Tip
              side="up"
              text="Member can still chat and post to workgroups; only host setup is gated. Not a sandbox on the agent's tools."
            >
              <span className={styles.helpDot} aria-label="more info">?</span>
            </Tip>
          </span>
          <span className={styles.adminBannerCaption}>
            Can manage profiles, devices. Sees all profiles.
          </span>
        </span>
      </label>

      {!grantAdmin && profiles.length > 0 && payload && (
        <div className={styles.field}>
          <Eyebrow as="label">Profiles access</Eyebrow>
          <div className={styles.lockedValue}>{scopeTriggerLabel}</div>
        </div>
      )}
      {!grantAdmin && profiles.length > 0 && !payload && (
        <div className={styles.field}>
          <Eyebrow as="label">Profiles access</Eyebrow>
          <Dropdown
            trigger={{ label: scopeTriggerLabel }}
            direction="down"
            align="left"
            variant="field"
            fullWidth
          >
            {() => (
              <>
                <Dropdown.Row
                  active={scopeMode === "all"}
                  leading={<Radio on={scopeMode === "all"} />}
                  trailing={
                    <span className={styles.muted}>
                      default · admin sees everything
                    </span>
                  }
                  onClick={() => selectMode("all")}
                >
                  All profiles
                </Dropdown.Row>
                <Dropdown.Row
                  active={scopeMode === "restrict"}
                  leading={<Radio on={scopeMode === "restrict"} />}
                  trailing={
                    <span className={styles.muted}>
                      pick specific profiles below
                    </span>
                  }
                  onClick={() => selectMode("restrict")}
                >
                  Restrict to…
                </Dropdown.Row>
                {scopeMode === "restrict" && (
                  <>
                    <div className={styles.scopeFilter}>
                      <Field
                        className={styles.input}
                        placeholder="filter…"
                        value={scopeQuery}
                        onChange={(e) => setScopeQuery(e.target.value)}
                      />
                    </div>
                    {filteredProfiles.map((p) => (
                      <Dropdown.Row
                        key={p.name}
                        leading={<Checkbox on={scope.includes(p.name)} />}
                        onClick={() => toggleScope(p.name)}
                      >
                        <span className={styles.scopeRowName}>
                          <Diamond color={p.accent || "var(--accent)"} />
                          <span className={styles.mono}>@{p.name}</span>
                        </span>
                      </Dropdown.Row>
                    ))}
                    {filteredProfiles.length === 0 && (
                      <Dropdown.Empty>no matches</Dropdown.Empty>
                    )}
                  </>
                )}
              </>
            )}
          </Dropdown>
        </div>
      )}

      {payload && (
        <>
          <div className={`${styles.inlineRow} ${styles.devicePairBody}`}>
            <div className={styles.deviceQr}>
              {qrSvg ? <span dangerouslySetInnerHTML={{ __html: qrSvg }} /> : null}
            </div>
            <div className={styles.devicePairMeta}>
              <Eyebrow as="div">Host</Eyebrow>
              <div className={styles.mono}>
                {payload.scope ? (
                  <span className={scopeChipClass(payload.scope, styles)}>{payload.scope}</span>
                ) : null}
                {ready ? `${payload.host}:${payload.port}` : "…"}
              </div>
              <Eyebrow as="div" className={styles.devicePairMetaSpacer}>
                Token
              </Eyebrow>
              <div className={styles.mono}>
                {payload.token ? `…${payload.token.slice(-8)}` : "…"}
              </div>
              <div className={`${styles.muted} ${styles.devicePairMetaSpacer}`}>
                {scopeHint(payload.scope)}
              </div>
            </div>
          </div>

          <div className={`${styles.inlineRow} ${styles.inlineRowNoWrap} ${styles.linkPill}`}>
            <span
              className={`${styles.mono} ${styles.muted} ${styles.truncate} ${styles.flexFill}`}
            >
              {desktopLink}
            </span>
            <Button
              size="sm"
              icon={<CopyIcon />}
              onClick={copyLink}
              disabled={!desktopLink}
              title="Copy pairing link"
              tooltipAlign="end"
            />
          </div>
        </>
      )}

      {payload ? (
        <DialogFooter
          onCancel={cancel}
          primaryLabel="Pair"
          primaryDisabled={!ready}
          primaryLoading={busy}
          onPrimary={pair}
        />
      ) : (
        <DialogFooter
          onCancel={cancel}
          primaryLabel="Generate pairing code"
          primaryDisabled={!canGenerate}
          primaryLoading={busy}
          onPrimary={generate}
        />
      )}
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
