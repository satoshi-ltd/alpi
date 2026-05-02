import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import SessionsDropdown from "./SessionsDropdown.jsx";
import Button from "../primitives/Button.jsx";
import ProgressBar from "../primitives/ProgressBar.jsx";
import styles from "./AppHeader.module.css";

const CTX_CACHE = new Map();

function useCtxWindow(profileName, model) {
  const [win, setWin] = useState(() => {
    const key = `${profileName}|${model}`;
    return CTX_CACHE.get(key) ?? null;
  });
  useEffect(() => {
    if (!profileName || !model) return;
    const key = `${profileName}|${model}`;
    const cached = CTX_CACHE.get(key);
    if (cached != null) {
      setWin(cached);
      return;
    }
    let cancelled = false;
    invoke("resolve_ctx_window", { profile: profileName, model })
      .then((n) => {
        if (cancelled) return;
        const v = Number(n) || 200_000;
        CTX_CACHE.set(key, v);
        setWin(v);
      })
      .catch(() => {
        if (!cancelled) setWin(200_000);
      });
    return () => {
      cancelled = true;
    };
  }, [profileName, model]);
  return win ?? 200_000;
}

export default function AppHeader({
  view,
  collapsed,
  profiles = [],
  activeProfile,
  activeWorkgroup,
  settingsWorkgroup,
  activeTask,
  sessionData,
  onToggleSidebar,
  onChangeSession,
  onNewSession,
  onCloseSettings,
}) {
  const hubProfile =
    activeWorkgroup &&
    profiles.find((p) => p.name === activeWorkgroup.profile);
  return (
    <header
      className={styles.header}
      data-drag
      data-sidebar-collapsed={collapsed ? "1" : "0"}
      data-view={view.kind}
    >
      <div className={styles.left} data-drag>
        {view.kind === "settings" ? (
          <>
            <Button
              icon={<BackIcon />}
              onClick={onCloseSettings}
              title="Back"
            />
            <span className={styles.title}>Settings</span>
          </>
        ) : (
          <Button
            icon={<SidebarIcon />}
            onClick={onToggleSidebar}
            title={
              <>
                {collapsed ? "Show sidebar" : "Hide sidebar"}{" "}
                <kbd>⌘B</kbd>
              </>
            }
          />
        )}
      </div>

      <div className={styles.main} data-drag>
        <div className={styles.center} data-drag>
          {view.kind === "profile" && activeProfile && (
            <ProfileTitle profile={activeProfile} sessionData={sessionData} />
          )}
          {view.kind === "workgroup" && activeWorkgroup && (
            <WorkgroupTitle workgroup={activeWorkgroup} hub={hubProfile} />
          )}
          {view.kind === "settings" && settingsWorkgroup && (
            <WorkgroupTitle
              workgroup={settingsWorkgroup}
              hub={profiles.find(
                (p) =>
                  p.name === (settingsWorkgroup.hub_id ?? settingsWorkgroup.profile),
              )}
            />
          )}
          {view.kind === "settings" && !settingsWorkgroup && activeProfile && (
            <SettingsTitle profile={activeProfile} />
          )}
        </div>

        <div className={styles.right}>
          {view.kind === "profile" && activeProfile && (
            <>
              {(activeProfile.counts?.sessions ?? 0) > 0 && (
                <SessionsDropdown
                  profile={activeProfile.name}
                  activeSessionId={view.sessionId}
                  onChange={onChangeSession}
                />
              )}
              <Button
                icon={<PlusIcon />}
                onClick={onNewSession}
                title={
                  <>
                    New session <kbd>⌘N</kbd>
                  </>
                }
                tooltipAlign="end"
              />
            </>
          )}
          {view.kind === "workgroup" && activeWorkgroup && (
            <>
              {activeWorkgroup.briefing && (
                <Button
                  icon={<QuestionIcon />}
                  title={activeWorkgroup.briefing}
                  tooltipAlign="end"
                />
              )}
              {activeTask && activeTask.state === "open" && (
                <Button
                  icon={<PulseDot />}
                  title={<TaskTooltip task={activeTask} />}
                  tooltipAlign="end"
                />
              )}
              {activeTask && activeTask.state === "done" && (
                <Button
                  icon={
                    <span style={{ color: "var(--color-success, #30d158)" }}>
                      <CheckIcon />
                    </span>
                  }
                  title={<TaskTooltip task={activeTask} />}
                  tooltipAlign="end"
                />
              )}
            </>
          )}
        </div>
      </div>
    </header>
  );
}

