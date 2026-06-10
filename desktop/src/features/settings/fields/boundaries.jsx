import { useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import Button from "../../../primitives/Button.jsx";
import Eyebrow from "../../../primitives/Eyebrow.jsx";
import Chip from "../../../primitives/Chip.jsx";
import Dropdown from "../../../primitives/Dropdown.jsx";
import useAutoPosition from "../../../primitives/useAutoPosition.js";
import { useNotify } from "../../../primitives/Notification.jsx";
import { useDismissOnOutside } from "../../../hooks/useDismissOnOutside.js";
import { Row } from "../primitives.jsx";
import { AccentPicker } from "../../../primitives/SettingsLayout.jsx";
import Field from "../../../primitives/Field.jsx";
import { BudgetEdit } from "../../../primitives/index.js";
import {
  ACCENT_PALETTE,
  HEX_RE,
  formatTokenCount,
} from "../util.js";
import styles from "../Settings.module.css";

export function BudgetField({ profile, onSaved }) {
  const notify = useNotify();
  const usd = profile.budget_daily_usd;
  const tokens = profile.budget_daily_tokens;
  const mode = usd != null ? "usd" : tokens != null ? "tokens" : "usd";
  const value = usd != null ? usd : tokens != null ? tokens : "";

  async function save({ mode: m, value: v }) {
    try {
      if (v == null || v === "") {
        await invoke("unset_config_field", { profile: profile.name, key: "budget.daily_usd" });
        await invoke("unset_config_field", { profile: profile.name, key: "budget.daily_tokens" });
      } else if (m === "usd") {
        await invoke("unset_config_field", { profile: profile.name, key: "budget.daily_tokens" });
        await invoke("set_config_field", { profile: profile.name, key: "budget.daily_usd", value: String(v) });
      } else {
        await invoke("unset_config_field", { profile: profile.name, key: "budget.daily_usd" });
        await invoke("set_config_field", { profile: profile.name, key: "budget.daily_tokens", value: String(v) });
      }
      await onSaved?.();
    } catch (e) {
      notify({ message: `budget: ${String(e)}`, variant: "error", duration: 4000 });
      throw e;
    }
  }

  const triggerLabel =
    usd != null
      ? `$${usd.toFixed(2)}/day`
      : tokens != null
        ? `${formatTokenCount(tokens)}/day`
        : "unlimited";

  return (
    <Row label="budget">
      <BudgetEdit
        value={value}
        mode={mode}
        triggerLabel={triggerLabel}
        onSave={save}
      />
    </Row>
  );
}

function ProfileBudgetEditor({ currentUsd, currentTokens, onSave }) {
  const [open, setOpen] = useState(false);
  const anchorRef = useRef(null);
  const popoverRef = useRef(null);
  const wrapRef = useRef(null);
  const initialKind = currentTokens != null ? "tokens" : "usd";
  const [kind, setKind] = useState(initialKind);
  const [value, setValue] = useState(
    currentUsd != null
      ? String(currentUsd)
      : currentTokens != null
        ? String(currentTokens)
        : "",
  );
  const [saving, setSaving] = useState(false);
  const pos = useAutoPosition({
    open,
    anchorRef,
    popoverRef,
    direction: "down",
    align: "left",
  });

  useEffect(() => {
    if (open) {
      setKind(currentTokens != null ? "tokens" : "usd");
      setValue(
        currentUsd != null
          ? String(currentUsd)
          : currentTokens != null
            ? String(currentTokens)
            : "",
      );
    }
  }, [open, currentUsd, currentTokens]);

  useDismissOnOutside({ open, onClose: () => setOpen(false), wrapRef });

  const trimmed = value.trim();
  let parsed = null;
  let valid = trimmed === "";
  if (trimmed !== "") {
    if (kind === "usd") {
      const n = Number(trimmed);
      valid = Number.isFinite(n) && n > 0;
      if (valid) parsed = n;
    } else {
      const n = parseInt(trimmed, 10);
      valid = Number.isFinite(n) && n > 0 && /^\d+$/.test(trimmed);
      if (valid) parsed = n;
    }
  }

  async function save() {
    if (!valid || saving) return;
    setSaving(true);
    try {
      await onSave?.({ kind, value: parsed });
      setOpen(false);
    } catch {
    } finally {
      setSaving(false);
    }
  }

  const hasAny = currentUsd != null || currentTokens != null;

  return (
    <span ref={wrapRef} className={styles.popoverAnchor}>
      <span ref={anchorRef}>
        <Button size="sm" onClick={() => setOpen((o) => !o)}>
          {hasAny ? "Edit" : "Set cap"}
        </Button>
      </span>
      {open && (
        <div
          ref={popoverRef}
          className={`${pos.ready ? "anim-pop " : ""}${styles.popover}`}
          style={{
            minWidth: 280,
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
            <Eyebrow as="label">cap type</Eyebrow>
            <span className={styles.inlineRow}>
              <Chip
                size="sm"
                state={kind === "usd" ? "on" : "off"}
                onClick={() => setKind("usd")}
                tooltip="for paid models — daily USD spend"
              >
                USD
              </Chip>
              <Chip
                size="sm"
                state={kind === "tokens" ? "on" : "off"}
                onClick={() => setKind("tokens")}
                tooltip="for local / free models — daily token count"
              >
                tokens
              </Chip>
            </span>
          </div>
          <div className={styles.field}>
            <Eyebrow as="label">
              {kind === "usd" ? "daily USD" : "daily tokens"}
            </Eyebrow>
            <Field
              className={styles.input}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="empty = unlimited"
              spellCheck={false}
              autoFocus
            />
          </div>
          {!valid && (
            <div className={styles.warn}>
              {kind === "usd"
                ? "must be a positive number"
                : "must be a positive integer"}
            </div>
          )}
          <div className={styles.actions}>
            <Button
              size="sm"
              variant="primary"
              onClick={save}
              disabled={!valid}
              loading={saving}
            >
              Save
            </Button>
          </div>
        </div>
      )}
    </span>
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
