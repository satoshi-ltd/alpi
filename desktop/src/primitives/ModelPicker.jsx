import { useEffect, useRef, useState } from "react";

import { useDismissOnOutside } from "../hooks/useDismissOnOutside.js";
import { I } from "./icons.jsx";
import Tip from "./Tip.jsx";
import { fmtTok } from "../lib/format.js";
import styles from "./ModelPicker.module.css";

export default function ModelPicker({
  currentModel,
  accent,
  models = {},
  onPick,
  onSetDefault,
  override = false,
  mode = "override",
  variant = "ghost",
}) {
  const [open, setOpen] = useState(false);
  const [picked, setPicked] = useState(currentModel);
  const ref = useRef(null);

  useDismissOnOutside({ open, onClose: () => setOpen(false), wrapRef: ref });

  useEffect(() => {
    setPicked(currentModel);
  }, [currentModel]);

  const slash = picked?.indexOf("/") ?? -1;
  const label = slash >= 0 ? picked.slice(slash + 1) : (picked || "");

  return (
    <span ref={ref} className={styles.modelPickerWrap}>
      <Tip
        text={
          mode === "default"
            ? "Model — default for this profile"
            : override
              ? "Model — override active (not this profile's configured model)"
              : "Model — overrides for this message"
        }
        side="up"
      >
        <button
          type="button"
          className={`btn btn-ghost ${styles.modelPickerTrigger} ${variant === "field" ? styles.modelPickerTriggerField : ""}`.trim()}
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
        >
          <I.Sparkle
            size="sm"
            className={override ? styles.modelPickerIconOverride : styles.modelPickerIcon}
            style={override && accent ? { "--c": accent } : undefined}
          />
          <span className={styles.modelPickerLabel}>{label}</span>
          <I.ChevDown style={{ width: 12, height: 12 }} />
        </button>
      </Tip>
      {open && (
        <div
          className={`anim-pop ${styles.modelPickerPop} ${
            mode === "default" ? styles.modelPickerPopDown : styles.modelPickerPopUp
          }`}
        >
          <div className={`col ${styles.modelPickerList}`}>
            {Object.entries(models).map(([provider, list]) => (
              <div key={provider}>
                <div className={`eyebrow ${styles.modelPickerEyebrow}`}>
                  {provider}
                </div>
                {list.map((m) => {
                  const sel = picked === m.id;
                  return (
                    <button
                      key={m.id}
                      type="button"
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
                            style={{ width: 13, height: 13, strokeWidth: 2.4 }}
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
