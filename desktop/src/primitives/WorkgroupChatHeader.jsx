import { ChatHeader, Diamond, MeterChip, Mono, Tip } from "./index.js";
import { profileLabel } from "../lib/profile-display.js";
import SoundWave from "./SoundWave.jsx";
import HeaderMenu from "./HeaderMenu.jsx";
import styles from "./WorkgroupChatHeader.module.css";

export default function WorkgroupChatHeader({
  workgroup,
  hubAccent,
  hubName,
  hubBio,
  memberCount = 0,
  budget,           // { used, cap } in USD
  paused = false,
  onTogglePause,
  autoRead = false,
  onToggleAutoRead,
  onOpenSettings,
  onRefresh,
  tasksButton,
}) {
  const accent = hubAccent || "var(--accent)";
  const bio = (hubBio || "").trim();
  const rawDiamond = <Diamond color={accent} />;
  const diamond = bio
    ? <Tip text={bio} side="l">{rawDiamond}</Tip>
    : rawDiamond;

  const meta = (
    <>
      <span className={`row row-gap ${styles.hubRow}`}>
        <span className={styles.label}>hub</span>
        {diamond}
        <Mono className={styles.ink2}>{`@${profileLabel(hubName)}`}</Mono>
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
    </>
  );

  const right = (
    <>
      {tasksButton}
      <SoundWave accent={accent} />
      <HeaderMenu
        noun="workgroup"
        paused={paused}
        onTogglePause={onTogglePause}
        onOpenSettings={onOpenSettings}
        autoRead={autoRead}
        onToggleAutoRead={onToggleAutoRead}
        onRefresh={onRefresh}
        canRefresh
      />
    </>
  );

  return (
    <ChatHeader
      kind="workgroup"
      id={workgroup?.name || workgroup?.id || ""}
      accent={accent}
      bio={workgroup?.briefing}
      meta={meta}
      right={right}
    />
  );
}
