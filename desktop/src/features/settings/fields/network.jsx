import { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import Button from "../../../primitives/Button.jsx";
import Chip from "../../../primitives/Chip.jsx";
import Field from "../../../primitives/Field.jsx";
import { useNotify } from "../../../primitives/Notification.jsx";
import { useDismissOnOutside } from "../../../hooks/useDismissOnOutside.js";
import { Row } from "../primitives.jsx";
import styles from "../Settings.module.css";

const MODES = [
  { value: "auto",      label: "Auto",      hint: "Tailscale if available, LAN otherwise" },
  { value: "tailscale", label: "Tailscale", hint: "Reachable on any network · recommended" },
  { value: "lan",       label: "LAN",       hint: "Same Wi-Fi only" },
  { value: "custom",    label: "Custom",    hint: "Hostname, MagicDNS, or VPN IP" },
];

function deriveMode(status) {
  if (!status) return "auto";
  const configured = status.candidates?.configured;
  if (!configured) return "auto";
  if (configured === status.candidates?.tailscale) return "tailscale";
  if (configured === status.candidates?.lan) return "lan";
  return "custom";
}

function resolveHost(mode, status, customInput) {
  if (mode === "auto") return "";
  if (mode === "tailscale") return status?.candidates?.tailscale || "";
  if (mode === "lan") return status?.candidates?.lan || "";
  if (mode === "custom") return customInput.trim();
  return "";
}

function modeAvailable(mode, status) {
  if (mode === "auto" || mode === "custom") return true;
  return Boolean(status?.candidates?.[mode]);
}

export function NetworkField() {
  const notify = useNotify();
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const [status, setStatus] = useState(null);
  const [mode, setMode] = useState("auto");
  const [customHost, setCustomHost] = useState("");
  const [deviceName, setDeviceName] = useState("");
  const [saving, setSaving] = useState(false);

  useDismissOnOutside({ open, onClose: () => setOpen(false), wrapRef });

  const refresh = useCallback(async () => {
    try {
      const s = await invoke("network_status");
      setStatus(s);
      const m = deriveMode(s);
      setMode(m);
      const configured = s?.candidates?.configured || "";
      setCustomHost(m === "custom" ? configured : "");
      setDeviceName(s?.device_name || "");
    } catch (e) {
      notify({ message: `network: ${String(e)}`, variant: "error" });
    }
  }, [notify]);

  useEffect(() => { refresh(); }, [refresh]);

  const chipLabel = (() => {
    if (!status) return "loading…";
    const scope = status.scope_in_use;
    const host = status.host_in_use;
    if (!scope || !host) return "no network";
    return `${scope} · ${host}`;
  })();

  const chipState = status?.host_in_use ? "on" : "off";

  const dirty = (() => {
    if (!status) return false;
    const nextHost = resolveHost(mode, status, customHost);
    const currentHost = status.candidates?.configured || "";
    if (nextHost !== currentHost) return true;
    if (deviceName !== (status.device_name || "")) return true;
    return false;
  })();

  const customValid = mode !== "custom" || customHost.trim().length > 0;
  const targetAvailable = modeAvailable(mode, status);

  async function save() {
    if (!dirty || saving || !customValid || !targetAvailable) return;
    setSaving(true);
    try {
      const host = resolveHost(mode, status, customHost);
      await invoke("network_set_advertised", { host, deviceName });
      try {
        await invoke("network_restart_host_server");
      } catch (e) {
        notify({
          message: `saved; restart failed: ${String(e)}`,
          variant: "warn",
          duration: 4500,
        });
        await refresh();
        setOpen(false);
        return;
      }
      notify({
        message: "Pairing endpoint updated · daemon restarting",
        variant: "success",
        duration: 3000,
      });
      await refresh();
      setOpen(false);
    } catch (e) {
      notify({
        message: `network: ${String(e)}`,
        variant: "error",
        duration: 4500,
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Row label="pairing">
      <span ref={wrapRef} className={styles.popoverAnchor}>
        <Chip
          state={chipState}
          onClick={() => setOpen((o) => !o)}
          tooltip={
            <>
              <div>Pairing endpoint</div>
              <div className={styles.tooltipStatus}>
                {chipLabel} · click to edit
              </div>
            </>
          }
        >
          {chipLabel}
        </Chip>
        {open && (
          <div className={`${styles.popover} ${styles.networkPopover}`}>
            <div className={styles.field}>
              <label className={styles.label}>advertised host</label>
              <div className={styles.modeGrid}>
                {MODES.map((m) => {
                  const available = modeAvailable(m.value, status);
                  return (
                    <button
                      key={m.value}
                      type="button"
                      className={`${styles.modeOption} ${mode === m.value ? styles.modeOptionActive : ""}`}
                      onClick={() => available && setMode(m.value)}
                      disabled={!available}
                      title={available ? m.hint : `${m.hint} · not detected`}
                    >
                      <span className={styles.modeOptionLabel}>{m.label}</span>
                      <span className={styles.modeOptionHint}>
                        {m.value === "tailscale" && status?.candidates?.tailscale
                          ? status.candidates.tailscale
                          : m.value === "lan" && status?.candidates?.lan
                          ? status.candidates.lan
                          : m.hint}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            {mode === "custom" && (
              <div className={styles.field}>
                <label className={styles.label}>host</label>
                <Field
                  className={styles.input}
                  value={customHost}
                  onChange={(e) => setCustomHost(e.target.value)}
                  placeholder="myhost.local"
                  spellCheck={false}
                />
                <div className={styles.muted}>
                  Hostnames, MagicDNS names, or VPN IPs.
                  Public IPs are rejected (token would leak).
                </div>
              </div>
            )}

            <div className={styles.field}>
              <label className={styles.label}>pairing name</label>
              <Field
                className={styles.input}
                value={deviceName}
                onChange={(e) => setDeviceName(e.target.value)}
                placeholder="auto-detect from hostname"
                spellCheck={false}
              />
            </div>

            {!targetAvailable && (
              <div className={styles.warn}>
                {mode} is not detected on this machine. Pick another mode or
                switch to Custom.
              </div>
            )}

            <div className={styles.actions}>
              <Button
                size="sm"
                variant="primary"
                onClick={save}
                disabled={!dirty || !customValid || !targetAvailable}
                loading={saving}
              >
                Save and restart
              </Button>
            </div>
          </div>
        )}
      </span>
    </Row>
  );
}
