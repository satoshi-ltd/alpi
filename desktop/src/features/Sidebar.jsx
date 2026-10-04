import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import ConnectionSwitcher from "./ConnectionSwitcher.jsx";
import VersionButton from "./VersionButton.jsx";
import { ActionLink, SidebarRow, SectionLabel, ContextMenu } from "../primitives/index.js";
import { WORKGROUP_FOLD } from "../../../common/folds.mjs";
import { shortcutKeys } from "../lib/shortcuts.js";
import {
  AutoIcon,
  Button,
  IconBtn,
  KeyHint,
  MoonIcon,
  SunIcon,
  Tip,
  Fold,
  GearIcon,
  Icon,
  PauseIcon,
  PinIcon,
  PinOffIcon,
  PlusIcon,
  SearchIcon,
  TrashIcon,
  XIcon,
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
import { isDefaultProfile, splitDefaultProfile, withoutDefaultPin } from "../../../common/rosterOrder.mjs";
import Skeleton from "../primitives/Skeleton.jsx";
import { useDelayedFlag } from "../lib/useDelayedFlag.js";
import styles from "./Sidebar.module.css";
import { ICON_ROLES } from "../../../common/iconRoles.mjs";
import { badgeCount } from "../../../common/countBadge.mjs";
import { EMPTY } from "../../../common/emptyCopy.mjs";

const MIN_VISIBLE_ALPIS = 3;
const MIN_VISIBLE_WORKGROUPS = 2;
const MAX_VISIBLE_WORKGROUPS = 6;
const ROW_HEIGHT_FALLBACK = 34;

export function fitWorkgroupRows(current, maximum, freeSpace, rowHeight) {
  const minimum = Math.min(MIN_VISIBLE_WORKGROUPS, maximum);
  if (freeSpace < 0) {
    return Math.max(minimum, current - Math.ceil(Math.abs(freeSpace) / rowHeight));
  }
  if (freeSpace >= rowHeight) {
    return Math.min(maximum, current + Math.floor(freeSpace / rowHeight));
  }
  return Math.min(maximum, Math.max(minimum, current));
}

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
  rosterState = null,
  view,
  settingsTarget = null,
  pinned = { profiles: [], workgroups: [] },
  hostConnections,
  daemonOffline = false,
  connectionSyncing = false,
  rosterAnswered = true,
  onNewSessionWith = null,
  onNewProfile,
  onNewWorkgroup,
  onOpenProfile,
  onOpenWorkgroup,
  onViewAllWorkgroups,
  onOpenSettings,
  onOpenPalette,
  onSetSettingsTarget,
  onOpenSettingsTarget,
  onTogglePin,
  onTogglePauseProfile,
  onSetHostConnection,
  onAddHostConnection,
  onForgetHostConnection,
  onRenameHostConnection,
  onRefreshHostConnectionStatus,
  autoOpenConnectionSwitcher = false,
  connectionLocked = false,
  onOpenNotifications,
  notificationsUnread = 0,
  onOpenActivity = null,
  activityNeedsYou = 0,
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
    connectionSyncing && !rosterAnswered && profiles.length === 0 && workgroups.length === 0,
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

  const pinnedProfileNames = useMemo(() => withoutDefaultPin(pinned.profiles), [pinned.profiles]);
  const pinnedWorkgroupKeys = pinned.workgroups ?? [];

  const { front: frontProfile, rest: otherProfiles } = useMemo(
    () => splitDefaultProfile(profiles),
    [profiles],
  );

  const sortedProfiles = useMemo(
    () =>
      orderedSidebarProfiles(otherProfiles, pinnedProfileNames).filter(
        (p) => !pinnedProfileNames.includes(p.name),
      ),
    [otherProfiles, pinnedProfileNames],
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
      .map((name) => otherProfiles.find((p) => p.name === name))
      .filter(Boolean);
    list.sort(compareProfiles);
    return list;
  }, [pinnedProfileNames, otherProfiles]);

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
  const visibleFront = frontProfile && matchProfile(frontProfile) ? frontProfile : null;
  const showProfilesSection =
    filteredProfiles.length > 0 || (!q && !!visibleFront && !!onNewProfile);
  const noMatches =
    !!q &&
    !visibleFront &&
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

  const [frontSectionRef, frontSectionH] = useMeasuredHeight();
  const [pinnedSectionRef, pinnedSectionH] = useMeasuredHeight();
  const [profilesSectionRef, profilesSectionH] = useMeasuredHeight();
  const [workgroupsSectionRef, workgroupsSectionH] = useMeasuredHeight();
  const [alpisLabelRef, alpisLabelH] = useMeasuredHeight();
  const [showMoreRef, showMoreH] = useMeasuredHeight();
  const [firstRowRef, firstRowH] = useMeasuredHeight();
  const rowHeight = firstRowH || ROW_HEIGHT_FALLBACK;
  const [workgroupLimit, setWorkgroupLimit] = useState(MAX_VISIBLE_WORKGROUPS);
  const maximumWorkgroupRows = Math.min(MAX_VISIBLE_WORKGROUPS, filteredWorkgroups.length);
  const renderedWorkgroupRows = q
    ? filteredWorkgroups.length
    : Math.min(workgroupLimit, maximumWorkgroupRows);
  const reservedWorkgroupsH = q
    ? workgroupsSectionH
    : workgroupsSectionH + (maximumWorkgroupRows - renderedWorkgroupRows) * rowHeight;

  const maxAlpisVisible = useMemo(() => {
    if (!navHeight) return sortedProfiles.length;
    const available =
      navHeight - frontSectionH - pinnedSectionH - reservedWorkgroupsH - alpisLabelH - showMoreH;
    return Math.max(MIN_VISIBLE_ALPIS, Math.floor(available / rowHeight));
  }, [
    navHeight,
    frontSectionH,
    pinnedSectionH,
    reservedWorkgroupsH,
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

  useEffect(() => {
    if (q || !onViewAllWorkgroups || !navHeight || !workgroupsSectionH) {
      setWorkgroupLimit(maximumWorkgroupRows);
      return;
    }
    const freeSpace = navHeight - frontSectionH - pinnedSectionH - profilesSectionH - workgroupsSectionH;
    setWorkgroupLimit((current) => fitWorkgroupRows(
      Math.min(current, maximumWorkgroupRows),
      maximumWorkgroupRows,
      freeSpace,
      rowHeight,
    ));
  }, [
    maximumWorkgroupRows,
    navHeight,
    onViewAllWorkgroups,
    frontSectionH,
    pinnedSectionH,
    profilesSectionH,
    q,
    rowHeight,
    workgroupsSectionH,
  ]);
  const visibleWorkgroups = useMemo(() => {
    if (q || filteredWorkgroups.length <= workgroupLimit) return filteredWorkgroups;
    const visible = filteredWorkgroups.slice(0, workgroupLimit);
    const active = filteredWorkgroups.find(
      (workgroup) => `${workgroup.profile}/${workgroup.id}` === activeWorkgroupId,
    );
    if (!active || visible.includes(active)) return visible;
    return [...visible.slice(0, -1), active];
  }, [activeWorkgroupId, filteredWorkgroups, q, workgroupLimit]);
  const hasWorkgroupOverflow = !q && visibleWorkgroups.length < filteredWorkgroups.length;

  const [ctxMenu, setCtxMenu] = useState(null);
  const closeCtxMenu = useCallback(() => setCtxMenu(null), []);

  const openProfileCtx = useCallback(
    (e, profile) => {
      e.preventDefault();
      const newSessionItems = onNewSessionWith
        ? [{
            label: "New session",
            icon: <PlusIcon />,
            shortcut: shortcutKeys("new-session"),
            onClick: () => onNewSessionWith(profile),
          }]
        : [];
      if (!onOpenSettingsTarget) {
        if (newSessionItems.length) setCtxMenu({ x: e.clientX, y: e.clientY, items: newSessionItems });
        return;
      }
      const pinned = pinnedProfileNames.includes(profile.name);
      const pinItems = isDefaultProfile(profile)
        ? []
        : [
            {
              label: pinned ? "Unpin from top" : "Pin to top",
              icon: pinned ? <PinOffIcon /> : <PinIcon />,
              onClick: () => onTogglePin?.("profiles", profile.name),
            },
            { kind: "separator" },
          ];
      const items = [
        ...(newSessionItems.length ? [...newSessionItems, { kind: "separator" }] : []),
        ...pinItems,
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
          shortcut: shortcutKeys("settings"),
          onClick: () => onOpenSettingsTarget({ kind: "profile", id: profile.name }),
        },
        ...(isDefaultProfile(profile)
          ? []
          : [
              { kind: "separator" },
              {
                label: "Delete profile…",
                icon: <TrashIcon />,
                kind: "danger",
                onClick: () =>
                  onOpenSettingsTarget({ kind: "profile", id: profile.name, intent: "delete" }),
              },
            ]),
      ];
      setCtxMenu({ x: e.clientX, y: e.clientY, items });
    },
    [pinnedProfileNames, onTogglePin, onTogglePauseProfile, onOpenSettingsTarget, onNewSessionWith],
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
          shortcut: shortcutKeys("settings"),
          onClick: () => onOpenSettingsTarget(wgTarget),
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
      pending={!!pendingProfiles?.has(p.name) || rosterState?.profiles?.[p.name] === "working"}
      rowState={rosterState?.profiles?.[p.name] ?? null}
      isPinned={pinnedProfileNames.includes(p.name)}
      pinnable={!isDefaultProfile(p)}
      offline={daemonOffline}
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
        run={rosterState?.workgroups?.[key] ?? null}
        active={activeWorkgroupId === key}
        isPinned={pinnedWorkgroupKeys.includes(key)}
        offline={daemonOffline}
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
              onRename={onRenameHostConnection}
              onOpen={onRefreshHostConnectionStatus}
              autoOpenSignal={autoOpenConnectionSwitcher}
              locked={connectionLocked}
            />
          </div>
          {!daemonOffline && !inSettings && searchOpen && (
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
              <IconBtn
                className={styles.searchClose}
                onClick={onCloseSearch}
                aria-label="Close filter"
              >
                <XIcon />
              </IconBtn>
            </div>
          )}
        </div>

        <nav ref={navRef} className={styles.nav}>
          {showLoadingRows && (
            <Section label="Profiles">
              <SidebarLoadingRows />
            </Section>
          )}
          {visibleFront && (
            <div ref={frontSectionRef} className={styles.section}>
              {renderProfileRow(visibleFront, "front:")}
            </div>
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

          {showProfilesSection && (
            <Section
              label="Profiles"
              containerRef={profilesSectionRef}
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
                  <Button variant="ghost" size="sm" onClick={() => setShowAllAlpis((v) => !v)}>
                    {showAllAlpis
                      ? "Show less"
                      : `Show ${hiddenAlpisCount} more`}
                  </Button>
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
              {visibleWorkgroups.map((w) => renderWorkgroupRow(w))}
              {hasWorkgroupOverflow && onViewAllWorkgroups && (
                <div className={styles.showMoreWrap}>
                  <Button variant="ghost" size="sm" onClick={onViewAllWorkgroups}>
                    View all workgroups
                  </Button>
                </div>
              )}
            </Section>
          )}
          {noMatches && (
            <div className={styles.searchEmpty}>No profiles or workgroups match</div>
          )}
          {!showLoadingRows && !query && !daemonOffline && rosterAnswered && profiles.length === 0 && workgroups.length === 0 && (
            <div className={styles.searchEmpty}>
              {EMPTY.profiles.title}
              {onNewProfile && (
                <div>
                  <ActionLink onClick={onNewProfile}>New profile</ActionLink>
                </div>
              )}
            </div>
          )}
        </nav>
      </div>

      <SidebarFooter
        inSettings={inSettings}
        onOpenSettings={onOpenSettings ? () => onOpenSettings() : null}
        onOpenPalette={() => onOpenPalette?.()}
        onOpenNotifications={onOpenNotifications}
        notificationsUnread={notificationsUnread}
        onOpenActivity={onOpenActivity}
        activityNeedsYou={activityNeedsYou}
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
  onOpenActivity = null,
  activityNeedsYou = 0,
}) {
  const showSettings = inSettings || Boolean(onOpenSettings);
  return (
    <div className={`${styles.footer} ${inSettings ? styles.footerSettings : ""}`}>
      {showSettings && (
        <Button
          variant="ghost"
          size="sm"
          className={inSettings ? styles.footerButton : `${styles.footerButton} ${styles.footerTight}`}
          icon={inSettings ? <SearchIcon /> : <Icon name={ICON_ROLES.settings} />}
          tip={inSettings ? `Command palette · ${shortcutKeys("palette")}` : `Settings · ${shortcutKeys("settings")}`}
          tipSide="up-l"
          onClick={inSettings ? onOpenPalette : onOpenSettings}
        >
          <span className={styles.rowLabel}>
            {inSettings ? "Command…" : "Settings"}
          </span>
          {inSettings ? <KeyHint hint={shortcutKeys("palette")} /> : null}
        </Button>
      )}
      {!inSettings && onOpenNotifications && (
        <NotificationsBellButton
          unread={notificationsUnread}
          onClick={onOpenNotifications}
        />
      )}
      {!inSettings && onOpenActivity && (
        <ActivityButton needsYou={activityNeedsYou} onClick={onOpenActivity} />
      )}
      {!inSettings && <ThemeButton />}
      <span className={styles.footerSpacer} aria-hidden />
      <VersionButton />
    </div>
  );
}

function NotificationsBellButton({ unread = 0, onClick }) {
  const keys = shortcutKeys("notifications");
  const tip = unread > 0
    ? `Notifications · ${unread} unread · ${keys}`
    : `Notifications · ${keys}`;
  return (
    <Tip text={tip} side="up-l">
      <IconBtn size="sm" className={styles.footerIcon} aria-label={tip} onClick={onClick}>
        <span className={styles.bellWrap}>
          <Icon name={ICON_ROLES.notifications} />
          {unread > 0 ? (
            <span className={styles.bellBadge} aria-hidden>
              {badgeCount(unread)}
            </span>
          ) : null}
        </span>
      </IconBtn>
    </Tip>
  );
}

function ActivityButton({ needsYou = 0, onClick }) {
  const keys = shortcutKeys("activity");
  const tip = needsYou > 0 ? `Activity · ${needsYou} need you · ${keys}` : `Activity · ${keys}`;
  return (
    <Tip text={tip} side="up-l">
      <IconBtn size="sm" className={styles.footerIcon} aria-label={tip} onClick={onClick}>
        <span className={styles.bellWrap}>
          <Icon name={ICON_ROLES.activity} />
          {needsYou > 0 ? (
            <span className={styles.bellBadge} aria-hidden>
              {badgeCount(needsYou)}
            </span>
          ) : null}
        </span>
      </IconBtn>
    </Tip>
  );
}

const ROW_STATE_LABEL = { "needs-you": "needs you", failed: "failed", working: "working" };

export function RowStateChip({ state, color }) {
  const text = ROW_STATE_LABEL[state];
  if (!text) return null;
  return (
    <span className={styles.stateChip} data-state={state} style={color ? { "--c": color } : undefined}>
      {state === "working" ? null : <span className={styles.stateDot} aria-hidden />}
      {text}
    </span>
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
        size="sm"
        className={styles.footerIcon}
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
    <IconBtn tip={tip} tipSide="r" onClick={onClick} aria-label={ariaLabel} className={styles.sectionAdd}>
      <PlusIcon />
    </IconBtn>
  );
}

function PinAction({ isPinned, onClick }) {
  return (
    <span className={`${styles.pinWrap} ${isPinned ? styles.pinWrapPinned : ""}`}>
      <IconBtn tip={isPinned ? "Unpin" : "Pin"} tipSide="up" onClick={onClick} aria-label={isPinned ? "Unpin" : "Pin"} className={styles.pinButton}>
        {isPinned ? <PinOffIcon /> : <PinIcon />}
      </IconBtn>
    </span>
  );
}

const ProfileRow = memo(function ProfileRow({
  profile,
  active,
  pending,
  rowState = null,
  isPinned,
  pinnable = true,
  offline = false,
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
  const trailing = rowState
    ? <RowStateChip state={rowState} color={profile.accent || undefined} />
    : sessionRecency > 0
      ? (
        <span className={`tnum sb-ts${unread ? " is-unr" : ""}`}>
          <RelativeTime ts={sessionRecency} />
        </span>
      )
      : null;
  const label = profileLabel(profile.name);
  const incompleteHint = `@${label}, needs provider — tap to set up`;
  const leadingDiamond = <Fold fold={profile.fold} color={profile.accent || undefined} pulse={pending} outlined={incomplete} unfolded={offline || !!profile.paused} />;
  const bio = (profile.bio || profile.public_bio || "").trim();

  return (
    <div className={pinnable ? styles.rowWrap : `${styles.rowWrap} ${styles.rowWrapFixed}`}>
      <SidebarRow
        kind="profile"
        id={label}
        color={profile.accent || undefined}
        fold={profile.fold}
        sel={active}
        unread={unread}
        state={paused ? "paused" : incomplete ? "needs-provider" : undefined}
        ariaLabel={
          incomplete
            ? incompleteHint
            : rowState
              ? `${label}, ${ROW_STATE_LABEL[rowState]}`
              : unread ? `${label} unread` : undefined
        }
        leading={
          pending
            ? <Tip text="thinking…" side="up-l">{leadingDiamond}</Tip>
            : incomplete
              ? <Tip text={incompleteHint} side="l" escape>{leadingDiamond}</Tip>
              : bio
              ? <Tip text={bio} side="l" escape>{leadingDiamond}</Tip>
              : leadingDiamond
        }
        trailing={trailing}
        onClick={handleClick}
        onContextMenu={handleContextMenu}
      />
      {pinnable ? <PinAction isPinned={isPinned} onClick={handleTogglePin} /> : null}
    </div>
  );
});

const WorkgroupRow = memo(function WorkgroupRow({
  workgroup,
  hubAccent,
  task,
  busy,
  run = null,
  active,
  isPinned,
  offline = false,
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
  if (run || busy || task?.state === "open") {
    stateKind = "working";
    stateLabel = run?.phase ? `Working · ${run.phase}` : "Working…";
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
  const hasPhases = run?.phasesTotal > 0 && run?.phasesDone != null;
  const trailing = hasPhases
    ? (
      <span className={`tnum ${styles.phaseCount}`} style={hubAccent ? { "--c": hubAccent } : undefined} aria-label={`phase ${run.phasesDone} of ${run.phasesTotal}`}>
        {run.phasesDone}/{run.phasesTotal}
      </span>
    )
    : mtime > 0
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
          <span className={styles.workgroupLeading} style={{ color: hubAccent || "var(--ink-3)" }}>
            {working && !paused ? (
              <Tip text={stateLabel} side="up-l">
                <Fold fold={WORKGROUP_FOLD} color={hubAccent || undefined} pulse unfolded={offline} />
              </Tip>
            ) : (
              <Fold fold={WORKGROUP_FOLD} color={hubAccent || undefined} unfolded={offline || paused} />
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
