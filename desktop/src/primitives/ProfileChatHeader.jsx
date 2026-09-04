import { ChatHeader, MeterChip, Mono } from "./index.js";
import { profileLabel } from "../lib/profile-display.js";
import { modelLabel } from "../lib/modelLabel.js";
import SessionsButton from "./SessionsButton.jsx";
import SoundWave from "./SoundWave.jsx";
import HeaderMenu from "./HeaderMenu.jsx";
import Tip from "./Tip.jsx";
import styles from "./ProfileChatHeader.module.css";

function fmtCount(n) {
  if (!n) return "0";
  if (n < 1000) return `${n}`;
  if (n < 1_000_000) return `${(n / 1000).toFixed(n < 10_000 ? 1 : 0)}K`;
  return `${(n / 1_000_000).toFixed(1)}M`;
}

function fmtCost(n) {
  if (n == null || n <= 0) return "";
  if (n < 0.01) return `$${n.toFixed(4)}`;
  return `$${n.toFixed(2)}`;
}

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
}) {
  const accent = profile?.accent || "var(--accent)";
  const shownModel = model || profile?.model;
  const ctxTokens = liveCtxTokens ?? sessionData?.last_ctx_tokens ?? 0;
  const ctxPct = contextWindow > 0 ? Math.min(1, ctxTokens / contextWindow) : 0;

  const capUsd = profile?.budget_daily_usd;
  const usedUsd = profile?.budget_used_usd ?? 0;
  let budgetSeg = null;
  if (capUsd != null && capUsd > 0) {
    budgetSeg = {
      value: (
        <>
          {fmtCost(usedUsd)}
          <span className={styles.ink3}>/${capUsd.toFixed(2)}</span>
        </>
      ),
      pct: Math.min(1, usedUsd / capUsd),
      tip: "Daily budget",
    };
  }

  const meta = (
    <>
      {shownModel && (
        <Tip text={shownModel} side="down" wide>
          <Mono className={styles.ink2}>{modelLabel(shownModel)}</Mono>
        </Tip>
      )}
      {shownModel && contextWindow > 0 && (
        <span className="sep" aria-hidden />
      )}
      {contextWindow > 0 && (
        <MeterChip
          value={
            <>
              {fmtCount(ctxTokens)}
              <span className={styles.ink3}>/{fmtCount(contextWindow)}</span>
            </>
          }
          pct={ctxPct}
          color={accent}
          tip="Context window"
        />
      )}
      {budgetSeg && (
        <>
          <span className="sep" aria-hidden />
          <MeterChip {...budgetSeg} color={accent} />
        </>
      )}
    </>
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
      bio={profile?.bio || profile?.public_bio}
      meta={meta}
      right={right}
    />
  );
}
