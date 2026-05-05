import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import Button from "../primitives/Button.jsx";
import NavRow, { Dot } from "../primitives/NavRow.jsx";
import Tooltip from "../primitives/Tooltip.jsx";
import { relativeTime } from "../lib/time.js";
import styles from "./Sidebar.module.css";

const MIN_VISIBLE_ALPIS = 3;
// Single fallback used until the first row is measured. Real row height is
// read from the DOM, so this only matters for the initial paint.
const ROW_HEIGHT_FALLBACK = 34;

// Returns [callbackRef, blockSize]. blockSize = offsetHeight + margin-bottom.
// Re-measures via ResizeObserver while attached; resets to 0 on detach.
function useMeasuredHeight() {
  const [size, setSize] = useState(0);
  const observerRef = useRef(null);
  const ref = useCallback((el) => {
    if (observerRef.current) {
      observerRef.current.disconnect();
      observerRef.current = null;
    }
    if (!el) {
      setSize(0);
      return;
    }
    const measure = () => {
      const cs = window.getComputedStyle(el);
      setSize(el.offsetHeight + (parseFloat(cs.marginBottom) || 0));
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    observerRef.current = ro;
  }, []);
  useEffect(() => () => observerRef.current?.disconnect(), []);
  return [ref, size];
}

export default function Sidebar({
  collapsed,
  profiles,
  workgroups,
  taskByWorkgroup = {},
  activityByWorkgroup = {},
  pendingProfile = null,
  view,
  pinned = { profiles: [], workgroups: [] },
  onNewChat,
  onOpenProfile,
  onOpenWorkgroup,
  onTogglePin,
}) {
  const activeProfileName =
    view.kind === "profile" ? view.profile : null;
  const activeWorkgroupId =
    view.kind === "workgroup" ? `${view.profile}/${view.id}` : null;
  const inEmpty = view.kind === "empty";

  const pinnedProfileNames = pinned.profiles ?? [];
  const pinnedWorkgroupKeys = pinned.workgroups ?? [];

  const sortedProfiles = useMemo(() => {
    const arr = profiles.filter((p) => !pinnedProfileNames.includes(p.name));
    arr.sort((a, b) => {
      const aIncomplete = !a.model ? 1 : 0;
      const bIncomplete = !b.model ? 1 : 0;
      if (aIncomplete !== bIncomplete) return aIncomplete - bIncomplete;
      return recencyOf(b) - recencyOf(a);
    });
    return arr;
  }, [profiles, pinnedProfileNames]);

  const sortedWorkgroups = useMemo(() => {
    const arr = workgroups.filter(
      (w) => !pinnedWorkgroupKeys.includes(`${w.profile}/${w.id}`),
    );
    arr.sort((a, b) => {
      const aPaused = a.paused ? 1 : 0;
      const bPaused = b.paused ? 1 : 0;
      if (aPaused !== bPaused) return aPaused - bPaused;
      return (b.mtime ?? 0) - (a.mtime ?? 0);
    });
    return arr;
  }, [workgroups, pinnedWorkgroupKeys]);

  const pinnedProfiles = useMemo(
    () =>
      pinnedProfileNames
        .map((name) => profiles.find((p) => p.name === name))
        .filter(Boolean),
    [pinnedProfileNames, profiles],
  );

  const pinnedWorkgroups = useMemo(
    () =>
      pinnedWorkgroupKeys
        .map((key) => workgroups.find((w) => `${w.profile}/${w.id}` === key))
        .filter(Boolean),
    [pinnedWorkgroupKeys, workgroups],
  );

  // Lookup table: profile name → accent. Stable per `profiles` reference,
  // so memoized WorkgroupRow only re-renders when its hub accent actually changes.
  const hubAccentByProfile = useMemo(() => {
    const map = {};
    for (const p of profiles) map[p.name] = p.accent ?? null;
    return map;
  }, [profiles]);

  const hasPinned = pinnedProfiles.length > 0 || pinnedWorkgroups.length > 0;

  // Measure the actual rendered chrome around the alpis list. We do not
  // hard-code paddings or label heights — they come from the live DOM, so the
  // cap auto-adjusts if NavRow / Section CSS changes.
  const navRef = useRef(null);
  const [navHeight, setNavHeight] = useState(0);
  useEffect(() => {
    const el = navRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      setNavHeight(entry.contentRect.height);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const [pinnedSectionRef, pinnedSectionH] = useMeasuredHeight();
  const [workgroupsSectionRef, workgroupsSectionH] = useMeasuredHeight();
  const [alpisLabelRef, alpisLabelH] = useMeasuredHeight();
  const [showMoreRef, showMoreH] = useMeasuredHeight();
  const [firstRowRef, firstRowH] = useMeasuredHeight();
  const rowHeight = firstRowH || ROW_HEIGHT_FALLBACK;

  const maxAlpisVisible = useMemo(() => {
    if (!navHeight) return sortedProfiles.length;
    const available =
      navHeight - pinnedSectionH - workgroupsSectionH - alpisLabelH - showMoreH;
    return Math.max(MIN_VISIBLE_ALPIS, Math.floor(available / rowHeight));
  }, [
    navHeight,
    pinnedSectionH,
    workgroupsSectionH,
    alpisLabelH,
    showMoreH,
    rowHeight,
  ]);

  const [showAllAlpis, setShowAllAlpis] = useState(false);
  const alpisOverflow =
    sortedProfiles.length > maxAlpisVisible && !showAllAlpis;
  const visibleAlpis = alpisOverflow
    ? sortedProfiles.slice(0, maxAlpisVisible)
    : sortedProfiles;
  const hiddenAlpisCount = sortedProfiles.length - maxAlpisVisible;

  const renderProfileRow = (p, keyPrefix = "") => (
    <ProfileRow
      key={keyPrefix + p.name}
      profile={p}
      active={activeProfileName === p.name}
      pending={pendingProfile === p.name}
      isPinned={pinnedProfileNames.includes(p.name)}
      onOpen={onOpenProfile}
      onTogglePin={onTogglePin}
    />
  );

  const renderWorkgroupRow = (w, keyPrefix = "") => {
    const key = `${w.profile}/${w.id}`;
    return (
      <WorkgroupRow
        key={keyPrefix + key}
        workgroup={w}
        hubAccent={hubAccentByProfile[w.hub_id ?? w.profile] ?? null}
        task={taskByWorkgroup[key] ?? null}
        busy={!!activityByWorkgroup[key]}
        active={activeWorkgroupId === key}
        isPinned={pinnedWorkgroupKeys.includes(key)}
        onOpen={onOpenWorkgroup}
        onTogglePin={onTogglePin}
      />
    );
  };

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

        <nav ref={navRef} className={styles.nav}>
          {hasPinned && (
            <Section label="Pinned" containerRef={pinnedSectionRef}>
              {pinnedProfiles.map((p) => renderProfileRow(p, "pin:"))}
              {pinnedWorkgroups.map((w) => renderWorkgroupRow(w, "pin:"))}
            </Section>
          )}

          {sortedProfiles.length > 0 && (
            <Section label="Alpis" labelRef={alpisLabelRef}>
              {visibleAlpis.map((p, i) =>
                i === 0 ? (
                  <div key={`measure:${p.name}`} ref={firstRowRef}>
                    {renderProfileRow(p)}
                  </div>
                ) : (
                  renderProfileRow(p)
                ),
              )}
              {(alpisOverflow || showAllAlpis) && (
                <div ref={showMoreRef} className={styles.showMoreWrap}>
                  <Button
                    size="sm"
                    onClick={() => setShowAllAlpis((v) => !v)}
                  >
                    {showAllAlpis
                      ? "Show less"
                      : `Show ${hiddenAlpisCount} more`}
                  </Button>
                </div>
              )}
            </Section>
          )}

          {sortedWorkgroups.length > 0 && (
            <Section label="Workgroups" containerRef={workgroupsSectionRef}>
              {sortedWorkgroups.map((w) => renderWorkgroupRow(w))}
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

function Section({ label, children, containerRef = null, labelRef = null }) {
  return (
    <div ref={containerRef} className={styles.section}>
      <div ref={labelRef} className={styles.sectionLabel}>{label}</div>
      {children}
    </div>
  );
}

function PinAction({ isPinned, onClick }) {
  return (
    <span className={`${styles.pinWrap} ${isPinned ? styles.pinWrapPinned : ""}`}>
      <Button
        size="xs"
        icon={<PinIcon filled={isPinned} />}
        onClick={onClick}
        title={isPinned ? "Unpin" : "Pin"}
        tooltipDirection="up"
      />
    </span>
  );
}

const ProfileRow = memo(function ProfileRow({
  profile,
  active,
  pending,
  isPinned,
  onOpen,
  onTogglePin,
}) {
  const handleClick = useCallback(() => onOpen(profile), [onOpen, profile]);
  const handleTogglePin = useCallback(
    () => onTogglePin?.("profiles", profile.name),
    [onTogglePin, profile.name],
  );

  const recency = profile.latest_session?.mtime ?? 0;
  const incomplete = !profile.model;
  const trailing = pending ? (
    <StatusIcon kind="working" tooltip="thinking…" />
  ) : incomplete ? (
    <span className={styles.rowTag}>!</span>
  ) : recency > 0 ? (
    <span className={styles.rowTime}>{relativeTime(recency)}</span>
  ) : null;

  const dot = <Dot color={profile.accent} />;
  const leading = profile.bio ? (
    <Tooltip text={profile.bio} direction="right">
      {dot}
    </Tooltip>
  ) : (
    dot
  );

  return (
    <div className={styles.rowWrap}>
      <NavRow
        active={active}
        accent={profile.accent || "var(--color-accent)"}
        muted={incomplete}
        leading={leading}
        trailing={trailing}
        onClick={handleClick}
      >
        {profile.name}
      </NavRow>
      <PinAction isPinned={isPinned} onClick={handleTogglePin} />
    </div>
  );
});

const WorkgroupRow = memo(function WorkgroupRow({
  workgroup,
  hubAccent,
  task,
  busy,
  active,
  isPinned,
  onOpen,
  onTogglePin,
}) {
  const handleClick = useCallback(() => onOpen(workgroup), [onOpen, workgroup]);
  const handleTogglePin = useCallback(
    () => onTogglePin?.("workgroups", `${workgroup.profile}/${workgroup.id}`),
    [onTogglePin, workgroup.profile, workgroup.id],
  );

  const label = workgroup.name ?? workgroup.id;
  const mtime = workgroup.mtime ?? 0;
  const paused = !!workgroup.paused;

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

  const trailing = mtime > 0 ? (
    <span className={styles.rowTime}>{relativeTime(mtime)}</span>
  ) : null;

  return (
    <div className={styles.rowWrap}>
      <NavRow
        active={active}
        accent={hubAccent || "var(--color-accent)"}
        muted={paused}
        leading={leading}
        trailing={trailing}
        onClick={handleClick}
      >
        #{label}
      </NavRow>
      <PinAction isPinned={isPinned} onClick={handleTogglePin} />
    </div>
  );
});

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

function PinIcon({ filled }) {
  return (
    <svg
      width="13"
      height="13"
      viewBox="0 0 24 24"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth="2.2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 17v5" fill="none" />
      <path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V17a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-1.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 8.24V6a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v2.24A2 2 0 0 1 9 10.76Z" />
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
