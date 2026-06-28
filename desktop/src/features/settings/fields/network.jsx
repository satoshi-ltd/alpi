import { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import Button from "../../../primitives/Button.jsx";
import Eyebrow from "../../../primitives/Eyebrow.jsx";
import Chip from "../../../primitives/Chip.jsx";
import Field from "../../../primitives/Field.jsx";
import { useNotify } from "../../../primitives/Notification.jsx";
import { useDismissOnOutside } from "../../../hooks/useDismissOnOutside.js";
import { Row } from "../primitives.jsx";
import { scopeLabel } from "../util.js";
import styles from "../Settings.module.css";

// Classify the typed address for the tag; warn only on the risky (public) case.
function detectTag(host, status) {
  const h = (host || "").trim();
  if (!h) {
    const auto = status?.candidates?.tailscale || status?.candidates?.lan || null;
    return { kind: "auto", note: auto ? `auto · ${auto}` : "auto-detect (none found yet)" };
  }
  const ip = h.replace(/:\d+$/, "");
  const m = ip.match(/^(\d+)\.(\d+)\.\d+\.\d+$/);
  if (m) {
    const a = Number(m[1]);
    const b = Number(m[2]);
    if (a === 100 && b >= 64 && b <= 127) return { kind: "tailscale", note: "Tailscale" };
    if (a === 10 || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168))
      return { kind: "lan", note: "private LAN" };
    if (a === 127) return { kind: "loopback", note: "loopback — devices can't reach this", warn: true };
    return {
      kind: "public",
      note: "public IP — not settable here; edit config.yaml (network.host + host.allow_public_bind)",
      warn: true,
    };
  }
  return {
    kind: "hostname",
    note: "hostname — binds all interfaces; pairing token + firewall are the access control",
    warn: true,
  };
}

