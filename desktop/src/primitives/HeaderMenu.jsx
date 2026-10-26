import { useState } from "react";
import { Icon, IconBtn, KeyHint, Pill, Popover } from "./index.js";
import { MenuSeparator, menuRowClass } from "./Menu.jsx";
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
      <IconBtn tip="More" tipSide="r" aria-label="More" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <Icon name="ellipsis" />
      </IconBtn>
      <Popover open={open} onClose={() => setOpen(false)} align="right" navigable role="menu">
        <div className={styles.menu}>
          {onOpenSettings && (
            <button type="button" role="menuitem" className={menuRowClass()} onClick={run(onOpenSettings)}>
              <Icon name="settings" size="md" className={styles.icon} />
              <span className={styles.label}>{Noun} settings</span>
              <KeyHint hint={shortcutKeys("settings")} />
            </button>
          )}
          {onTogglePause && (
            <button type="button" role="menuitem" className={menuRowClass()} onClick={run(onTogglePause)}>
              <Icon name={paused ? "play" : "pause"} size="md" className={styles.icon} />
              <span className={styles.label}>{paused ? "Resume" : "Pause"} {noun}</span>
              <KeyHint hint={shortcutKeys("pause")} />
            </button>
          )}
          {onToggleAutoRead && (
            <button type="button" role="menuitemcheckbox" aria-checked={autoRead} className={menuRowClass()} onClick={() => onToggleAutoRead()}>
              <Icon name="volume" size="md" className={styles.icon} />
              <span className={styles.label}>Auto-read replies</span>
              <Pill state={autoRead ? "on" : "off"} className={styles.statePill}>{autoRead ? "on" : "off"}</Pill>
            </button>
          )}
          {(onOpenSkills || onOpenMemory || onOpenTools || onOpenSchedule) && <MenuSeparator />}
          {onOpenSkills && (
            <button type="button" role="menuitem" className={menuRowClass()} onClick={run(onOpenSkills)}>
              <Icon name="sparkle" size="md" className={styles.icon} />
              <span className={styles.label}>Skills</span>
              <KeyHint hint={shortcutKeys("skills")} />
            </button>
          )}
          {onOpenMemory && (
            <button type="button" role="menuitem" className={menuRowClass()} onClick={run(onOpenMemory)}>
              <Icon name="folder" size="md" className={styles.icon} />
              <span className={styles.label}>Memory</span>
              <KeyHint hint={shortcutKeys("memory")} />
            </button>
          )}
          {onOpenTools && (
            <button type="button" role="menuitem" className={menuRowClass()} onClick={run(onOpenTools)}>
              <Icon name="cpu" size="md" className={styles.icon} />
              <span className={styles.label}>Tools</span>
              <KeyHint hint={shortcutKeys("tools")} />
            </button>
          )}
          {onOpenSchedule && (
            <button type="button" role="menuitem" className={menuRowClass()} onClick={run(onOpenSchedule)}>
              <Icon name="clock" size="md" className={styles.icon} />
              <span className={styles.label}>Schedule</span>
              <KeyHint hint={shortcutKeys("schedule")} />
            </button>
          )}
          {onRefresh && canRefresh && (
            <>
              <MenuSeparator />
              <button type="button" role="menuitem" className={menuRowClass()} onClick={run(onRefresh)}>
                <Icon name="refresh" size="md" className={styles.icon} />
                <span className={styles.label}>Refresh thread</span>
                <KeyHint hint={shortcutKeys("refresh")} />
              </button>
            </>
          )}
        </div>
      </Popover>
    </span>
  );
}
