import { useState } from "react";
import { Icon, IconBtn, Kbd, Pill, Popover, Tip } from "./index.js";
import styles from "./HeaderMenu.module.css";

export default function HeaderMenu({
  noun = "profile",
  paused = false,
  onTogglePause,
  onOpenSettings,
  autoRead = false,
  onToggleAutoRead,
  onOpenSkills,
  onOpenMemory,
  onOpenTools,
  onRefresh,
  canRefresh = false,
}) {
  const [open, setOpen] = useState(false);
  const Noun = noun.charAt(0).toUpperCase() + noun.slice(1);
  const run = (fn) => () => {
    fn?.();
    setOpen(false);
  };
  return (
    <span className={styles.root}>
      <Tip text="More" side="r">
        <IconBtn aria-label="More" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
          <Icon name="ellipsis" />
        </IconBtn>
      </Tip>
      <Popover open={open} onClose={() => setOpen(false)} width="var(--pop-sm)" align="right">
        <div className={styles.menu}>
          {onOpenSettings && (
            <button type="button" className={styles.item} onClick={run(onOpenSettings)}>
              <Icon name="settings" size="lg" className={styles.icon} />
              <span className={styles.label}>{Noun} settings</span>
              <span className={styles.kbd}><Kbd>⌘</Kbd><Kbd>,</Kbd></span>
            </button>
          )}
          {onTogglePause && (
            <button type="button" className={styles.item} onClick={run(onTogglePause)}>
              <Icon name={paused ? "play" : "pause"} size="lg" className={styles.icon} />
              <span className={styles.label}>{paused ? "Resume" : "Pause"} {noun}</span>
            </button>
          )}
          {onToggleAutoRead && (
            <button type="button" className={styles.item} onClick={() => onToggleAutoRead()}>
              <Icon name="volume" size="lg" className={styles.icon} />
              <span className={styles.label}>Auto-read replies</span>
              <Pill state={autoRead ? "on" : "off"} className={styles.statePill}>{autoRead ? "on" : "off"}</Pill>
            </button>
          )}
          {(onOpenSkills || onOpenMemory || onOpenTools) && <div className={styles.sep} aria-hidden />}
          {onOpenSkills && (
            <button type="button" className={styles.item} onClick={run(onOpenSkills)}>
              <Icon name="sparkle" size="lg" className={styles.icon} />
              <span className={styles.label}>Skills</span>
            </button>
          )}
          {onOpenMemory && (
            <button type="button" className={styles.item} onClick={run(onOpenMemory)}>
              <Icon name="folder" size="lg" className={styles.icon} />
              <span className={styles.label}>Memory</span>
            </button>
          )}
          {onOpenTools && (
            <button type="button" className={styles.item} onClick={run(onOpenTools)}>
              <Icon name="cpu" size="lg" className={styles.icon} />
              <span className={styles.label}>Tools</span>
            </button>
          )}
          {onRefresh && canRefresh && (
            <>
              <div className={styles.sep} aria-hidden />
              <button type="button" className={styles.item} onClick={run(onRefresh)}>
                <Icon name="refresh" size="lg" className={styles.icon} />
                <span className={styles.label}>Refresh thread</span>
              </button>
            </>
          )}
        </div>
      </Popover>
    </span>
  );
}
