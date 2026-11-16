import { ChatHeader } from "./index.js";
import { ProfileDetails, profileBudget } from "./HeaderDetails.jsx";
import { profileLabel } from "../lib/profile-display.js";
import SessionsButton from "./SessionsButton.jsx";
import SoundWave from "./SoundWave.jsx";
import HeaderMenu from "./HeaderMenu.jsx";

export const HIGH_USE = 0.8;

export default function ProfileChatHeader({
  profile,
  sessionData,
  model,
  contextWindow = 200_000,
  liveCtxTokens = null,
  activeSessionId,
  connectionId = null,
  onOpenSkills,
  onOpenMemory,
  onOpenTools,
  onOpenSchedule,
  onOpenSettings,
  onRefresh,
  paused = false,
  onTogglePause,
  autoRead = false,
  onToggleAutoRead,
  onNewSession,
  onChangeSession,
  sessionsOpenTick = 0,
  sessionsButton,
  markState = null,
}) {
  const accent = profile?.accent || "var(--accent)";
  const shownModel = model || profile?.model;
  const ctxTokens = liveCtxTokens ?? sessionData?.last_ctx_tokens ?? 0;
  const ctxPct = contextWindow > 0 ? Math.min(1, ctxTokens / contextWindow) : 0;

  const budget = profileBudget(profile);
  const budgetPct = budget ? Math.min(1, budget.used / budget.cap) : 0;
  const flag = paused
    ? null
    : budgetPct >= HIGH_USE
      ? { label: `Daily budget ${Math.round(budgetPct * 100)}% used`, tone: budgetPct >= 1 ? "danger" : "warning" }
      : ctxPct >= HIGH_USE
        ? { label: `Context ${Math.round(ctxPct * 100)}% full`, tone: "warning" }
        : null;

  const meta = (
    <ProfileDetails model={shownModel} contextWindow={contextWindow} ctxTokens={ctxTokens} budget={budget} accent={accent} />
  );

  const right = (
    <>
      {sessionsButton !== undefined ? (
        sessionsButton
      ) : (
        <SessionsButton
          profile={profile?.name}
          connectionId={connectionId}
          accent={accent}
          activeSessionId={activeSessionId}
          openTick={sessionsOpenTick}
          onChange={onChangeSession}
          onNew={onNewSession}
        />
      )}
      <SoundWave accent={accent} />
      <HeaderMenu
        paused={paused}
        onTogglePause={onTogglePause}
        onOpenSettings={onOpenSettings}
        autoRead={autoRead}
        onToggleAutoRead={onToggleAutoRead}
        onOpenSkills={onOpenSkills}
        onOpenMemory={onOpenMemory}
        onOpenTools={onOpenTools}
        onOpenSchedule={onOpenSchedule}
        onRefresh={onRefresh}
        canRefresh={activeSessionId != null || (sessionData?.turns?.length ?? 0) > 0}
      />
    </>
  );

  return (
    <ChatHeader
      kind="profile"
      id={profileLabel(profile?.name) || ""}
      accent={accent}
      shape={profile?.shape}
      bio={profile?.bio || profile?.public_bio}
      meta={meta}
      right={right}
      paused={paused}
      state={markState}
      flag={flag}
    />
  );
}
