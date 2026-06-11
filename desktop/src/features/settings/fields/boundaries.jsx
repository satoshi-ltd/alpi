import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import Button from "../../../primitives/Button.jsx";
import Chip from "../../../primitives/Chip.jsx";
import { useNotify } from "../../../primitives/Notification.jsx";
import { Row } from "../primitives.jsx";
import { AccentPicker } from "../../../primitives/SettingsLayout.jsx";
import Field from "../../../primitives/Field.jsx";
import { BudgetEdit } from "../../../primitives/index.js";
import styles from "../Settings.module.css";

export function BudgetField({ profile, onSaved }) {
  const notify = useNotify();
  const usd = profile.budget_daily_usd;
  const value = usd != null ? usd : "";

  async function save({ value: v }) {
    try {
      if (v == null || v === "") {
        await invoke("unset_config_field", { profile: profile.name, key: "budget.daily_usd" });
      } else {
        await invoke("set_config_field", { profile: profile.name, key: "budget.daily_usd", value: String(v) });
      }
      await onSaved?.();
    } catch (e) {
      notify({ message: `budget: ${String(e)}`, variant: "error", duration: 4000 });
      throw e;
    }
  }

  const triggerLabel = usd != null ? `$${usd.toFixed(2)}/day` : "unlimited";

  return (
    <Row label="budget">
      <BudgetEdit value={value} triggerLabel={triggerLabel} onSave={save} />
    </Row>
  );
}

export function WorkspaceField({ value, onChange, isLocal = true }) {
  async function browse() {
    try {
      const path = await invoke("pick_folder");
      if (path) onChange(path);
    } catch {}
  }
  return (
    <span
      className={styles.inlineRow}
      style={{ flex: 1, width: "100%", maxWidth: 520 }}
    >
      <Field
        className={`${styles.input} ${styles.inputFull} ${styles.flexFill}`}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="absolute path"
      />
      {isLocal && (
        <Button size="sm" onClick={browse}>
          Browse…
        </Button>
      )}
    </span>
  );
}

export function AccentField({ value, onChange }) {
  return <AccentPicker value={(value ?? "").toLowerCase()} onChange={onChange} />;
}

export function SandboxField({ profile, onSaved }) {
  const notify = useNotify();
  const [busy, setBusy] = useState(null);
  const sandbox = !!profile.sandbox;
  const network = !!profile.sandbox_allow_network;

  async function setSandbox(state) {
    setBusy("sandbox");
    try {
      await invoke("sandbox_set", { profile: profile.name, state });
      await onSaved?.();
    } catch (e) {
      notify({ message: `sandbox: ${String(e)}`, variant: "error", duration: 4000 });
    } finally {
      setBusy(null);
    }
  }

  async function setNetwork(state) {
    setBusy("network");
    try {
      await invoke("sandbox_network", { profile: profile.name, state });
      await onSaved?.();
    } catch (e) {
      notify({ message: `network: ${String(e)}`, variant: "error", duration: 4000 });
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <Row label="terminal">
        <span className={styles.inlineRow}>
          <Chip
            state={sandbox ? "on" : "off"}
            tooltip={
              <>
                <div>Wraps shell commands in sandbox-exec / bubblewrap</div>
                <div className={styles.tooltipStatus}>
                  blocks writes outside workspace + ~/.alpi
                </div>
              </>
            }
          >
            {sandbox ? "sandboxed" : "off"}
          </Chip>
          <Button
            size="sm"
            onClick={() => setSandbox(sandbox ? "off" : "on")}
            disabled={!!busy}
            loading={busy === "sandbox"}
          >
            {sandbox ? "Disable" : "Enable"}
          </Button>
        </span>
      </Row>
      <Row label="network">
        <span className={styles.inlineRow}>
          <Chip
            state={!sandbox ? "off" : network ? "on" : "error"}
            tooltip={
              !sandbox
                ? "enable sandbox first"
                : network
                  ? "sub-processes can reach the internet (git push, pip install, …)"
                  : "denied — sub-processes can't open sockets (safest)"
            }
          >
            {!sandbox ? "n/a" : network ? "allowed" : "denied"}
          </Chip>
          <Button
            size="sm"
            onClick={() => setNetwork(network ? "off" : "on")}
            disabled={!sandbox || !!busy}
            loading={busy === "network"}
          >
            {network ? "Deny" : "Allow"}
          </Button>
        </span>
      </Row>
    </>
  );
}
