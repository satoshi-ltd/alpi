import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import ConnectionSwitcher from "./ConnectionSwitcher.jsx";
import VersionButton from "./VersionButton.jsx";
import { SidebarRow, SectionLabel, ContextMenu } from "../primitives/index.js";
import {
  AutoIcon,
  BellIcon,
  Btn,
  IconBtn,
  Kbd,
  MoonIcon,
  SunIcon,
  Tip,
  ArrowLeftIcon,
  GearIcon,
  PauseIcon,
  PinIcon,
  PinOffIcon,
  PlusIcon,
  SearchIcon,
  StatusIcon,
  TrashIcon,
  ArchiveIcon,
} from "../primitives/index.js";
import { relativeTime } from "../lib/time.js";
import { cycleTheme, nextTheme, useTheme } from "../lib/theme.js";
import { profileLabel } from "../lib/profile-display.js";
import {
  useReadState,
  markProfileRead,
  markWorkgroupRead,
} from "../hooks/useReadState.js";
import { orderedSidebarProfiles } from "../lib/profile-order.js";
import styles from "./Sidebar.module.css";

const MIN_VISIBLE_ALPIS = 3;
const ROW_HEIGHT_FALLBACK = 34;

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

function Sidebar({
  profiles,
  workgroups,
  taskByWorkgroup = {},
  activityByWorkgroup = {},
  pendingProfile = null,
  view,
  settingsTarget = null,
  pinned = { profiles: [], workgroups: [] },
  hostConnections,
  daemonOffline = false,
  onNewChat,
  onNewProfile,
  onNewWorkgroup,
  onOpenProfile,
  onOpenWorkgroup,
  onOpenSettings,
  onOpenPalette,
  onCloseSettings,
  onSetSettingsTarget,
  onTogglePin,
  onSetHostConnection,
  onAddHostConnection,
  onForgetHostConnection,
  onRefreshHostConnectionStatus,
  autoOpenConnectionSwitcher = false,
  onOpenNotifications,
  notificationsUnread = 0,
}) {
  const inSettings = view.kind === "settings";

  const connId = hostConnections?.active_id ?? "local";
  const { checkProfile: checkUnread, checkWorkgroup: checkWorkgroupUnread } =
    useReadState(connId);
  const openProfile = inSettings
    ? (p) => onSetSettingsTarget?.({ kind: "profile", id: p.name })
    : (p) => {
        markProfileRead(connId, p.name);
        onOpenProfile?.(p);
      };
  const openWorkgroup = inSettings
    ? (w) => onSetSettingsTarget?.({ kind: "workgroup", id: w.id, profile: w.profile })
    : (w) => {
        markWorkgroupRead(connId, w.profile, w.id);
        onOpenWorkgroup?.(w);
      };
  const activeProfileName = inSettings
    ? settingsTarget?.kind === "profile"
      ? settingsTarget.id
      : null
    : view.kind === "profile"
      ? view.profile
      : null;
  const activeWorkgroupId = inSettings
    ? settingsTarget?.kind === "workgroup"
      ? `${settingsTarget.profile || ""}/${settingsTarget.id}`
      : null
    : view.kind === "workgroup"
      ? `${view.profile}/${view.id}`
      : null;
  const inEmpty = view.kind === "empty";

  const pinnedProfileNames = pinned.profiles ?? [];
  const pinnedWorkgroupKeys = pinned.workgroups ?? [];

  const sortedProfiles = useMemo(
    () =>
      orderedSidebarProfiles(profiles, pinnedProfileNames).filter(
        (p) => !pinnedProfileNames.includes(p.name),
      ),
    [profiles, pinnedProfileNames],
  );

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

  const pinnedProfiles = useMemo(() => {
    const list = pinnedProfileNames
      .map((name) => profiles.find((p) => p.name === name))
      .filter(Boolean);
    list.sort((a, b) => {
      const aBad = !a.model ? 1 : 0;
      const bBad = !b.model ? 1 : 0;
      if (aBad !== bBad) return aBad - bBad;
      const ra = a.latest_session?.updated_at ?? a.latest_session?.started_at ?? a.latest_session?.mtime ?? 0;
      const rb = b.latest_session?.updated_at ?? b.latest_session?.started_at ?? b.latest_session?.mtime ?? 0;
      return rb - ra;
    });
    return list;
  }, [pinnedProfileNames, profiles]);

  const pinnedWorkgroups = useMemo(() => {
    const list = pinnedWorkgroupKeys
      .map((key) => workgroups.find((w) => `${w.profile}/${w.id}` === key))
      .filter(Boolean);
    list.sort((a, b) => {
      const aPaused = a.paused ? 1 : 0;
      const bPaused = b.paused ? 1 : 0;
      if (aPaused !== bPaused) return aPaused - bPaused;
      return (b.mtime ?? 0) - (a.mtime ?? 0);
    });
    return list;
  }, [pinnedWorkgroupKeys, workgroups]);

  const hubAccentByProfile = useMemo(() => {
    const map = {};
    for (const p of profiles) map[p.name] = p.accent ?? null;
    return map;
  }, [profiles]);

  const hasPinned = pinnedProfiles.length > 0 || pinnedWorkgroups.length > 0;

  const pinnedItems = useMemo(() => {
    const items = [
      ...pinnedProfiles.map((p) => ({
        kind: "profile",
        item: p,
        ts: p.latest_session?.updated_at ?? p.latest_session?.started_at ?? p.latest_session?.mtime ?? 0,
        bad: !p.model ? 1 : 0,
      })),
      ...pinnedWorkgroups.map((w) => ({
        kind: "workgroup",
        item: w,
        ts: w.mtime ?? 0,
        bad: w.paused ? 1 : 0,
      })),
    ];
    items.sort((a, b) => {
      if (a.bad !== b.bad) return a.bad - b.bad;
      return b.ts - a.ts;
    });
    return items;
  }, [pinnedProfiles, pinnedWorkgroups]);

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

  const [ctxMenu, setCtxMenu] = useState(null);
  const closeCtxMenu = useCallback(() => setCtxMenu(null), []);
  const canOpenSettings = Boolean(onOpenSettings);

  const openProfileCtx = useCallback(
    (e, profile) => {
      e.preventDefault();
      const pinned = pinnedProfileNames.includes(profile.name);
      const items = [
        {
          label: pinned ? "Unpin from top" : "Pin to top",
          icon: pinned ? <PinOffIcon /> : <PinIcon />,
          onClick: () => onTogglePin?.("profiles", profile.name),
        },
      ];
      if (canOpenSettings) {
        items.push(
          { kind: "separator" },
          {
            label: "Open settings",
            icon: <GearIcon />,
            shortcut: "⌘,",
            onClick: () => onSetSettingsTarget?.({ kind: "profile", id: profile.name }),
          },
          { kind: "separator" },
          {
            label: "Delete profile…",
            icon: <TrashIcon />,
            kind: "danger",
            onClick: () => onSetSettingsTarget?.({ kind: "profile", id: profile.name }),
          },
        );
      }
      setCtxMenu({ x: e.clientX, y: e.clientY, items });
    },
    [pinnedProfileNames, onTogglePin, onSetSettingsTarget, canOpenSettings],
  );

  const openWorkgroupCtx = useCallback(
    (e, workgroup) => {
      e.preventDefault();
      const key = `${workgroup.profile}/${workgroup.id}`;
      const pinned = pinnedWorkgroupKeys.includes(key);
      const items = [
        {
          label: pinned ? "Unpin from top" : "Pin to top",
          icon: pinned ? <PinOffIcon /> : <PinIcon />,
          onClick: () => onTogglePin?.("workgroups", key),
        },
      ];
      if (canOpenSettings) {
        items.push(
          { kind: "separator" },
          {
            label: "Open settings",
            icon: <GearIcon />,
            shortcut: "⌘,",
            onClick: () =>
              onSetSettingsTarget?.({
                kind: "workgroup",
                id: workgroup.id,
                profile: workgroup.profile,
              }),
          },
          {
            label: "Archive workgroup",
            icon: <ArchiveIcon />,
            onClick: () => window.notify?.(`#${workgroup.id} archived`, { kind: "info" }),
          },
          { kind: "separator" },
          {
            label: "Delete workgroup…",
            icon: <TrashIcon />,
            kind: "danger",
            onClick: () =>
              onSetSettingsTarget?.({
                kind: "workgroup",
                id: workgroup.id,
                profile: workgroup.profile,
              }),
          },
        );
      }
      setCtxMenu({ x: e.clientX, y: e.clientY, items });
    },
    [pinnedWorkgroupKeys, onTogglePin, onSetSettingsTarget, canOpenSettings],
  );

  const renderProfileRow = (p, keyPrefix = "") => (
    <ProfileRow
      key={keyPrefix + p.name}
      profile={p}
      active={activeProfileName === p.name}
      pending={pendingProfile === p.name}
      isPinned={pinnedProfileNames.includes(p.name)}
      connId={connId}
      checkUnread={checkUnread}
      onOpen={openProfile}
      onTogglePin={onTogglePin}
      onContextMenu={openProfileCtx}
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
        connId={connId}
        checkUnread={checkWorkgroupUnread}
        onOpen={openWorkgroup}
        onTogglePin={onTogglePin}
        onContextMenu={openWorkgroupCtx}
      />
    );
  };

  return (
    <aside className={styles.sidebar}>
      <div className={styles.titlebarSpacer} aria-hidden data-drag />
      {inSettings && (
        <div className={styles.settingsHeader}>
          <Tip text="Back to chat" side="l">
            <IconBtn onClick={onCloseSettings} aria-label="Back to chat">
              <ArrowLeftIcon />
            </IconBtn>
          </Tip>
          <span className={styles.settingsTitle}>
            Settings
          </span>
          <span className={styles.spacer} />
          <Kbd>⌘,</Kbd>
        </div>
      )}
      <div className={styles.inner}>
        <div className={styles.actions}>
          <div className={styles.actionSection}>
            <ConnectionSwitcher
              className={styles.connectionSlot}
              state={hostConnections}
              onSetActive={onSetHostConnection}
              onAddRemote={onAddHostConnection}
              onForget={onForgetHostConnection}
              onOpen={onRefreshHostConnectionStatus}
              autoOpenSignal={autoOpenConnectionSwitcher}
            />
          </div>
          {!daemonOffline && !inSettings && (
            <button
              type="button"
              className="ds-sb-row"
              data-active={inEmpty || undefined}
              onClick={onNewChat}
              style={inEmpty ? { background: "var(--selected)" } : undefined}
            >
              <PlusIcon />
              <span className={styles.rowLabel}>New chat</span>
              <span className={styles.kbdGroup} aria-hidden>
                <Kbd>⌘</Kbd>
                <Kbd>N</Kbd>
              </span>
            </button>
          )}
        </div>

        <nav ref={navRef} className={styles.nav}>
          {hasPinned && (
            <Section label="Pinned" containerRef={pinnedSectionRef}>
              {pinnedItems.map((it) =>
                it.kind === "profile"
                  ? renderProfileRow(it.item, "pin:")
                  : renderWorkgroupRow(it.item, "pin:"),
              )}
            </Section>
          )}

          {sortedProfiles.length > 0 && (
            <Section
              label={inSettings ? "Profiles" : "Alpis"}
              labelRef={alpisLabelRef}
              right={
                onNewProfile ? (
                  <SectionAddButton
                    tip="New profile"
                    ariaLabel="New profile"
                    onClick={onNewProfile}
                  />
                ) : null
              }
            >
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
                  <Btn variant="ghost" onClick={() => setShowAllAlpis((v) => !v)}>
                    {showAllAlpis
                      ? "Show less"
                      : `Show ${hiddenAlpisCount} more`}
                  </Btn>
                </div>
              )}
            </Section>
          )}

          {sortedWorkgroups.length > 0 && (
            <Section
              label="Workgroups"
              containerRef={workgroupsSectionRef}
              right={
                onNewWorkgroup ? (
                  <SectionAddButton
                    tip="New workgroup"
                    ariaLabel="New workgroup"
                    onClick={onNewWorkgroup}
                  />
                ) : null
              }
            >
              {sortedWorkgroups.map((w) => renderWorkgroupRow(w))}
            </Section>
          )}
        </nav>
      </div>

      <SidebarFooter
        inSettings={inSettings}
        onOpenSettings={onOpenSettings ? () => onOpenSettings() : null}
        onOpenPalette={() => onOpenPalette?.()}
        onOpenNotifications={onOpenNotifications}
        notificationsUnread={notificationsUnread}
      />
      {ctxMenu && (
        <ContextMenu
          x={ctxMenu.x}
          y={ctxMenu.y}
          items={ctxMenu.items}
          onClose={closeCtxMenu}
        />
      )}
    </aside>
  );
}

