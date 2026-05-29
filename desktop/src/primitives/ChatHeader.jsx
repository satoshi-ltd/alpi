import { Diamond, Hash, Tip } from "./index.js";
import styles from "./ChatHeader.module.css";

export default function ChatHeader({
  kind = "profile",
  id,
  accent,
  bio,
  meta,
  right,
}) {
  const isWg = kind === "workgroup";
  const trimmedBio = (bio || "").trim();
  const glyph = isWg
    ? <Hash size="md" />
    : <Diamond color={accent} size="md" />;
  const titleGlyph = !isWg && trimmedBio
    ? <Tip text={trimmedBio} side="l">{glyph}</Tip>
    : glyph;
  return (
    <header className="ds-chat-header" style={{ "--c": accent }} data-drag>
      <div className={`row between ${styles.topRow}`}>
        <div className={`col ${styles.titleCol}`}>
          <div className="title-row">
            {titleGlyph}
            <h1>{id}</h1>
            <span className="kicker">{isWg ? "workgroup" : "profile"}</span>
          </div>
          {meta && <div className="meta-row">{meta}</div>}
        </div>
        {right && <div className={`row ${styles.actions}`}>{right}</div>}
      </div>
      <span className="stripe" aria-hidden />
    </header>
  );
}
