import { ChatHeader, Fold, MeterChip, Tip } from "./index.js";
import { HeaderDetail } from "./ChatHeader.jsx";
import { workgroupStatusLine } from "../../../common/workgroupMarkState.mjs";
import { profileLabel } from "../lib/profile-display.js";
import SoundWave from "./SoundWave.jsx";
import HeaderMenu from "./HeaderMenu.jsx";
import styles from "./WorkgroupChatHeader.module.css";

export default function WorkgroupChatHeader({
  workgroup,
  hubAccent,
  hubShape,
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
  mark = null,
}) {
  const accent = hubAccent || "var(--accent)";
  const bio = (hubBio || "").trim();
  const rawDiamond = <Fold shape={hubShape} color={accent} />;
  const diamond = bio
    ? <Tip text={bio} side="l">{rawDiamond}</Tip>
    : rawDiamond;

  const status = paused ? null : workgroupStatusLine(mark);
  const flag = !paused && (mark?.state === "needs" || mark?.state === "failed")
    ? { label: status || (mark.state === "needs" ? "Needs you" : "Failed"), tone: mark.state === "failed" ? "danger" : "warning" }
    : null;
  const meta = (
    <>
      <HeaderDetail label="Hub">
        <span className={`row row-gap ${styles.hubRow}`}>
          {diamond}
          <span className={styles.ink2}>{`@${profileLabel(hubName)}`}</span>
        </span>
      </HeaderDetail>
      <HeaderDetail label="Members">
        <span className={`tnum ${styles.ink2}`}>{memberCount}</span>
      </HeaderDetail>
      {status && (
        <HeaderDetail label="Status">
          <span className={styles.ink2} data-status="">{status}</span>
        </HeaderDetail>
      )}
      {budget && budget.cap > 0 && (
        <HeaderDetail label="Budget">
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
        </HeaderDetail>
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
      paused={paused}
      mark={mark}
      flag={flag}
    />
  );
}
