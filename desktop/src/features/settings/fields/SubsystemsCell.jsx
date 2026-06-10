import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import Chip from "../../../primitives/Chip.jsx";
import { useNotify } from "../../../primitives/Notification.jsx";
import { SUBSYSTEMS, SUBSYSTEM_DESC } from "../util.js";
import styles from "../Settings.module.css";

export function SubsystemsCell({ profile, onSaved }) {
  const notify = useNotify();
  const [busy, setBusy] = useState(null);
  const subs = profile.subsystems ?? {
    gateway: true,
    schedule: true,
    alp: true,
    workgroups: true,
  };
  async function toggle(key) {
    if (busy) return;
    const next = !subs[key];
    setBusy(key);
    try {
      await invoke("set_config_field", {
        profile: profile.name,
        key: `service.${key}`,
        value: String(next),
      });
      // The daemon applies subsystem toggles on its next config rescan (≤5s) — no restart.
      await onSaved?.();
      notify({
        message: profile.running
          ? `${key} ${next ? "enabled" : "disabled"} · applying`
          : `${key} ${next ? "enabled" : "disabled"}`,
        variant: "success",
        duration: profile.running ? 3000 : 2400,
      });
    } catch (e) {
      notify({ message: `${key}: ${String(e)}`, variant: "error", duration: 4000 });
    } finally {
      setBusy(null);
    }
  }
  return (
    <span className={styles.gatewayChips}>
      {SUBSYSTEMS.map((k) => {
        const enabled = subs[k];
        const state = !profile.running ? "off" : enabled ? "on" : "error";
        const desc = SUBSYSTEM_DESC[k];
        const status = !profile.running
          ? "daemon stopped"
          : enabled
            ? "running · click to disable"
            : "disabled · click to enable";
        const tooltip = (
          <>
            <div>{desc}</div>
            <div className={styles.tooltipStatus}>{status}</div>
          </>
        );
        return (
          <Chip
            key={k}
            state={state}
            tooltip={tooltip}
            onClick={busy ? undefined : () => toggle(k)}
          >
            {k}
          </Chip>
        );
      })}
    </span>
  );
}
