import { ChatHeader } from "./index.js";
import { WorkgroupDetails } from "./HeaderDetails.jsx";
import { workgroupStatusLine } from "../../../common/workgroupMarkState.mjs";
import SoundWave from "./SoundWave.jsx";
import HeaderMenu from "./HeaderMenu.jsx";

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
  markColor = null,
}) {
  const accent = hubAccent || "var(--accent)";

  const status = paused ? null : workgroupStatusLine(mark);
  const flag = !paused && (mark?.state === "needs" || mark?.state === "failed")
    ? { label: status || (mark.state === "needs" ? "Needs you" : "Failed"), tone: mark.state === "failed" ? "danger" : "warning" }
    : null;
  const meta = (
    <WorkgroupDetails hubName={hubName} hubShape={hubShape} hubBio={hubBio} memberCount={memberCount} status={status} budget={budget} accent={accent} />
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
      markColor={markColor}
      flag={flag}
    />
  );
}
