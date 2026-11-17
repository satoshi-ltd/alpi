import ChatHeader from "./ChatHeader.jsx";
import {
  ArrowLeftIcon,
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
  shape,
  bio,
  meta,
  onOpenChat,
  onTogglePause,
  paused = false,
  onOpenConnections,
  actions = null,
  mark = null,
  markColor = null,
}) {
  const isWg = kind === "workgroup";
  const isConnections = kind === "connections";
  const right = (
    <>
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
    </>
  );
  return (
    <ChatHeader
      kind={isWg ? "workgroup" : "profile"}
      id={id}
      accent={accent}
      shape={shape}
      bio={isConnections ? null : bio}
      meta={meta || null}
      right={right}
      paused={paused}
      mark={mark}
      markColor={markColor}
      state="idle"
      label={isConnections ? "Connections" : "Settings"}
      className={styles.header}
    />
  );
}