function SidebarFooter({
  inSettings,
  onOpenSettings,
  onOpenPalette,
  onOpenNotifications,
  notificationsUnread = 0,
}) {
  const showSettings = inSettings || Boolean(onOpenSettings);
  return (
    <div className={`${styles.footer} ${inSettings ? styles.footerSettings : ""}`}>
      {showSettings && (
        <Tip text={inSettings ? "Command palette · ⌘K" : "Settings · ⌘,"} side="up">
          <button
            type="button"
            className={`ds-sb-row ${styles.footerButton}`}
            onClick={inSettings ? onOpenPalette : onOpenSettings}
          >
            {inSettings ? <SearchIcon /> : <GearIcon />}
            <span className={styles.rowLabel}>
              {inSettings ? "Command…" : "Settings"}
            </span>
            {inSettings ? (
              <span className={styles.footerKbds} aria-hidden>
                <Kbd>⌘</Kbd>
                <Kbd>K</Kbd>
              </span>
            ) : null}
          </button>
        </Tip>
      )}
      {!inSettings && (
        <NotificationsBellButton
          unread={notificationsUnread}
          onClick={onOpenNotifications}
        />
      )}
      {!inSettings && <ThemeButton />}
      <span className={styles.footerSpacer} aria-hidden />
      <VersionButton />
    </div>
  );
}

