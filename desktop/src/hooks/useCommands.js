import { useMemo } from "react";
import { shortcutKeys as keys } from "../lib/shortcuts.js";

export function useCommands({
  view,
  searchOpen,
  activeProfileName = null,
  historyKind = null,
  onOpenSettings,
  onCloseSettings,
  onToggleSearch,
  onToggleSidebarSearch,
  sidebarSearchOpen = false,
  onCycleTheme = null,
  onNewProfile,
  onNewWorkgroup,
  onNewSession,
  onRefreshThread,
  canRefreshThread = false,
  onToggleReadAloud,
  canReadAloud = false,
  readAloudActive = false,
  profilePaused = false,
  onToggleProfilePause,
  workgroupPaused = false,
  onToggleWorkgroupPause,
  onBrowseTools,
  onBrowseSkills,
  onBrowseMemory,
  onBrowseSchedule,
  onOpenHistory,
  onToggleNotifications,
  onToggleActivity = null,
  onOpenShortcuts = null,
}) {
  return useMemo(() => {
    const cmds = [
      {
        id: "help:palette",
        group: "General",
        label: "Command palette",
        hint: keys("palette"),
      },
      {
        id: "help:jump",
        group: "General",
        label: "Jump to profile / workgroup",
        hint: keys("jump"),
      },
    ];

    if (onOpenShortcuts) {
      cmds.push({
        id: "view:shortcuts",
        group: "General",
        label: "Keyboard shortcuts",
        hint: keys("shortcuts"),
        action: () => onOpenShortcuts(),
      });
    }

    if (onToggleActivity) {
      cmds.push({
        id: "view:activity",
        group: "General",
        label: "Activity",
        hint: keys("activity"),
        action: () => onToggleActivity(),
      });
    }

    if (onToggleSidebarSearch) {
      cmds.push({
        id: "view:find",
        group: "General",
        label: sidebarSearchOpen ? "Close filter" : "Filter profiles & workgroups",
        hint: keys("filter"),
        action: () => onToggleSidebarSearch(),
      });
    }

    if (historyKind === "sessions" && activeProfileName && onOpenHistory) {
      cmds.push({
        id: "profile:sessions",
        group: "Profile",
        label: "Sessions",
        hint: keys("history"),
        action: () => onOpenHistory(),
      });
    }

    if (onNewSession) {
      cmds.push({
        id: "create:chat",
        group: "Chat",
        label: "New session",
        hint: keys("new-session"),
        action: () => onNewSession(),
      });
    }

    if (view.kind === "profile" && onRefreshThread && canRefreshThread) {
      cmds.push({
        id: "chat:refresh",
        group: "Chat",
        label: "Refresh thread",
        hint: keys("refresh"),
        action: () => onRefreshThread(),
      });
    }

    if (view.kind === "profile" && onToggleReadAloud && canReadAloud) {
      cmds.push({
        id: "chat:read-aloud",
        group: "Chat",
        label: readAloudActive ? "Stop audio" : "Read aloud",
        hint: keys("read-aloud"),
        action: () => onToggleReadAloud(),
      });
    }

    if (view.kind === "profile" || view.kind === "workgroup") {
      cmds.push({
        id: "chat:find",
        group: "Chat",
        label: searchOpen ? "Close find" : "Find in transcript",
        hint: keys("find"),
        action: () => onToggleSearch?.(),
      });
    }

    if (historyKind === "tasks" && onOpenHistory) {
      cmds.push({
        id: "workgroup:tasks",
        group: "Workgroup",
        label: "Task history",
        hint: keys("history"),
        action: () => onOpenHistory(),
      });
    }

    if (view.kind === "workgroup" && onToggleWorkgroupPause) {
      cmds.push({
        id: "workgroup:pause",
        group: "Workgroup",
        label: workgroupPaused ? "Resume workgroup" : "Pause workgroup",
        hint: keys("pause"),
        action: () => onToggleWorkgroupPause(),
      });
    }

    if (view.kind === "workgroup" && onRefreshThread) {
      cmds.push({
        id: "workgroup:refresh",
        group: "Workgroup",
        label: "Refresh thread",
        hint: keys("refresh"),
        action: () => onRefreshThread(),
      });
    }

    if (activeProfileName) {
      if (onToggleProfilePause) {
        cmds.push({
          id: "profile:pause",
          group: "Profile",
          label: profilePaused ? "Resume profile" : "Pause profile",
          hint: keys("pause"),
          action: () => onToggleProfilePause(),
        });
      }
      cmds.push({
        id: "profile:tools",
        group: "Profile",
        label: "Tools",
        hint: keys("tools"),
        action: () => onBrowseTools?.(),
      });
      cmds.push({
        id: "profile:skills",
        group: "Profile",
        label: "Skills",
        hint: keys("skills"),
        action: () => onBrowseSkills?.(),
      });
      cmds.push({
        id: "profile:memory",
        group: "Profile",
        label: "Memory",
        hint: keys("memory"),
        action: () => onBrowseMemory?.(),
      });
      cmds.push({
        id: "profile:schedule",
        group: "Profile",
        label: "Schedule",
        hint: keys("schedule"),
        action: () => onBrowseSchedule?.(),
      });
    }

    if (view.kind === "settings" ? Boolean(onCloseSettings) : Boolean(onOpenSettings)) {
      cmds.push({
        id: "view:settings",
        group: "General",
        label: view.kind === "settings" ? "Close settings" : "Open settings",
        hint: keys("settings"),
        action: () =>
          view.kind === "settings" ? onCloseSettings?.() : onOpenSettings?.(),
      });
    }

    if (onToggleNotifications) {
      cmds.push({
        id: "view:notifications",
        group: "General",
        label: "Notifications",
        hint: keys("notifications"),
        action: () => onToggleNotifications(),
      });
    }

    if (onNewProfile) {
      cmds.push({
        id: "create:profile",
        group: "Create",
        label: "New profile",
        hint: keys("new-profile"),
        action: () => onNewProfile(),
      });
    }

    if (onNewWorkgroup) {
      cmds.push({
        id: "create:workgroup",
        group: "Create",
        label: "New workgroup",
        hint: keys("new-workgroup"),
        action: () => onNewWorkgroup(),
      });
    }

    if (onCycleTheme) {
      cmds.push({
        id: "pref:theme",
        group: "Preferences",
        label: "Switch theme",
        hint: "light · dark · system",
        action: () => onCycleTheme(),
      });
    }

    [
      ["help:send", "Chat", "Send message", keys("send")],
      ["help:zoom-in", "View", "Zoom in", keys("zoom-in")],
      ["help:zoom-out", "View", "Zoom out", keys("zoom-out")],
      ["help:zoom-reset", "View", "Reset zoom", keys("zoom-reset")],
      ["help:close", "View", "Close / dismiss", keys("close")],
    ].forEach(([id, group, label, hint]) => {
      cmds.push({
        id,
        group,
        label,
        hint,
      });
    });

    return cmds;
  }, [
    view,
    searchOpen,
    onCycleTheme,
    activeProfileName,
    historyKind,
    onOpenSettings,
    onCloseSettings,
    onToggleSearch,
    onToggleSidebarSearch,
    sidebarSearchOpen,
    onNewProfile,
    onNewWorkgroup,
    onNewSession,
    onRefreshThread,
    canRefreshThread,
    onToggleReadAloud,
    canReadAloud,
    readAloudActive,
    profilePaused,
    onToggleProfilePause,
    workgroupPaused,
    onToggleWorkgroupPause,
    onBrowseTools,
    onBrowseSkills,
    onBrowseMemory,
    onBrowseSchedule,
    onOpenHistory,
    onToggleNotifications,
    onToggleActivity,
    onOpenShortcuts,
  ]);
}
