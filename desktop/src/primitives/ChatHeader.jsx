import { WORKGROUP_FOLD } from "../../../common/folds.mjs";
import { palettes } from "../../../common/tokens.mjs";
import { Crease, Fold, Tip } from "./index.js";
import styles from "./ChatHeader.module.css";

export default function ChatHeader({
  kind = "profile",
  id,
  accent,
  fold,
  bio,
  meta,
  right,
  paused = false,
}) {
  const isWg = kind === "workgroup";
  const trimmedBio = (bio || "").trim();
  const glyph = isWg
    ? <Fold fold={WORKGROUP_FOLD} color={accent} size="md" unfolded={paused} />
    : <Fold fold={fold} color={accent} size="md" unfolded={paused} />;
  const titleGlyph = trimmedBio
    ? <Tip text={trimmedBio} side="l">{glyph}</Tip>
    : glyph;
  return (
    <header className="ds-chat-header" style={{ "--c": accent }} data-drag>
      <div className={`row between ${styles.topRow}`}>
        <div className={`col ${styles.titleCol}`}>
          <div className="title-row">
            {titleGlyph}
            <h1><Crease text={id} accent={paused ? palettes.light.ink3 : accent} /></h1>
          </div>
          {meta && <div className="meta-row">{meta}</div>}
        </div>
        {right && <div className={`row ${styles.actions}`}>{right}</div>}
      </div>
    </header>
  );
}