function NotificationsBellButton({ unread = 0, onClick }) {
  const tip = unread > 0
    ? `Notifications · ${unread} unread · ⌘O`
    : "Notifications · ⌘O";
  return (
    <Tip text={tip} side="up">
      <IconBtn aria-label={tip} onClick={onClick}>
        <span className={styles.bellWrap}>
          <BellIcon />
          {unread > 0 ? (
            <span className={styles.bellBadge} aria-hidden>
              {unread > 99 ? "99+" : unread}
            </span>
          ) : null}
        </span>
      </IconBtn>
    </Tip>
  );
}

function ThemeButton() {
  const theme = useTheme();
  const icon = theme === "light"
    ? <SunIcon />
    : theme === "dark"
      ? <MoonIcon />
      : <AutoIcon />;
  return (
    <Tip text={`Theme: ${theme} · click for ${nextTheme(theme)}`} side="up">
      <IconBtn
        aria-label={`Theme: ${theme}`}
        onClick={() => cycleTheme()}
      >
        {icon}
      </IconBtn>
    </Tip>
  );
}

export default memo(Sidebar);

function Section({ label, children, right = null, containerRef = null, labelRef = null }) {
  return (
    <div ref={containerRef} className={styles.section}>
      <div ref={labelRef}>
        <SectionLabel right={right}>{label}</SectionLabel>
      </div>
      {children}
    </div>
  );
}

