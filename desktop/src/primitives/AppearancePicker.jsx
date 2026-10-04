import { useEffect, useRef, useState } from "react";
import { FOLD_IDS, DEFAULT_FOLD, normaliseFold } from "../../../common/folds.mjs";
import { ACCENTS, pairName, selectedAccent } from "../../../common/accents.mjs";
import ActionLink from "./ActionLink.jsx";
import Eyebrow from "./Eyebrow.jsx";
import Fold from "./Fold.jsx";
import IconBtn from "./IconBtn.jsx";
import Selectish from "./Selectish.jsx";
import { useDismissOnOutside } from "../hooks/useDismissOnOutside.js";
import styles from "./AppearancePicker.module.css";

const FALLBACK_ACCENT = "#f0b447";
const HEX_RE = /^#[0-9a-f]{6}$/i;

export default function AppearancePicker({ fold, accent, onChange }) {
  const [open, setOpen] = useState(false);
  const [hex, setHex] = useState(accent || FALLBACK_ACCENT);
  const ref = useRef(null);

  useDismissOnOutside({ open, onClose: () => setOpen(false), wrapRef: ref });

  useEffect(() => {
    setHex(accent || FALLBACK_ACCENT);
  }, [accent]);

  const id = normaliseFold(fold);
  const colour = accent || FALLBACK_ACCENT;
  const name = pairName(id, colour);
  const swatch = selectedAccent(colour);
  const isValidHex = HEX_RE.test(hex);

  const pickColour = (c) => {
    setHex(c);
    onChange?.({ accent: c });
  };

  return (
    <span ref={ref} className={styles.wrap}>
      <Selectish
        leading={<Fold fold={id} color={colour} />}
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        {name}
      </Selectish>
      {open && (
        <div className={`anim-pop ${styles.popover}`}>
          <Eyebrow>Object</Eyebrow>
          <div className={styles.objects}>
            {FOLD_IDS.map((candidate) => {
              const sel = candidate === id;
              return (
                <IconBtn
                  key={candidate}
                  tip={candidate}
                  tipSide="up"
                  aria-label={candidate}
                  aria-pressed={sel}
                  onClick={() => onChange?.({ fold: candidate })}
                  className={`${styles.object} ${sel ? styles.selected : ""}`}
                >
                  <Fold fold={candidate} color={colour} size={28} />
                </IconBtn>
              );
            })}
          </div>
          <Eyebrow>Colour</Eyebrow>
          <div className={styles.colours}>
            {ACCENTS.map(([label, c]) => {
              const sel = swatch === c;
              return (
                <IconBtn
                  key={c}
                  tip={`${label} · ${c}`}
                  tipSide="up"
                  aria-label={`${label} ${c}`}
                  aria-pressed={sel}
                  onClick={() => pickColour(c)}
                  className={`${styles.colour} ${sel ? styles.selected : ""}`}
                >
                  <span
                    className={styles.chip}
                    style={{ background: c }}
                  />
                </IconBtn>
              );
            })}
          </div>
          <input
            value={hex}
            onChange={(e) => {
              setHex(e.target.value);
              if (HEX_RE.test(e.target.value)) onChange?.({ accent: e.target.value });
            }}
            className={`field field-mono ${styles.hexInput}`}
            placeholder="#hex"
            spellCheck={false}
            aria-label="accent hex"
          />
          {!isValidHex && hex.length > 0 && (
            <div className={styles.hexError}>must be 6-digit #hex</div>
          )}
          <div className={styles.preview}>
            <Fold fold={id} color={colour} size={40} />
            <div className={styles.previewText}>
              <span className={styles.previewName}>{name.charAt(0).toUpperCase() + name.slice(1)}</span>
              <span className={`mono ${styles.previewMeta}`}>{`fold: ${id} · accent: "${colour}"`}</span>
            </div>
          </div>
          <ActionLink onClick={() => onChange?.({ fold: DEFAULT_FOLD })}>Reset to diamond</ActionLink>
        </div>
      )}
    </span>
  );
}
