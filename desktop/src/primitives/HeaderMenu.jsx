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
  onOpenSchedule,
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
              <span className={styles.kbd}><Kbd>⇧</Kbd><Kbd>⌘</Kbd><Kbd>P</Kbd></span>
            </button>
          )}
          {onToggleAutoRead && (
            <button type="button" className={styles.item} onClick={() => onToggleAutoRead()}>
              <Icon name="volume" size="lg" className={styles.icon} />
              <span className={styles.label}>Auto-read replies</span>
              <Pill state={autoRead ? "on" : "off"} className={styles.statePill}>{autoRead ? "on" : "off"}</Pill>
            </button>
          )}
          {(onOpenSkills || onOpenMemory || onOpenTools || onOpenSchedule) && <div className={styles.sep} aria-hidden />}
          {onOpenSkills && (
            <button type="button" className={styles.item} onClick={run(onOpenSkills)}>
              <Icon name="sparkle" size="lg" className={styles.icon} />
              <span className={styles.label}>Skills</span>
              <span className={styles.kbd}><Kbd>⇧</Kbd><Kbd>⌘</Kbd><Kbd>S</Kbd></span>
            </button>
          )}
          {onOpenMemory && (
            <button type="button" className={styles.item} onClick={run(onOpenMemory)}>
              <Icon name="folder" size="lg" className={styles.icon} />
              <span className={styles.label}>Memory</span>
              <span className={styles.kbd}><Kbd>⇧</Kbd><Kbd>⌘</Kbd><Kbd>M</Kbd></span>
            </button>
          )}
          {onOpenTools && (
            <button type="button" className={styles.item} onClick={run(onOpenTools)}>
              <Icon name="cpu" size="lg" className={styles.icon} />
              <span className={styles.label}>Tools</span>
              <span className={styles.kbd}><Kbd>⇧</Kbd><Kbd>⌘</Kbd><Kbd>T</Kbd></span>
            </button>
          )}
          {onOpenSchedule && (
            <button type="button" className={styles.item} onClick={run(onOpenSchedule)}>
              <Icon name="clock" size="lg" className={styles.icon} />
              <span className={styles.label}>Schedule</span>
              <span className={styles.kbd}><Kbd>⇧</Kbd><Kbd>⌘</Kbd><Kbd>E</Kbd></span>
            </button>
          )}
          {onRefresh && canRefresh && (
            <>
              <div className={styles.sep} aria-hidden />
              <button type="button" className={styles.item} onClick={run(onRefresh)}>
                <Icon name="refresh" size="lg" className={styles.icon} />
                <span className={styles.label}>Refresh thread</span>
                <span className={styles.kbd}><Kbd>⇧</Kbd><Kbd>⌘</Kbd><Kbd>R</Kbd></span>
              </button>
            </>
          )}
        </div>
      </Popover>
    </span>
  );
}
