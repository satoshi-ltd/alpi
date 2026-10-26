import Button from "./Button.jsx";
import { useEffect, useRef, useState } from "react";

import { useDismissOnOutside } from "../hooks/useDismissOnOutside.js";
import { navigateMenu } from "../lib/menuNavigation.js";
import { I } from "./icons.jsx";
import Tip from "./Tip.jsx";
import { fmtTok } from "../lib/format.js";
import { modelLabel } from "../lib/modelLabel.js";
import styles from "./ModelPicker.module.css";

const EFFORT_OPTIONS = [
  { value: "", label: "Default" },
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
];

export default function ModelPicker({
  currentModel,
  accent,
  models = {},
  onPick,
  onSetDefault,
  override = false,
  mode = "override",
  variant = "ghost",
  effort = "",
  effortSupported = false,
  onEffortChange,
}) {
  const [open, setOpen] = useState(false);
  const [picked, setPicked] = useState(currentModel);
  const ref = useRef(null);
  const popRef = useRef(null);
  const triggerRef = useRef(null);

  useDismissOnOutside({ open, onClose: () => setOpen(false), wrapRef: ref });

  useEffect(() => {
    if (open) popRef.current?.querySelector("button:not(:disabled)")?.focus();
    else if (ref.current?.contains(document.activeElement) || document.activeElement === document.body) triggerRef.current?.focus();
  }, [open]);

  useEffect(() => {
    setPicked(currentModel);
  }, [currentModel]);

  const label = modelLabel(picked);
  const supported = typeof effortSupported === "function" ? !!effortSupported(picked) : !!effortSupported;
  const effortTag = supported && effort ? effort : null;

  return (
    <span ref={ref} className={styles.modelPickerWrap}>
      <Tip
        text={picked}
        side="up"
      >
        <Button
          ref={triggerRef}
          type="button"
          variant="ghost"
          className={variant === "field" ? styles.modelPickerTriggerField : undefined}
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
        >
          <I.Sparkle
            size="sm"
            className={override ? styles.modelPickerIconOverride : styles.modelPickerIcon}
            style={override && accent ? { "--c": accent } : undefined}
          />
          <span className={styles.modelPickerLabel}>
            <span className={styles.modelPickerLabelModel}>{label}</span>
            {effortTag && <span className={styles.modelPickerLabelEffort}>{` · ${effortTag}`}</span>}
          </span>
          <I.ChevDown size="sm" />
        </Button>
      </Tip>
      {open && (
        <div
          ref={popRef}
          onKeyDown={(event) => navigateMenu(event, popRef.current)}
          className={`anim-pop ${styles.modelPickerPop} ${
            mode === "default" ? styles.modelPickerPopDown : styles.modelPickerPopUp
          }`}
        >
          <div role="listbox" aria-label="Model" className={`col ${styles.modelPickerList}`}>
            {Object.entries(models).map(([provider, list]) => (
              <div key={provider} role="group" aria-label={provider}>
                <div role="presentation" className={`eyebrow ${styles.modelPickerEyebrow}`}>
                  {provider}
                </div>
                {list.map((m) => {
                  const sel = picked === m.id;
                  return (
                    <button
                      key={m.id}
                      type="button"
                      role="option"
                      aria-selected={sel}
                      onClick={() => {
                        setPicked(m.id);
                        onPick?.(m.id);
                        setOpen(false);
                      }}
                      className={`row ${styles.modelPickerOption} ${
                        sel ? styles.modelPickerOptionSelected : ""
                      }`}
                    >
                      <span
                        className={`${styles.modelPickerCheckSlot} ${
                          sel ? styles.modelPickerCheckSlotSelected : ""
                        }`}
                        style={sel ? { "--c": accent } : undefined}
                      >
                        {sel && (
                          <I.Check
                            size="sm"
                          />
                        )}
                      </span>
                      <span className={`col ${styles.modelPickerOptionBody}`}>
                        <span
                          className={`${styles.modelPickerOptionLabel} ${
                            sel ? styles.modelPickerOptionLabelSelected : ""
                          }`}
                        >
                          {m.label}
                        </span>
                        {m.ctx != null && (
                          <span
                            className={`mono ${styles.modelPickerOptionCtx}`}
                          >
                            {fmtTok(m.ctx)} ctx
                          </span>
                        )}
                      </span>
                      {m.badge && (
                        <span className={`tag ${styles.modelPickerBadge}`}>
                          {m.badge}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            ))}
          </div>
          {supported && (
            <div className={styles.modelPickerEffort}>
              <div role="presentation" className={`eyebrow ${styles.modelPickerEyebrow}`}>Reasoning effort · saved for this profile</div>
              <div role="radiogroup" aria-label="Reasoning effort" className={styles.modelPickerSegments}>
                {EFFORT_OPTIONS.map((opt) => {
                  const on = opt.value === (effort ?? "");
                  return (
                    <button
                      key={opt.value || "default"}
                      type="button"
                      role="radio"
                      aria-checked={on}
                      onClick={() => onEffortChange?.(opt.value)}
                      className={`${styles.modelPickerSegment} ${on ? styles.modelPickerSegmentOn : ""}`}
                    >
                      {opt.label}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
          {mode === "override" && (
            <div className={`row between ${styles.modelPickerFooter}`}>
              <span>Override for this message only</span>
              {onSetDefault && (
                <button
                  type="button"
                  className={styles.modelPickerFooterLink}
                  onClick={() => {
                    setOpen(false);
                    onSetDefault();
                  }}
                >
                  Set default…
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </span>
  );
}