function SectionAddButton({ tip, ariaLabel, onClick }) {
  return (
    <Tip text={tip} side="r">
      <IconBtn
        onClick={onClick}
        aria-label={ariaLabel}
        style={{ width: 18, height: 18 }}
      >
        <PlusIcon style={{ width: 12, height: 12 }} />
      </IconBtn>
    </Tip>
  );
}

function PinAction({ isPinned, onClick }) {
  return (
    <span className={`${styles.pinWrap} ${isPinned ? styles.pinWrapPinned : ""}`}>
      <Tip text={isPinned ? "Unpin" : "Pin"} side="up">
        <IconBtn onClick={onClick} aria-label={isPinned ? "Unpin" : "Pin"} style={{ width: 22, height: 22 }}>
          <PinIcon filled={isPinned} />
        </IconBtn>
      </Tip>
    </span>
  );
}

const ProfileRow = memo(function ProfileRow({
  profile,
  active,
  pending,
  isPinned,
  connId,
  checkUnread,
  onOpen,
  onTogglePin,
  onContextMenu,
}) {
  const handleClick = useCallback(() => onOpen(profile), [onOpen, profile]);
  const handleContextMenu = useCallback(
    (e) => onContextMenu?.(e, profile),
    [onContextMenu, profile],
  );
  const handleTogglePin = useCallback(
    () => onTogglePin?.("profiles", profile.name),
    [onTogglePin, profile.name],
  );

  const ls = profile.latest_session;
  const sessionRecency = ls?.updated_at ?? ls?.started_at ?? ls?.mtime ?? 0;
  const incomplete = !profile.model;
  useEffect(() => {
    if (active && sessionRecency > 0) markProfileRead(connId, profile.name, sessionRecency);
  }, [active, connId, profile.name, sessionRecency]);
  const unread =
    !incomplete && !active && checkUnread?.(profile.name, sessionRecency);
  const trailing = pending
    ? (
        <Tip text="thinking…" side="r">
          <StatusIcon kind="working" />
        </Tip>
      )
    : unread
      ? (
          <span
            className="sb-unread-dot"
            style={{ "--c": profile.accent || "var(--accent)" }}
            aria-label="unread"
          />
        )
      : sessionRecency > 0
        ? <span className="tnum sb-ts">{relativeTime(sessionRecency)}</span>
        : null;
  const label = profileLabel(profile.name);
  const incompleteHint = `@${label}, needs provider — tap to set up`;

  return (
    <div className={styles.rowWrap}>
      <SidebarRow
        kind="profile"
        id={label}
        color={profile.accent || undefined}
        sel={active}
        unread={unread}
        state={incomplete ? "needs-provider" : undefined}
        ariaLabel={incomplete ? incompleteHint : undefined}
        title={incomplete ? incompleteHint : undefined}
        trailing={trailing}
        onClick={handleClick}
        onContextMenu={handleContextMenu}
      />
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
  connId,
  checkUnread,
  onOpen,
  onTogglePin,
  onContextMenu,
}) {
  const handleClick = useCallback(() => onOpen(workgroup), [onOpen, workgroup]);
  const handleContextMenu = useCallback(
    (e) => onContextMenu?.(e, workgroup),
    [onContextMenu, workgroup],
  );
  const handleTogglePin = useCallback(
    () => onTogglePin?.("workgroups", `${workgroup.profile}/${workgroup.id}`),
    [onTogglePin, workgroup.profile, workgroup.id],
  );

  const label = workgroup.name ?? workgroup.id;
  const mtime = workgroup.mtime ?? 0;
  const paused = !!workgroup.paused;

  let stateKind;
  let stateLabel;
  if (busy || task?.state === "open") {
    stateKind = "working";
    stateLabel = "Working…";
  } else if (paused) {
    stateKind = "paused";
    stateLabel = "Paused";
  } else if (task?.state === "error") {
    stateKind = "error";
    stateLabel = "Error";
  } else if (task?.state === "done") {
    stateKind = "done";
    stateLabel = "Task done";
  } else {
    stateKind = "idle";
    stateLabel = "Idle";
  }

  const leading = (
    <span className={styles.workgroupLeading} style={{ color: hubAccent || "var(--ink-4)" }}>
      <StatusIcon kind={stateKind} />
    </span>
  );

  useEffect(() => {
    if (active && mtime > 0) markWorkgroupRead(connId, workgroup.profile, workgroup.id, mtime);
  }, [active, connId, workgroup.profile, workgroup.id, mtime]);
  const unread =
    !paused && !active && checkUnread?.(workgroup.profile, workgroup.id, mtime);
  const trailing = unread
    ? (
        <span
          className="sb-unread-dot"
          style={{ "--c": hubAccent || "var(--accent)" }}
          aria-label="unread"
        />
      )
    : mtime > 0
      ? <span className="tnum sb-ts">{relativeTime(mtime)}</span>
      : null;

  return (
    <div className={styles.rowWrap}>
      <SidebarRow
        kind="workgroup"
        id={label}
        color={hubAccent || undefined}
        sel={active}
        unread={unread}
        state={paused ? "paused" : undefined}
        leading={leading}
        trailing={trailing}
        onClick={handleClick}
        onContextMenu={handleContextMenu}
      />
      <PinAction isPinned={isPinned} onClick={handleTogglePin} />
    </div>
  );
});
