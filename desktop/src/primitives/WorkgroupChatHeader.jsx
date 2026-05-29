import { ChatHeader } from "./index.js";
import {
  Btn,
  Diamond,
  IconBtn,
  Mono,
  MeterChip,
  Pill,
  RefreshButton,
  Tip,
  GearIcon,
  PauseIcon,
  PlayIcon,
} from "./index.js";
import styles from "./WorkgroupChatHeader.module.css";

export default function WorkgroupChatHeader({
  workgroup,
  hubAccent,
  hubName,
  memberCount = 0,
  budget,           // { used, cap } in USD
  paused = false,
  onTogglePause,
  onOpenSettings,
  onRefresh,
  tasksButton,
}) {
  const accent = hubAccent || "var(--accent)";

  const meta = (
    <>
      <span className={`row row-gap ${styles.hubRow}`}>
        <span className={styles.label}>hub</span>
        <Diamond color={accent} />
        <Mono className={styles.ink2}>{`@${hubName}`}</Mono>
      </span>
      <span className="sep" aria-hidden />
      <span>
        <span className={styles.label}>members</span>{" "}
        <Mono className={`tnum ${styles.ink2}`}>{memberCount}</Mono>
      </span>
      {budget && budget.cap > 0 && (
        <>
          <span className="sep" aria-hidden />
          <MeterChip
            value={
              <>
                ${budget.used.toFixed(2)}
                <span className={styles.ink3}>/${budget.cap.toFixed(2)}</span>
              </>
            }
            pct={Math.min(1, budget.used / budget.cap)}
            color={accent}
            tip={`Workgroup budget — spent $${budget.used.toFixed(2)} of $${budget.cap.toFixed(2)} cap`}
          />
        </>
      )}
      {paused && (
        <>
          <span className="sep" aria-hidden />
          <Pill state="warn">paused</Pill>
        </>
      )}
    </>
  );

  const right = (
    <>
      {tasksButton}
      {tasksButton && <span className={styles.divider} aria-hidden />}
      {onTogglePause && (
        <Btn variant="ghost" onClick={onTogglePause} title={paused ? "Resume workgroup" : "Pause workgroup"}>
          {paused ? <PlayIcon /> : <PauseIcon />}
          <span>{paused ? "Resume" : "Pause"}</span>
        </Btn>
      )}
      <span className={styles.divider} aria-hidden />
      {onOpenSettings && (
        <Tip text="Workgroup settings" side="r">
          <IconBtn onClick={onOpenSettings} aria-label="Workgroup settings"><GearIcon /></IconBtn>
        </Tip>
      )}
      {onRefresh && <RefreshButton onClick={onRefresh} />}
    </>
  );

  return (
    <ChatHeader
      kind="workgroup"
      id={workgroup?.name || workgroup?.id || ""}
      accent={accent}
      meta={meta}
      right={right}
    />
  );
}
