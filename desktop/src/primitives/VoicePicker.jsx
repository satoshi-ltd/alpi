import { useState } from "react";
import Popover from "./Popover.jsx";
import { Selectish, Mono, CheckIcon } from "./index.js";
import styles from "./VoicePicker.module.css";

export default function VoicePicker({
  voices = [],
  current,
  onChange,
  accent,
}) {
  const [open, setOpen] = useState(false);
  const selected = voices.find((v) => v.id === current) || null;
  return (
    <span className={styles.root}>
      <Selectish onClick={() => setOpen((o) => !o)}>
        {selected ? `${selected.name} · ${selected.desc}` : "—"}
      </Selectish>
      <Popover open={open} onClose={() => setOpen(false)} width="var(--pop-sm)">
        <div className={styles.list}>
          {voices.map((v) => {
            const sel = v.id === current;
            return (
              <button
                key={v.id}
                type="button"
                onClick={() => {
                  onChange?.(v.id);
                  setOpen(false);
                }}
                className={`${styles.row} ${sel ? styles.selected : ""}`}
                style={sel && accent ? { "--c": accent } : undefined}
              >
                <span className={styles.check}>
                  {sel && <CheckIcon style={{ width: 13, height: 13, strokeWidth: 2.4 }} />}
                </span>
                <span className={styles.body}>
                  <span className={styles.name}>{v.name}</span>
                  <Mono className={styles.desc}>{v.desc}</Mono>
                </span>
              </button>
            );
          })}
        </div>
      </Popover>
    </span>
  );
}
