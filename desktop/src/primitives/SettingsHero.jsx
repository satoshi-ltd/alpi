import {
  ArrowLeftIcon,
  Diamond,
  Hash,
  IconBtn,
  PauseIcon,
  PlayIcon,
  Tip,
} from "./index.js";
import styles from "./SettingsHero.module.css";

export default function SettingsHero({
  kind = "profile",
  id,
  accent,
  bio,
  meta,
  onOpenChat,
  onTogglePause,
  paused = false,
}) {
  const isWg = kind === "workgroup";
  const trimmedBio = (bio || "").trim();
  const glyph = isWg
    ? <Hash size="md" />
    : <Diamond color={accent} size="md" />;
  const titleGlyph = !isWg && trimmedBio
    ? <Tip text={trimmedBio} side="l" escape>{glyph}</Tip>
    : glyph;
  return (
    <header
      className={`ds-chat-header ${styles.header}`}
      style={{ "--c": accent }}
      data-drag
    >
      <div className={`row between ${styles.topRow}`}>
        <div className={`col ${styles.titleCol}`}>
          <div className="title-row">
            {titleGlyph}
            <h1>{id}</h1>
            <span className="kicker">
              {isWg ? "workgroup · settings" : "profile · settings"}
            </span>
          </div>
          {meta && <div className="meta-row">{meta}</div>}
        </div>
        <div className={`row ${styles.actions}`}>
          {isWg && onTogglePause && (
            <Tip text={paused ? "Resume workgroup" : "Pause workgroup"} side="r">
              <IconBtn
                onClick={onTogglePause}
                aria-label={paused ? "Resume" : "Pause"}
              >
                {paused ? <PlayIcon /> : <PauseIcon />}
              </IconBtn>
            </Tip>
          )}
          {onOpenChat && (
            <Tip text="Back to chat · ⌘," side="r">
              <IconBtn onClick={onOpenChat} aria-label="Back to chat">
                <ArrowLeftIcon />
              </IconBtn>
            </Tip>
          )}
        </div>
      </div>
      <span className="stripe" aria-hidden />
    </header>
  );
}
