import { useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import Button from "../../../primitives/Button.jsx";
import Chip from "../../../primitives/Chip.jsx";
import Field from "../../../primitives/Field.jsx";
import { useNotify } from "../../../primitives/Notification.jsx";
import { useDismissOnOutside } from "../../../hooks/useDismissOnOutside.js";
import { formatTcpLabel } from "../util.js";
import styles from "../Settings.module.css";

export function TcpPortField({ profile, onSaved }) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const notify = useNotify();
  const [host, setHost] = useState(profile.tcp_host || "127.0.0.1");
  const [port, setPort] = useState(
    profile.tcp_port ? String(profile.tcp_port) : "",
  );
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setHost(profile.tcp_host || "127.0.0.1");
    setPort(profile.tcp_port ? String(profile.tcp_port) : "");
  }, [profile.tcp_host, profile.tcp_port]);

  useDismissOnOutside({ open, onClose: () => setOpen(false), wrapRef });

  const portTrim = port.trim();
  const portValid = portTrim === "" || /^[0-9]+$/.test(portTrim);
  const portNum = portTrim === "" ? 0 : Number(portTrim);
  const portInRange = portTrim === "" || (portNum >= 1 && portNum <= 65535);
  const dirty =
    host.trim() !== (profile.tcp_host || "127.0.0.1") ||
    portTrim !== (profile.tcp_port ? String(profile.tcp_port) : "");

  const [portFree, setPortFree] = useState(null);
  useEffect(() => {
    if (!open || !portInRange || portTrim === "") {
      setPortFree(null);
      return;
    }
    if (portNum === profile.tcp_port) {
      setPortFree(true);
      return;
    }
    let cancelled = false;
    const id = setTimeout(() => {
      invoke("port_available", {
        host: host.trim() || "127.0.0.1",
        port: portNum,
      })
        .then((ok) => { if (!cancelled) setPortFree(ok); })
        .catch(() => { if (!cancelled) setPortFree(null); });
    }, 350);
    return () => { cancelled = true; clearTimeout(id); };
  }, [open, portTrim, portNum, host, portInRange, profile.tcp_port]);

  async function save() {
    if (!portValid || !portInRange || saving) return;
    if (portTrim !== "" && portFree === false) return;
    setSaving(true);
    try {
      if (portTrim === "") {
        await invoke("unset_config_field", { profile: profile.name, key: "alp.tcp_port" });
        await invoke("unset_config_field", { profile: profile.name, key: "alp.tcp_host" });
      } else {
        await invoke("set_config_field", {
          profile: profile.name,
          key: "alp.tcp_host",
          value: host.trim() || "127.0.0.1",
        });
        await invoke("set_config_field", {
          profile: profile.name,
          key: "alp.tcp_port",
          value: portTrim,
        });
      }
      invoke("daemon_restart").catch(() => {});
      await onSaved?.();
      notify({
        message: portTrim
          ? `TCP listener ${host.trim()}:${portTrim} · daemon restarting`
          : "TCP listener disabled · daemon restarting",
        variant: "success",
        duration: 3000,
      });
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
        state={profile.tcp_port ? "on" : "off"}
        onClick={() => setOpen((o) => !o)}
        tooltip={
          <>
            <div>ALP TCP listener</div>
            <div className={styles.tooltipStatus}>
              {profile.tcp_port
                ? `${profile.tcp_host || "127.0.0.1"}:${profile.tcp_port} · click to edit`
                : "disabled · click to enable"}
            </div>
          </>
        }
      >
        {profile.tcp_port
          ? formatTcpLabel(profile.tcp_host, profile.tcp_port)
          : "tcp off"}
      </Chip>
      {open && (
        <div className={styles.popover}>
          <div className={styles.field}>
            <label className={styles.label}>host</label>
            <Field
              className={styles.input}
              value={host}
              onChange={(e) => setHost(e.target.value)}
              placeholder="127.0.0.1"
              spellCheck={false}
            />
          </div>
          <div className={styles.field}>
            <label className={styles.label}>port</label>
            <Field
              className={styles.input}
              value={port}
              onChange={(e) => setPort(e.target.value)}
              placeholder="empty to disable"
              spellCheck={false}
            />
          </div>
          {host.trim() === "0.0.0.0" && (
            <div className={styles.warn}>
              0.0.0.0 exposes the port to all interfaces. Use only behind a VPN.
            </div>
          )}
          {!portInRange && (
            <div className={styles.warn}>Port must be 1-65535.</div>
          )}
          {portInRange && portTrim !== "" && portFree === false && (
            <div className={styles.warn}>
              Port {portTrim} is in use on {host.trim() || "127.0.0.1"}.
            </div>
          )}
          <div className={styles.actions}>
            <Button
              size="sm"
              onClick={save}
              disabled={
                !dirty ||
                !portInRange ||
                (portTrim !== "" && portFree === false)
              }
              loading={saving}
              variant="primary"
            >
              Save
            </Button>
          </div>
        </div>
      )}
    </span>
  );
}
