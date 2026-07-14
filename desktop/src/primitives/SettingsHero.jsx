import {
  ArrowLeftIcon,
  Diamond,
  Hash,
  IconBtn,
  PauseIcon,
  PlayIcon,
  Tip,
  Button,
  GlobeIcon,
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
  onOpenConnections,
  actions = null,
}) {
  const isWg = kind === "workgroup";
  const isConnections = kind === "connections";
  const trimmedBio = (bio || "").trim();
  const glyph = isConnections
    ? <GlobeIcon />
    : isWg
      ? <Hash size="md" />
      : <Diamond color={accent} size="md" />;
  const titleGlyph = !isWg && !isConnections && trimmedBio
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
              {isConnections
                ? "host · settings"
                : isWg ? "workgroup · settings" : "profile · settings"}
            </span>
          </div>
          {meta && <div className="meta-row">{meta}</div>}
        </div>
        <div className={`row ${styles.actions}`}>
          {actions}
          {onOpenConnections && (
            <Button icon={<GlobeIcon />} onClick={onOpenConnections}>Connections</Button>
          )}
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
