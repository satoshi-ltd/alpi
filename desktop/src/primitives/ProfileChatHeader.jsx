import { ChatHeader, MeterChip, Mono } from "./index.js";
import { HeaderDetail } from "./ChatHeader.jsx";
import { profileLabel } from "../lib/profile-display.js";
import { modelLabel } from "../lib/modelLabel.js";
import SessionsButton from "./SessionsButton.jsx";
import SoundWave from "./SoundWave.jsx";
import HeaderMenu from "./HeaderMenu.jsx";
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

  const budgetPct = budgetSeg?.pct ?? 0;
  const flag = paused
    ? null
    : budgetPct >= HIGH_USE
      ? { label: `Daily budget ${Math.round(budgetPct * 100)}% used`, tone: budgetPct >= 1 ? "danger" : "warning" }
      : ctxPct >= HIGH_USE
        ? { label: `Context ${Math.round(ctxPct * 100)}% full`, tone: "warning" }
        : null;

  const meta = (
    <>
      {shownModel && (
        <HeaderDetail label="Model">
          <Mono className={styles.ink2}>{modelLabel(shownModel)}</Mono>
        </HeaderDetail>
      )}
      {shownModel && modelLabel(shownModel) !== shownModel && (
        <span className={styles.detailId} data-model-id="">{shownModel}</span>
      )}
      {contextWindow > 0 && (
        <HeaderDetail label="Context">
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
        </HeaderDetail>
      )}
      {budgetSeg && (
        <HeaderDetail label="Cost today">
          <MeterChip {...budgetSeg} color={accent} />
        </HeaderDetail>
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