function ProfileTitle({ profile, sessionData }) {
  const ctxTokens = sessionData?.last_ctx_tokens ?? 0;
  const cost = sessionData?.cost_usd ?? 0;
  const win = useCtxWindow(profile.name, profile.model);
  const pct = win > 0 ? Math.min(100, Math.round((ctxTokens / win) * 100)) : 0;

  // Budget uses either USD or tokens, never both.
  const capUsd = profile.budget_daily_usd;
  const capTokens = profile.budget_daily_tokens;
  const usedUsd = profile.budget_used_usd ?? 0;
  const usedTokens = profile.budget_used_tokens ?? 0;
  let budgetSeg = null;
  if (capUsd != null && capUsd > 0) {
    const bPct = Math.min(100, Math.round((usedUsd / capUsd) * 100));
    budgetSeg = {
      label: `${formatCost(usedUsd)}/$${capUsd.toFixed(2)}`,
      value: usedUsd,
      max: capUsd,
      pct: bPct,
    };
  } else if (capTokens != null && capTokens > 0) {
    const bPct = Math.min(100, Math.round((usedTokens / capTokens) * 100));
    budgetSeg = {
      label: `${fmtCount(usedTokens)}/${fmtCount(capTokens)} tok`,
      value: usedTokens,
      max: capTokens,
      pct: bPct,
    };
  }

  return (
    <div className={styles.profileTitle}>
      <span
        className={styles.dot}
        style={profile.accent ? { backgroundColor: profile.accent } : undefined}
      />
      <div className={styles.profileText}>
        <div className={styles.title}>{profile.name}</div>
        {sessionData ? (
          <div className={styles.meta}>
            {profile.model && (
              <>
                <span>{profile.model}</span>
                <span className={styles.sep}>·</span>
              </>
            )}
            <span>{fmtCount(ctxTokens)}/{fmtCount(win)}</span>
            <ProgressBar
              value={ctxTokens}
              max={win}
              cells={8}
              accent={profile.accent}
            />
            <span>{pct}%</span>
            {cost > 0 && (
              <>
                <span className={styles.sep}>·</span>
                <span>{formatCost(cost)}</span>
              </>
            )}
            {budgetSeg && (
              <>
                <span className={styles.sep}>·</span>
                <span>{budgetSeg.label}</span>
                <ProgressBar
                  value={budgetSeg.value}
                  max={budgetSeg.max}
                  cells={8}
                  accent={profile.accent}
                />
                <span>{budgetSeg.pct}%</span>
              </>
            )}
          </div>
        ) : profile.model ? (
          <div className={styles.meta}>{profile.model}</div>
        ) : null}
      </div>
    </div>
  );
}

function SettingsTitle({ profile }) {
  return (
    <div className={styles.profileTitle}>
      <span
        className={styles.dot}
        style={profile.accent ? { backgroundColor: profile.accent } : undefined}
      />
      <div className={styles.profileText}>
        <div className={styles.title}>{profile.name}</div>
      </div>
    </div>
  );
}

function WorkgroupTitle({ workgroup, hub }) {
  const spent = workgroup.spent_usd ?? 0;
  const budget = workgroup.budget_usd ?? 0;
  return (
    <div className={styles.profileTitle}>
      <span
        className={styles.dot}
        style={hub?.accent ? { backgroundColor: hub.accent } : undefined}
      />
      <div className={styles.profileText}>
        <div className={styles.title}>{workgroup.name ?? workgroup.id}</div>
        <div className={styles.meta}>
          @{workgroup.hub_id ?? workgroup.profile}
          <span className={styles.sep}>·</span>
          {workgroup.members} {workgroup.members === 1 ? "member" : "members"}
          {budget > 0 && (
            <>
              <span className={styles.sep}>·</span>
              <span>${spent.toFixed(2)}/${budget.toFixed(2)}</span>
              <ProgressBar value={spent} max={budget} />
            </>
          )}
          {workgroup.paused && (
            <>
              <span className={styles.sep}>·</span>
              <span>paused</span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function BackIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path
        d="M10 3.5 5.5 8l4.5 4.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function SidebarIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <rect x="2" y="3" width="12" height="10" rx="1.5" stroke="currentColor" strokeWidth="1.3" />
      <line x1="6" y1="3.5" x2="6" y2="12.5" stroke="currentColor" strokeWidth="1.3" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M7 2.5v9M2.5 7h9" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function QuestionIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth="1.3" />
      <path
        d="M5.4 5.5c0-.9.7-1.6 1.6-1.6s1.6.7 1.6 1.6c0 .8-.6 1.1-1.1 1.4-.4.3-.5.6-.5 1v.3"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        fill="none"
      />
      <circle cx="7" cy="9.9" r="0.55" fill="currentColor" />
    </svg>
  );
}

function PulseDot() {
  return (
    <span className={styles.pulseDot} aria-hidden />
  );
}

function TaskTooltip({ task }) {
  // Show the task first and the `#done` result below.
  return (
    <>
      <strong>{task.text}</strong>
      {task.state === "done" && task.result && (
        <span className={styles.tooltipBlock}>{task.result}</span>
      )}
    </>
  );
}

function CheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path
        d="M3 7.4l2.8 2.6L11 4.6"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function fmtCount(n) {
  if (!n) return "0";
  if (n < 1000) return `${n}`;
  if (n < 1_000_000) return `${(n / 1000).toFixed(n < 10_000 ? 1 : 0)}K`;
  return `${(n / 1_000_000).toFixed(1)}M`;
}

function formatCost(n) {
  if (n <= 0) return "";
  if (n < 0.01) return `$${n.toFixed(4)}`;
  return `$${n.toFixed(2)}`;
}
