import { useState } from "react";
import { Button, Icon, IconBtn, KeyHint, Pill, Popover } from "./index.js";
import { shortcutKeys } from "../lib/shortcuts.js";
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
      <IconBtn tip="More" tipSide="r" aria-label="More" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <Icon name="ellipsis" />
      </IconBtn>
      <Popover open={open} onClose={() => setOpen(false)} align="right" navigable role="menu">
        <div className={styles.menu}>
          {onOpenSettings && (
            <Button role="menuitem" fullWidth className={styles.item} onClick={run(onOpenSettings)}>
              <Icon name="settings" size="lg" className={styles.icon} />
              <span className={styles.label}>{Noun} settings</span>
              <KeyHint hint={shortcutKeys("settings")} />
            </Button>
          )}
          {onTogglePause && (
            <Button role="menuitem" fullWidth className={styles.item} onClick={run(onTogglePause)}>
              <Icon name={paused ? "play" : "pause"} size="lg" className={styles.icon} />
              <span className={styles.label}>{paused ? "Resume" : "Pause"} {noun}</span>
              <KeyHint hint={shortcutKeys("pause")} />
            </Button>
          )}
          {onToggleAutoRead && (
            <Button role="menuitem" fullWidth className={styles.item} onClick={() => onToggleAutoRead()}>
              <Icon name="volume" size="lg" className={styles.icon} />
              <span className={styles.label}>Auto-read replies</span>
              <Pill state={autoRead ? "on" : "off"} className={styles.statePill}>{autoRead ? "on" : "off"}</Pill>
            </Button>
          )}
          {(onOpenSkills || onOpenMemory || onOpenTools || onOpenSchedule) && <div className={styles.sep} aria-hidden />}
          {onOpenSkills && (
            <Button role="menuitem" fullWidth className={styles.item} onClick={run(onOpenSkills)}>
              <Icon name="sparkle" size="lg" className={styles.icon} />
              <span className={styles.label}>Skills</span>
              <KeyHint hint={shortcutKeys("skills")} />
            </Button>
          )}
          {onOpenMemory && (
            <Button role="menuitem" fullWidth className={styles.item} onClick={run(onOpenMemory)}>
              <Icon name="folder" size="lg" className={styles.icon} />
              <span className={styles.label}>Memory</span>
              <KeyHint hint={shortcutKeys("memory")} />
            </Button>
          )}
          {onOpenTools && (
            <Button role="menuitem" fullWidth className={styles.item} onClick={run(onOpenTools)}>
              <Icon name="cpu" size="lg" className={styles.icon} />
              <span className={styles.label}>Tools</span>
              <KeyHint hint={shortcutKeys("tools")} />
            </Button>
          )}
          {onOpenSchedule && (
            <Button role="menuitem" fullWidth className={styles.item} onClick={run(onOpenSchedule)}>
              <Icon name="clock" size="lg" className={styles.icon} />
              <span className={styles.label}>Schedule</span>
              <KeyHint hint={shortcutKeys("schedule")} />
            </Button>
          )}
          {onRefresh && canRefresh && (
            <>
              <div className={styles.sep} aria-hidden />
              <Button role="menuitem" fullWidth className={styles.item} onClick={run(onRefresh)}>
                <Icon name="refresh" size="lg" className={styles.icon} />
                <span className={styles.label}>Refresh thread</span>
                <KeyHint hint={shortcutKeys("refresh")} />
              </Button>
            </>
          )}
        </div>
      </Popover>
    </span>
  );
}
