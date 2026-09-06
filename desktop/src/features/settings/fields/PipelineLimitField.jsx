import { useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import Button from "../../../primitives/Button.jsx";
import Eyebrow from "../../../primitives/Eyebrow.jsx";
import Chip from "../../../primitives/Chip.jsx";
import Field from "../../../primitives/Field.jsx";
import { useNotify } from "../../../primitives/Notification.jsx";
import { useDismissOnOutside } from "../../../hooks/useDismissOnOutside.js";
import styles from "../Settings.module.css";

export function pipelineLimitLabel(limit) {
  return Number(limit) > 0 ? `${limit} workgroups` : "unlimited";
}

export function PipelineLimitField({ profile, onSaved }) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const notify = useNotify();
  const current = Number(profile.max_active_workgroups) > 0 ? Number(profile.max_active_workgroups) : 0;
  const origin = profile.max_active_workgroups_origin ?? "profile";
  const isDefaultProfile = profile.name === "default";
  const canInherit = !isDefaultProfile && origin === "profile";
  const [value, setValue] = useState(String(current));
  const [saving, setSaving] = useState(false);

  useEffect(() => { setValue(String(current)); }, [current]);
  useDismissOnOutside({ open, onClose: () => setOpen(false), wrapRef });

  const trimmed = value.trim();
  const parsed = Number(trimmed);
  const valid = /^[0-9]+$/.test(trimmed) && Number.isFinite(parsed);
  // Pinning the inherited value on a hub is a real change: it stops following the default profile.
  const dirty = valid && (parsed !== current || (origin !== "profile" && !isDefaultProfile));

  async function persist(action) {
    setSaving(true);
    try {
      await action();
      await onSaved?.();
      setOpen(false);
    } catch (e) {
      notify({ message: `active workgroups: ${String(e)}`, variant: "error", duration: 4000 });
    } finally {
      setSaving(false);
    }
  }

  async function inherit() {
    if (saving) return;
    await persist(async () => {
      await invoke("unset_config_field", { profile: profile.name, key: "alp.max_active_workgroups" });
      notify({ message: "active workgroups: following the default profile", variant: "success", duration: 3000 });
    });
  }

  async function save() {
    if (!dirty || saving) return;
    await persist(async () => {
      await invoke("set_config_field", { profile: profile.name, key: "alp.max_active_workgroups", value: String(parsed) });
      notify({ message: `active workgroups: ${pipelineLimitLabel(parsed)}`, variant: "success", duration: 3000 });
    });
  }

  return (
    <span ref={wrapRef} className={`${styles.popoverAnchor} ${styles.withHint}`}>
      <Chip
        state={current > 0 ? "on" : "off"}
        onClick={() => setOpen((o) => !o)}
        tooltip={
          <>
            <div>{isDefaultProfile ? "Workgroups every hub runs at once" : "Workgroups this hub runs at once"}</div>
            <div className={styles.tooltipStatus}>
              {(profile.queued_pipelines ?? 0) > 0 ? `${profile.queued_pipelines} queued · ` : ""}
              pipelines beyond the cap wait in the admission queue; deliberations always open and count · click to edit
            </div>
          </>
        }
      >
        {pipelineLimitLabel(current)}
      </Chip>
      {origin === "default" && <span className={styles.hint}>from default</span>}
      {open && (
        <div className={styles.popover}>
          <div className={styles.field}>
            <Eyebrow as="label">active workgroups</Eyebrow>
            <Field
              className={styles.input}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="0 = unlimited"
              spellCheck={false}
            />
          </div>
          {!valid && <div className={styles.warn}>Use a whole number of 0 or greater.</div>}
          <div className={styles.actions}>
            {canInherit && (
              <Button size="sm" onClick={inherit} disabled={saving}>
                Use default
              </Button>
            )}
            <Button size="sm" variant="primary" onClick={save} disabled={!dirty} loading={saving}>
              Save
            </Button>
          </div>
        </div>
      )}
    </span>
  );
}