// Service section — the one shared accessible address (network.host).
export function NetworkAddressField({ onLoadingChange = null }) {
  const notify = useNotify();
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const [status, setStatus] = useState(null);
  const [host, setHost] = useState("");
  const [saving, setSaving] = useState(false);

  useDismissOnOutside({ open, onClose: () => setOpen(false), wrapRef });

  const refresh = useCallback(async () => {
    onLoadingChange?.(true);
    try {
      const s = await invoke("network_status");
      setStatus(s);
      setHost(s?.candidates?.configured || "");
    } catch (e) {
      notify({ message: `network: ${String(e)}`, variant: "error" });
    } finally {
      onLoadingChange?.(false);
    }
  }, [notify, onLoadingChange]);

  useEffect(() => { refresh(); }, [refresh]);

  const chipLabel = (() => {
    if (!status) return "loading…";
    const scope = status.scope_in_use;
    const h = status.host_in_use;
    if (!scope || !h) return "no address";
    return `${scope}:${h}`;
  })();
  const tag = detectTag(host, status);
  const dirty = status ? host.trim() !== (status.candidates?.configured || "") : false;

  async function save() {
    if (!dirty || saving) return;
    setSaving(true);
    try {
      await invoke("network_set_advertised", { host: host.trim() });
      try {
        await invoke("network_restart_host_server");
      } catch (e) {
        notify({ message: `saved; restart failed: ${String(e)}`, variant: "warn", duration: 4500 });
        await refresh();
        setOpen(false);
        return;
      }
      notify({ message: "Accessible address updated · daemon restarting", variant: "success", duration: 3000 });
      await refresh();
      setOpen(false);
    } catch (e) {
      notify({ message: `network: ${String(e)}`, variant: "error", duration: 4500 });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Row label="address">
      <span ref={wrapRef} className={styles.popoverAnchor}>
        <Chip
          state={status?.host_in_use ? "on" : "off"}
          onClick={() => setOpen((o) => !o)}
          tooltip={
            <>
              <div>Accessible address — shared by pairing + ALP</div>
              <div className={styles.tooltipStatus}>{chipLabel} · click to edit</div>
            </>
          }
        >
          {chipLabel}
        </Chip>
        {open && (
          <div className={`${styles.popover} ${styles.networkPopover}`}>
            <div className={styles.field}>
              <Eyebrow as="label">address</Eyebrow>
              <Field
                className={styles.input}
                value={host}
                onChange={(e) => setHost(e.target.value)}
                placeholder="empty = auto · or 100.x / 192.168.x / host.internal"
                spellCheck={false}
              />
              {tag.warn && <div className={styles.warn}>{tag.note}</div>}
            </div>
            <div className={styles.actions}>
              <Button size="sm" variant="primary" onClick={save} disabled={!dirty} loading={saving}>
                Save and restart
              </Button>
            </div>
          </div>
        )}
      </span>
    </Row>
  );
}

// Devices section — the device-pairing port (always on; only the port edits here).
export function HostPortField({ profile, onSaved, onLoadingChange = null }) {
  const notify = useNotify();
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const [status, setStatus] = useState(null);
  const [port, setPort] = useState("");
  const [saving, setSaving] = useState(false);

  useDismissOnOutside({ open, onClose: () => setOpen(false), wrapRef });

  const refresh = useCallback(async () => {
    onLoadingChange?.(true);
    try {
      const s = await invoke("network_status");
      setStatus(s);
      setPort(String(s?.port || 49200));
    } catch (e) {
      notify({ message: `network: ${String(e)}`, variant: "error" });
    } finally {
      onLoadingChange?.(false);
    }
  }, [notify, onLoadingChange]);
  useEffect(() => { refresh(); }, [refresh]);

  const current = status?.port || 49200;
  const portNum = Number(port.trim());
  const portValid = /^[0-9]+$/.test(port.trim()) && portNum >= 1 && portNum <= 65535;
  const dirty = portValid && portNum !== current;

  const [portFree, setPortFree] = useState(null);
  useEffect(() => {
    if (!open || !portValid || portNum === current) { setPortFree(null); return; }
    let cancelled = false;
    const id = setTimeout(() => {
      invoke("port_available", { host: (profile.advertise_host || "").trim() || "0.0.0.0", port: portNum })
        .then((ok) => { if (!cancelled) setPortFree(ok); })
        .catch(() => { if (!cancelled) setPortFree(null); });
    }, 350);
    return () => { cancelled = true; clearTimeout(id); };
  }, [open, port, portNum, portValid, current, profile.advertise_host]);

  async function save() {
    if (!dirty || saving || portFree === false) return;
    setSaving(true);
    try {
      if (portNum === 49200) {
        await invoke("unset_config_field", { profile: profile.name, key: "host.tcp_port" });
      } else {
        await invoke("set_config_field", { profile: profile.name, key: "host.tcp_port", value: String(portNum) });
      }
      try {
        await invoke("network_restart_host_server");
      } catch (e) {
        await onSaved?.();
        await refresh();
        notify({ message: `Port ${portNum} saved · restart failed: ${String(e)}`, variant: "warn", duration: 4500 });
        setOpen(false);
        return;
      }
      await onSaved?.();
      notify({ message: `Pairing port ${portNum} · daemon restarting`, variant: "success", duration: 3000 });
      await refresh();
      setOpen(false);
    } catch (e) {
      notify({ message: `network: ${String(e)}`, variant: "error", duration: 4500 });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Row label="pairing port">
      <span ref={wrapRef} className={styles.popoverAnchor}>
        <Chip state="on" onClick={() => setOpen((o) => !o)} tooltip="Control-plane port · click to edit">
          {scopeLabel(profile.advertise_host)}:{current}
        </Chip>
        {open && (
          <div className={styles.popover}>
            <div className={styles.field}>
              <Eyebrow as="label">tcp port</Eyebrow>
              <Field
                className={styles.input}
                value={port}
                onChange={(e) => setPort(e.target.value)}
                placeholder="49200"
                spellCheck={false}
              />
              {!portValid && <div className={styles.warn}>Port must be 1-65535.</div>}
              {portValid && portFree === false && (
                <div className={styles.warn}>Port {portNum} is in use.</div>
              )}
            </div>
            <div className={styles.actions}>
              <Button size="sm" variant="primary" onClick={save} disabled={!dirty || portFree === false} loading={saving}>
                Save and restart
              </Button>
            </div>
          </div>
        )}
      </span>
    </Row>
  );
}

// Devices section — the pairing label shown to new devices.
export function PairingNameField({ onLoadingChange = null }) {
  const notify = useNotify();
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const [status, setStatus] = useState(null);
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);

  useDismissOnOutside({ open, onClose: () => setOpen(false), wrapRef });

  const refresh = useCallback(async () => {
    onLoadingChange?.(true);
    try {
      const s = await invoke("network_status");
      setStatus(s);
      setName(s?.device_name || "");
    } catch (e) {
      notify({ message: `network: ${String(e)}`, variant: "error" });
    } finally {
      onLoadingChange?.(false);
    }
  }, [notify, onLoadingChange]);

  useEffect(() => { refresh(); }, [refresh]);

  const current = status?.device_name || "";
  const dirty = status ? name.trim() !== current : false;

  async function save() {
    if (!dirty || saving) return;
    setSaving(true);
    try {
      await invoke("network_set_advertised", { deviceName: name.trim() });
      notify({ message: "Pairing name updated", variant: "success", duration: 2500 });
      await refresh();
      setOpen(false);
    } catch (e) {
      notify({ message: `network: ${String(e)}`, variant: "error", duration: 4500 });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Row label="pairing name">
      <span ref={wrapRef} className={styles.popoverAnchor}>
        <Chip state="on" onClick={() => setOpen((o) => !o)} tooltip="Label shown to new devices · click to edit">
          {current || "auto"}
        </Chip>
        {open && (
          <div className={styles.popover}>
            <div className={styles.field}>
              <Eyebrow as="label">pairing name</Eyebrow>
              <Field
                className={styles.input}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="auto-detect from hostname"
                spellCheck={false}
              />
            </div>
            <div className={styles.actions}>
              <Button size="sm" variant="primary" onClick={save} disabled={!dirty} loading={saving}>
                Save
              </Button>
            </div>
          </div>
        )}
      </span>
    </Row>
  );
}
