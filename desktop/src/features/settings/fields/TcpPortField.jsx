import { useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import Button from "../../../primitives/Button.jsx";
import Eyebrow from "../../../primitives/Eyebrow.jsx";
import Chip from "../../../primitives/Chip.jsx";
import Field from "../../../primitives/Field.jsx";
import { useNotify } from "../../../primitives/Notification.jsx";
import { useDismissOnOutside } from "../../../hooks/useDismissOnOutside.js";
import { formatTcpLabel } from "../util.js";
import styles from "../Settings.module.css";

const DEFAULT_ALP_PORT = 7423;

// ALP peer TCP listener — always-on; only the port is editable here.
export function TcpPortField({ profile, onSaved }) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const notify = useNotify();
  const effective = profile.tcp_port || DEFAULT_ALP_PORT;
  const [port, setPort] = useState(String(effective));
  const [saving, setSaving] = useState(false);

  const endpoint = formatTcpLabel(profile.advertise_host, effective);

  useEffect(() => { setPort(String(profile.tcp_port || DEFAULT_ALP_PORT)); }, [profile.tcp_port]);
  useDismissOnOutside({ open, onClose: () => setOpen(false), wrapRef });

  const portTrim = port.trim();
  const portNum = Number(portTrim);
  const portValid = /^[0-9]+$/.test(portTrim) && portNum >= 1 && portNum <= 65535;
  const dirty = portValid && portNum !== effective;

  const [portFree, setPortFree] = useState(null);
  useEffect(() => {
    if (!open || !portValid || portNum === profile.tcp_port) { setPortFree(null); return; }
    let cancelled = false;
    const id = setTimeout(() => {
      invoke("port_available", { host: (profile.advertise_host || "").trim() || "0.0.0.0", port: portNum })
        .then((ok) => { if (!cancelled) setPortFree(ok); })
        .catch(() => { if (!cancelled) setPortFree(null); });
    }, 350);
    return () => { cancelled = true; clearTimeout(id); };
  }, [open, portTrim, portNum, portValid, profile.tcp_port, profile.advertise_host]);

  async function save() {
    if (!dirty || saving || (portFree === false)) return;
    setSaving(true);
    try {
      if (portNum === DEFAULT_ALP_PORT) {
        await invoke("unset_config_field", { profile: profile.name, key: "alp.tcp_port" });
      } else {
        await invoke("set_config_field", { profile: profile.name, key: "alp.tcp_port", value: String(portNum) });
      }
      // The daemon rebinds the ALP listener on its next config rescan (≤5s) — host plane stays up.
      await onSaved?.();
      notify({ message: `ALP TCP port ${portNum} · applying`, variant: "success", duration: 3000 });
      setOpen(false);
    } catch (e) {
      notify({ message: `tcp: ${String(e)}`, variant: "error", duration: 4000 });
    } finally {
      setSaving(false);
    }
  }

  return (
    <span ref={wrapRef} className={styles.popoverAnchor}>
      <Chip
        state="on"
        onClick={() => setOpen((o) => !o)}
        tooltip={
          <>
            <div>ALP peer TCP listener</div>
            <div className={styles.tooltipStatus}>{endpoint} · click to edit port</div>
          </>
        }
      >
        {endpoint}
      </Chip>
      {open && (
        <div className={styles.popover}>
          <div className={styles.field}>
            <Eyebrow as="label">tcp port</Eyebrow>
            <Field
              className={styles.input}
              value={port}
              onChange={(e) => setPort(e.target.value)}
              placeholder={String(DEFAULT_ALP_PORT)}
              spellCheck={false}
            />
          </div>
          {!portValid && <div className={styles.warn}>Port must be 1-65535.</div>}
          {portValid && portFree === false && (
            <div className={styles.warn}>Port {portNum} is in use.</div>
          )}
          <div className={styles.actions}>
            <Button size="sm" variant="primary" onClick={save} disabled={!dirty || portFree === false} loading={saving}>
              Save
            </Button>
          </div>
        </div>
      )}
    </span>
  );
}
