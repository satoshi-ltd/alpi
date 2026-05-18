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
  meta,
  onOpenChat,
  onTogglePause,
  paused = false,
}) {
  const isWg = kind === "workgroup";
  return (
    <header
      className={`ds-chat-header ${styles.header}`}
      style={{ "--c": accent }}
      data-drag
    >
      <div className={`row between ${styles.topRow}`}>
        <div className={`col ${styles.titleCol}`}>
          <div className="title-row">
            {isWg ? <Hash size={28} /> : <Diamond color={accent} size={14} />}
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
