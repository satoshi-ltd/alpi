import { useMemo } from "react";
import Tooltip from "../primitives/Tooltip.jsx";
import { relativeTime } from "../lib/time.js";
import styles from "./Sidebar.module.css";

export default function Sidebar({
  collapsed,
  profiles,
  workgroups,
  taskByWorkgroup = {},
  activityByWorkgroup = {},
  pendingProfile = null,
  view,
  onNewChat,
  onOpenProfile,
  onOpenWorkgroup,
}) {
  const activeProfileName =
    view.kind === "profile" ? view.profile : null;
  const activeWorkgroupId =
    view.kind === "workgroup" ? `${view.profile}/${view.id}` : null;
  const inEmpty = view.kind === "empty";

  const sortedProfiles = useMemo(() => {
    const arr = [...profiles];
    arr.sort((a, b) => {
      const aIncomplete = !a.model ? 1 : 0;
      const bIncomplete = !b.model ? 1 : 0;
      if (aIncomplete !== bIncomplete) return aIncomplete - bIncomplete;
      return recencyOf(b) - recencyOf(a);
    });
    return arr;
  }, [profiles]);

  const sortedWorkgroups = useMemo(() => {
    const arr = [...workgroups];
    arr.sort((a, b) => {
      const aPaused = a.paused ? 1 : 0;
      const bPaused = b.paused ? 1 : 0;
      if (aPaused !== bPaused) return aPaused - bPaused;
      return (b.mtime ?? 0) - (a.mtime ?? 0);
    });
    return arr;
  }, [workgroups]);

  return (
    <aside
      className={`${styles.sidebar} ${collapsed ? styles.collapsed : ""}`}
      aria-hidden={collapsed}
    >
      <div className={styles.inner}>
        <div className={styles.actions}>
          <button
            className={`${styles.newChatBtn} ${
              inEmpty ? styles.newChatBtnActive : ""
            }`}
            onClick={onNewChat}
          >
            <PlusIcon />
            <span>New Chat</span>
          </button>
        </div>

        <nav className={styles.nav}>
          {sortedProfiles.length > 0 && (
            <Section label="Alpis">
              {sortedProfiles.map((p) => (
                <ProfileRow
                  key={p.name}
                  profile={p}
                  active={activeProfileName === p.name}
                  pending={pendingProfile === p.name}
                  onClick={() => onOpenProfile(p)}
                />
              ))}
            </Section>
          )}

          {sortedWorkgroups.length > 0 && (
            <Section label="Workgroups">
              {sortedWorkgroups.map((w) => {
                const key = `${w.profile}/${w.id}`;
                const hub = profiles.find(
                  (p) => p.name === (w.hub_id ?? w.profile),
                );
                return (
                  <WorkgroupRow
                    key={key}
                    workgroup={w}
                    hubAccent={hub?.accent ?? null}
                    task={taskByWorkgroup[key] ?? null}
                    busy={!!activityByWorkgroup[key]}
                    active={activeWorkgroupId === key}
                    onClick={() => onOpenWorkgroup(w)}
                  />
                );
              })}
            </Section>
          )}
        </nav>
      </div>
    </aside>
  );
}

function recencyOf(profile) {
  return profile.latest_session?.mtime ?? 0;
}

function Section({ label, children }) {
  return (
    <div className={styles.section}>
      <div className={styles.sectionLabel}>{label}</div>
      {children}
    </div>
  );
}

function ProfileRow({ profile, active, pending, onClick }) {
  const recency = profile.latest_session?.mtime ?? 0;
  const incomplete = !profile.model;
  const trailing = pending ? (
    <StatusIcon kind="working" tooltip="thinking…" />
  ) : incomplete ? (
    <span className={styles.rowTag}>!</span>
  ) : recency > 0 ? (
    <span className={styles.rowTime}>{relativeTime(recency)}</span>
  ) : null;
  const accent = profile.accent || "var(--color-accent)";
  const activeStyle = active
    ? { backgroundColor: `color-mix(in srgb, ${accent} 14%, transparent)` }
    : undefined;
  return (
    <button
      className={`${styles.row} ${active ? styles.rowActive : ""}`}
      onClick={onClick}
      style={activeStyle}
      data-incomplete={incomplete ? "1" : "0"}
    >
      <span className={styles.iconCell}>
        <span
          className={styles.dot}
          style={
            profile.accent ? { backgroundColor: profile.accent } : undefined
          }
        />
      </span>
      <span className={styles.rowName}>{profile.name}</span>
      {trailing}
    </button>
  );
}

function WorkgroupRow({ workgroup, hubAccent, task, busy, active, onClick }) {
  const label = workgroup.name ?? workgroup.id;
  const mtime = workgroup.mtime ?? 0;
  const paused = !!workgroup.paused;
  const accent = hubAccent || "var(--color-accent)";

  // Status indicator with an accent dot fallback.
  let leading;
  if (busy) {
    leading = <StatusIcon kind="working" tooltip="Working…" />;
  } else if (paused) {
    leading = <StatusIcon kind="paused" tooltip="Paused" />;
  } else if (task?.state === "error") {
    leading = <StatusIcon kind="error" tooltip="Error" />;
  } else if (task?.state === "open") {
    leading = <StatusIcon kind="working" tooltip="Working…" />;
  } else if (task?.state === "done") {
    leading = <StatusIcon kind="done" tooltip="Task done" />;
  } else {
    leading = (
      <Tooltip text="Idle" direction="right">
        <span className={styles.idleDot} aria-label="Idle" />
      </Tooltip>
    );
  }

  const activeStyle = active
    ? { backgroundColor: `color-mix(in srgb, ${accent} 14%, transparent)` }
    : undefined;
  return (
    <button
      className={`${styles.row} ${active ? styles.rowActive : ""}`}
      onClick={onClick}
      style={activeStyle}
      data-paused={paused ? "1" : "0"}
    >
      <span className={styles.iconCell}>{leading}</span>
      <span className={styles.rowName}>#{label}</span>
      {mtime > 0 && (
        <span className={styles.rowTime}>{relativeTime(mtime)}</span>
      )}
    </button>
  );
}

function PlusIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path
        d="M7 2.5v9M2.5 7h9"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    </svg>
  );
}

function StatusIcon({ kind, tooltip }) {
  return (
    <Tooltip text={tooltip} direction="right">
      <span
        className={styles.statusIcon}
        data-kind={kind}
        aria-label={tooltip}
      >
        {kind === "done" && (
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
          <path
            d="M2 5.2l1.9 1.9L8 3"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      )}
      {kind === "working" && <span className={styles.statusPulse} />}
        {kind === "error" && (
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
            <circle cx="5" cy="5" r="4" fill="currentColor" />
            <rect x="4.4" y="2.4" width="1.2" height="3.4" rx="0.4" fill="var(--color-bg-solid)" />
            <rect x="4.4" y="6.6" width="1.2" height="1.2" rx="0.4" fill="var(--color-bg-solid)" />
          </svg>
        )}
        {kind === "paused" && (
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
            <rect x="2.5" y="2" width="1.6" height="6" rx="0.4" fill="currentColor" />
            <rect x="5.9" y="2" width="1.6" height="6" rx="0.4" fill="currentColor" />
          </svg>
        )}
      </span>
    </Tooltip>
  );
}
