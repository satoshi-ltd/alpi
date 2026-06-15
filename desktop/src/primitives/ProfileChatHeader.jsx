import { ChatHeader } from "./index.js";
import {
  Btn,
  IconBtn,
  Mono,
  MeterChip,
  RefreshButton,
  Tip,
  BlocksIcon,
  CpuIcon,
  GearIcon,
  PauseIcon,
  PlayIcon,
  WrenchIcon,
} from "./index.js";
import SessionsButton from "./SessionsButton.jsx";
import SoundWave from "./SoundWave.jsx";
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
  contextWindow = 200_000,
  activeSessionId,
  onOpenSkills,
  onOpenMemory,
  onOpenTools,
  onOpenSettings,
  onRefresh,
  paused = false,
  onTogglePause,
  onNewSession,
  onChangeSession,
  sessionsButton,
}) {
  const accent = profile?.accent || "var(--accent)";
  const ctxTokens = sessionData?.last_ctx_tokens ?? 0;
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
      tip: `Daily budget — spent ${fmtCost(usedUsd)} of $${capUsd.toFixed(2)} cap today`,
    };
  }

  const meta = (
    <>
      {profile?.model && <Mono className={styles.ink2}>{profile.model}</Mono>}
      {profile?.model && contextWindow > 0 && (
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
          tip={`Context window — ${fmtCount(ctxTokens)} of ${fmtCount(contextWindow)} tokens in use`}
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
          accent={accent}
          activeSessionId={activeSessionId}
          onChange={onChangeSession}
          onNew={onNewSession}
        />
      )}
      <span className={styles.divider} aria-hidden />
      {onOpenSkills && (
        <Tip text="Skills" side="r">
          <IconBtn onClick={onOpenSkills} aria-label="Skills"><BlocksIcon /></IconBtn>
        </Tip>
      )}
      {onOpenMemory && (
        <Tip text="Memory" side="r">
          <IconBtn onClick={onOpenMemory} aria-label="Memory"><CpuIcon /></IconBtn>
        </Tip>
      )}
      {onOpenTools && (
        <Tip text="Tools" side="r">
          <IconBtn onClick={onOpenTools} aria-label="Tools"><WrenchIcon /></IconBtn>
        </Tip>
      )}
      <span className={styles.divider} aria-hidden />
      {onTogglePause && (
        <Btn variant="ghost" onClick={onTogglePause} title={paused ? "Resume profile" : "Pause profile"}>
          {paused ? <PlayIcon /> : <PauseIcon />}
          <span>{paused ? "Resume" : "Pause"}</span>
        </Btn>
      )}
      {onOpenSettings && (
        <Tip text="Profile settings" side="r">
          <IconBtn onClick={onOpenSettings} aria-label="Profile settings"><GearIcon /></IconBtn>
        </Tip>
      )}
      <SoundWave accent={accent} />
      {onRefresh && (sessionData?.turns?.length ?? 0) > 0 && (
        <RefreshButton onClick={onRefresh} />
      )}
    </>
  );

  return (
    <ChatHeader
      kind="profile"
      id={profile?.name || ""}
      accent={accent}
      bio={profile?.bio || profile?.public_bio}
      meta={meta}
      right={right}
    />
  );
}
