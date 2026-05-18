import { useEffect, useMemo, useRef, useState } from "react";
import { Diamond, ChevDownIcon, Mono } from "../primitives/index.js";
import ToPickerBar from "../primitives/ToPickerBar.jsx";
import { profileLabel } from "../lib/profile-display.js";
import styles from "./AlpiPicker.module.css";

export default function AlpiPicker({ profiles, activeAlpi, onChange, variant = "chip", modelLabel = null }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const ref = useRef(null);

  const active = profiles.find((p) => p.name === activeAlpi) ?? null;

  useEffect(() => {
    if (!open) return undefined;
    function onDoc(e) {
      if (!ref.current?.contains(e.target)) setOpen(false);
    }
    function onKey(e) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const filtered = useMemo(() => {
    const q = query.toLowerCase().trim();
    if (!q) return profiles;
    return profiles.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        profileLabel(p.name).toLowerCase().includes(q) ||
        (p.model ?? "").toLowerCase().includes(q),
    );
  }, [profiles, query]);

  return (
    <span ref={ref} className={`${styles.root} ${variant === "bar" ? styles.rootBar : ""}`.trim()}>
      {variant === "bar" ? (
        <ToPickerBar
          profile={active}
          model={modelLabel}
          open={open}
          onClick={() => setOpen((o) => !o)}
        />
      ) : (
        <button
          type="button"
          className={`btn btn-ghost ${styles.trigger}`}
          onClick={() => setOpen((o) => !o)}
        >
          {active && <Diamond color={active.accent} size={9} />}
          <Mono>{active ? profileLabel(active.name) : "—"}</Mono>
          <ChevDownIcon style={{ width: 12, height: 12 }} />
        </button>
      )}
      {open && (
        <div className={`anim-pop ${styles.popover}`}>
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Find alpi…"
            className={styles.search}
          />
          <div className={`scroll ${styles.list}`}>
            {filtered.length === 0 ? (
              <div className={styles.empty}>No alpis match</div>
            ) : (
              filtered.map((p) => {
                const sel = p.name === activeAlpi;
                return (
                  <button
                    key={p.name}
                    type="button"
                    onClick={() => {
                      onChange?.(p.name);
                      setOpen(false);
                    }}
                    className={`row row-gap ${styles.option} ${sel ? styles.optionSelected : ""}`}
                  >
                    <Diamond color={p.accent} />
                    <span className={styles.optionLabel}>
                      {profileLabel(p.name)}
                    </span>
                    {p.model && (
                      <Mono className={styles.optionModel}>
                        {p.model.split("/").pop()}
                      </Mono>
                    )}
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </span>
  );
}
