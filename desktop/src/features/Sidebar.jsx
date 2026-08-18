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
  Diamond,
  DiamondStack,
  GearIcon,
  PauseIcon,
  PinIcon,
  PinOffIcon,
  PlusIcon,
  SearchIcon,
  TrashIcon,
  XIcon,
  ArchiveIcon,
} from "../primitives/index.js";
import RelativeTime from "../primitives/RelativeTime.jsx";
import { cycleTheme, nextTheme, useTheme } from "../lib/theme.js";
import { profileLabel } from "../lib/profile-display.js";
import {
  useReadState,
  markProfileRead,
  markWorkgroupRead,
} from "../hooks/useReadState.js";
import { compareProfiles, orderedSidebarProfiles, orderPinnedItems } from "../lib/profile-order.js";
import Skeleton from "../primitives/Skeleton.jsx";
import { useDelayedFlag } from "../lib/useDelayedFlag.js";
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
  pendingProfiles = null,
  view,
  settingsTarget = null,
  pinned = { profiles: [], workgroups: [] },
  hostConnections,
  daemonOffline = false,
  connectionSyncing = false,
  onNewChat,
  onNewProfile,
  onNewWorkgroup,
  onOpenProfile,
  onOpenWorkgroup,
  onOpenSettings,
  onOpenPalette,
  onSetSettingsTarget,
  onOpenSettingsTarget,
  onTogglePin,
  onTogglePauseProfile,
  onSetHostConnection,
  onAddHostConnection,
  onForgetHostConnection,
  onRefreshHostConnectionStatus,
  autoOpenConnectionSwitcher = false,
  connectionLocked = false,
  onOpenNotifications,
  notificationsUnread = 0,
  searchOpen = false,
  onCloseSearch,
}) {
  const inSettings = view.kind === "settings";
  const [query, setQuery] = useState("");
  const searchInputRef = useRef(null);
  useEffect(() => {
    if (searchOpen) {
      searchInputRef.current?.focus();
      searchInputRef.current?.select();
    } else {
      setQuery("");
    }
  }, [searchOpen]);

  const connId = hostConnections?.active_id ?? "local";
  const showLoadingRows = useDelayedFlag(
    connectionSyncing && profiles.length === 0 && workgroups.length === 0,
    300,
  );
  const { checkProfile: checkUnread, checkWorkgroup: checkWorkgroupUnread } =
    useReadState(connId);
  const openProfile = useCallback(
    (p) => {
      if (inSettings) {
        onSetSettingsTarget?.({ kind: "profile", id: p.name });
        return;
      }
      markProfileRead(connId, p.name);
      onOpenProfile?.(p);
    },
    [inSettings, onSetSettingsTarget, connId, onOpenProfile],
  );
  const openWorkgroup = useCallback(
    (w) => {
      if (inSettings) {
        onSetSettingsTarget?.({ kind: "workgroup", id: w.id, profile: w.profile });
        return;
      }
      markWorkgroupRead(connId, w.profile, w.id);
      onOpenWorkgroup?.(w);
    },
    [inSettings, onSetSettingsTarget, connId, onOpenWorkgroup],
  );
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
    list.sort(compareProfiles);
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

  const pinnedItems = useMemo(
    () => orderPinnedItems(pinnedProfiles, pinnedWorkgroups),
    [pinnedProfiles, pinnedWorkgroups],
  );

  const q = searchOpen ? query.trim().toLowerCase() : "";
  const matchProfile = (p) =>
    !q ||
    p.name.toLowerCase().includes(q) ||
    profileLabel(p.name).toLowerCase().includes(q);
  const matchWorkgroup = (w) =>
    !q ||
    (w.name ?? "").toLowerCase().includes(q) ||
    String(w.id ?? "").toLowerCase().includes(q);
  const filteredProfiles = q ? sortedProfiles.filter(matchProfile) : sortedProfiles;
  const filteredWorkgroups = q ? sortedWorkgroups.filter(matchWorkgroup) : sortedWorkgroups;
  const filteredPinnedItems = q
    ? pinnedItems.filter((it) =>
        it.kind === "profile" ? matchProfile(it.item) : matchWorkgroup(it.item),
      )
    : pinnedItems;
  const hasPinned = filteredPinnedItems.length > 0;
  const noMatches =
    !!q &&
    filteredProfiles.length === 0 &&
    filteredWorkgroups.length === 0 &&
    filteredPinnedItems.length === 0;

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
  const hasAlpisOverflow = !q && sortedProfiles.length > maxAlpisVisible;
  const visibleAlpis = q
    ? filteredProfiles
    : hasAlpisOverflow && !showAllAlpis
      ? sortedProfiles.slice(0, maxAlpisVisible)
      : sortedProfiles;
  const hiddenAlpisCount = sortedProfiles.length - maxAlpisVisible;

  const [ctxMenu, setCtxMenu] = useState(null);
  const closeCtxMenu = useCallback(() => setCtxMenu(null), []);

  const openProfileCtx = useCallback(
    (e, profile) => {
      e.preventDefault();
      if (!onOpenSettingsTarget) return;
      const pinned = pinnedProfileNames.includes(profile.name);
      const items = [
        {
          label: pinned ? "Unpin from top" : "Pin to top",
          icon: pinned ? <PinOffIcon /> : <PinIcon />,
          onClick: () => onTogglePin?.("profiles", profile.name),
        },
        { kind: "separator" },
        ...(onTogglePauseProfile
          ? [{
              label: profile.paused ? "Resume profile" : "Pause profile",
              icon: <PauseIcon />,
              onClick: () => onTogglePauseProfile(profile),
            }]
          : []),
        {
          label: "Open settings",
          icon: <GearIcon />,
          shortcut: "⌘,",
          onClick: () => onOpenSettingsTarget({ kind: "profile", id: profile.name }),
        },
        { kind: "separator" },
        {
          label: "Delete profile…",
          icon: <TrashIcon />,
          kind: "danger",
          onClick: () =>
            onOpenSettingsTarget({ kind: "profile", id: profile.name, intent: "delete" }),
        },
      ];
      setCtxMenu({ x: e.clientX, y: e.clientY, items });
    },
    [pinnedProfileNames, onTogglePin, onTogglePauseProfile, onOpenSettingsTarget],
  );

  const openWorkgroupCtx = useCallback(
    (e, workgroup) => {
      e.preventDefault();
      if (!onOpenSettingsTarget) return;
      const key = `${workgroup.profile}/${workgroup.id}`;
      const pinned = pinnedWorkgroupKeys.includes(key);
      const wgTarget = {
        kind: "workgroup",
        id: workgroup.id,
        profile: workgroup.profile,
      };
      const items = [
        {
          label: pinned ? "Unpin from top" : "Pin to top",
          icon: pinned ? <PinOffIcon /> : <PinIcon />,
          onClick: () => onTogglePin?.("workgroups", key),
        },
        { kind: "separator" },
        {
          label: "Open settings",
          icon: <GearIcon />,
          shortcut: "⌘,",
          onClick: () => onOpenSettingsTarget(wgTarget),
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
          onClick: () => onOpenSettingsTarget(wgTarget),
        },
      ];
      setCtxMenu({ x: e.clientX, y: e.clientY, items });
    },
    [pinnedWorkgroupKeys, onTogglePin, onOpenSettingsTarget],
  );

  const renderProfileRow = (p, keyPrefix = "") => (
    <ProfileRow
      key={keyPrefix + p.name}
      profile={p}
      active={activeProfileName === p.name}
      pending={!!pendingProfiles?.has(p.name)}
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
              locked={connectionLocked}
            />
          </div>
          {!daemonOffline && !inSettings && (
            searchOpen ? (
              <div className={styles.searchRow} role="search">
                <SearchIcon className={styles.searchIcon} />
                <input
                  ref={searchInputRef}
                  className={styles.searchInput}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Escape") {
                      e.preventDefault();
                      onCloseSearch?.();
                    }
                  }}
                  placeholder="Filter profiles & workgroups…"
                  spellCheck={false}
                  autoCapitalize="off"
                  autoCorrect="off"
                  aria-label="Filter profiles and workgroups"
                />
                <button
                  type="button"
                  className={styles.searchClose}
                  onClick={onCloseSearch}
                  aria-label="Close filter"
                >
                  <XIcon size={14} />
                </button>
              </div>
            ) : (
              <button
                type="button"
                className="ds-sb-row"
                data-active={inEmpty || undefined}
                onClick={onNewChat}
                style={inEmpty ? { background: "var(--selected)" } : undefined}
              >
                <PlusIcon />
                <span className={styles.rowLabel}>New session</span>
              </button>
            )
          )}
        </div>

        <nav ref={navRef} className={styles.nav}>
          {showLoadingRows && (
            <Section label="Profiles">
              <SidebarLoadingRows />
            </Section>
          )}
          {hasPinned && (
            <Section label="Pinned" containerRef={pinnedSectionRef}>
              {filteredPinnedItems.map((it) =>
                it.kind === "profile"
                  ? renderProfileRow(it.item, "pin:")
                  : renderWorkgroupRow(it.item, "pin:"),
              )}
            </Section>
          )}

          {filteredProfiles.length > 0 && (
            <Section
              label="Profiles"
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
              {hasAlpisOverflow && (
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

          {filteredWorkgroups.length > 0 && (
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
              {filteredWorkgroups.map((w) => renderWorkgroupRow(w))}
            </Section>
          )}
          {noMatches && (
            <div className={styles.searchEmpty}>No profiles or workgroups match</div>
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

function SidebarLoadingRows() {
  return (
    <div className={styles.loadingRows} role="status" aria-label="Loading profiles">
      {["68%", "52%", "60%"].map((w) => (
        <div key={w} className={styles.loadingRow}>
          <Skeleton width="9px" height="9px" radius="2px" delay={0} />
          <Skeleton width={w} height="0.65em" delay={0} />
        </div>
      ))}
    </div>
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
        <Tip text={inSettings ? "Command palette · ⌘K" : "Settings · ⌘,"} side="up-l">
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
      {!inSettings && onOpenNotifications && (
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
    <Tip text={tip} side="up-l">
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
    <Tip text={`Theme: ${theme} · click for ${nextTheme(theme)}`} side="up-l">
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
          {isPinned ? <PinOffIcon /> : <PinIcon />}
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
  const paused = !!profile.paused;
  useEffect(() => {
    if (active && sessionRecency > 0) markProfileRead(connId, profile.name, sessionRecency);
  }, [active, connId, profile.name, sessionRecency]);
  const unread =
    !incomplete && !paused && !active && checkUnread?.(profile.name, sessionRecency);
  const trailing = sessionRecency > 0
    ? (
      <span className={`tnum sb-ts${unread ? " is-unr" : ""}`}>
        <RelativeTime ts={sessionRecency} />
      </span>
    )
    : null;
  const label = profileLabel(profile.name);
  const incompleteHint = `@${label}, needs provider — tap to set up`;
  const leadingDiamond = <Diamond color={profile.accent || undefined} pulse={pending} />;
  const bio = (profile.bio || profile.public_bio || "").trim();

  return (
    <div className={styles.rowWrap}>
      <SidebarRow
        kind="profile"
        id={label}
        color={profile.accent || undefined}
        sel={active}
        unread={unread}
        state={paused ? "paused" : incomplete ? "needs-provider" : undefined}
        ariaLabel={incomplete ? incompleteHint : unread ? `${label} unread` : undefined}
        title={incomplete ? incompleteHint : undefined}
        leading={
          pending
            ? <Tip text="thinking…" side="up-l">{leadingDiamond}</Tip>
            : bio
              ? <Tip text={bio} side="l" escape>{leadingDiamond}</Tip>
              : leadingDiamond
        }
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

  useEffect(() => {
    if (active && mtime > 0) markWorkgroupRead(connId, workgroup.profile, workgroup.id, mtime);
  }, [active, connId, workgroup.profile, workgroup.id, mtime]);
  const unread =
    !paused && !active && checkUnread?.(workgroup.profile, workgroup.id, mtime);
  const working = stateKind === "working";
  const trailing = mtime > 0
    ? (
      <span className={`tnum sb-ts${unread ? " is-unr" : ""}`}>
        <RelativeTime ts={mtime} />
      </span>
    )
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
        ariaLabel={unread ? `${label} unread` : undefined}
        leading={
          <span className={styles.workgroupLeading} style={{ color: hubAccent || "var(--ink-4)" }}>
            {working ? (
              <Tip text={stateLabel} side="up-l">
                <DiamondStack color={hubAccent || undefined} pulse />
              </Tip>
            ) : (
              <DiamondStack color={hubAccent || undefined} />
            )}
          </span>
        }
        trailing={trailing}
        onClick={handleClick}
        onContextMenu={handleContextMenu}
      />
      <PinAction isPinned={isPinned} onClick={handleTogglePin} />
    </div>
  );
});
