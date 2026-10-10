import { WORKGROUP_FOLD } from "../../../common/folds.mjs";
import { palettes } from "../../../common/tokens.mjs";
import {
  ArrowLeftIcon,
  Crease,
  Fold,
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
  fold,
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
  const glyph = isWg
    ? <Fold fold={WORKGROUP_FOLD} color={accent} size="md" unfolded={paused} />
    : <Fold fold={fold} color={accent} size="md" unfolded={paused} />;
  const titleGlyph = !isConnections && trimmedBio
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
            <h1><Crease text={id} accent={paused ? palettes.light.ink3 : accent} /></h1>
            <span className="eyebrow">{isConnections ? "connections" : "settings"}</span>
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
    </header>
  );
}
