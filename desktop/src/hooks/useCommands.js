import { useMemo } from "react";

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
  onNewProfile,
  onNewWorkgroup,
  onNewChat,
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
}) {
  return useMemo(() => {
    const cmds = [
      {
        id: "help:palette",
        group: "General",
        label: "Command palette",
        hint: "⌘K",
      },
      {
        id: "help:jump",
        group: "General",
        label: "Jump to profile / workgroup",
        hint: "⌘1–9",
      },
    ];

    if (onToggleSidebarSearch) {
      cmds.push({
        id: "view:find",
        group: "General",
        label: sidebarSearchOpen ? "Close filter" : "Filter alpis & workgroups",
        hint: "⌘S",
        action: () => onToggleSidebarSearch(),
      });
    }

    if (historyKind === "sessions" && activeProfileName && onOpenHistory) {
      cmds.push({
        id: "profile:sessions",
        group: "Profile",
        label: "Sessions",
        hint: "⇧⌘H",
        action: () => onOpenHistory(),
      });
    }

    if (view.kind === "profile") {
      cmds.push({
        id: "create:chat",
        group: "Chat",
        label: "New chat",
        hint: "⌘N",
        action: () => onNewChat?.(),
      });
    }

    if (view.kind === "profile" && onRefreshThread && canRefreshThread) {
      cmds.push({
        id: "chat:refresh",
        group: "Chat",
        label: "Refresh thread",
        hint: "⇧⌘R",
        action: () => onRefreshThread(),
      });
    }

    if (view.kind === "profile" && onToggleReadAloud && canReadAloud) {
      cmds.push({
        id: "chat:read-aloud",
        group: "Chat",
        label: readAloudActive ? "Stop audio" : "Read aloud",
        hint: "⇧⌘L",
        action: () => onToggleReadAloud(),
      });
    }

    if (view.kind === "profile" || view.kind === "workgroup") {
      cmds.push({
        id: "chat:find",
        group: "Chat",
        label: searchOpen ? "Close find" : "Find in transcript",
        hint: "⌘F",
        action: () => onToggleSearch?.(),
      });
    }

    if (historyKind === "tasks" && onOpenHistory) {
      cmds.push({
        id: "workgroup:tasks",
        group: "Workgroup",
        label: "Task history",
        hint: "⇧⌘H",
        action: () => onOpenHistory(),
      });
    }

    if (view.kind === "workgroup" && onToggleWorkgroupPause) {
      cmds.push({
        id: "workgroup:pause",
        group: "Workgroup",
        label: workgroupPaused ? "Resume workgroup" : "Pause workgroup",
        hint: "⇧⌘P",
        action: () => onToggleWorkgroupPause(),
      });
    }

    if (view.kind === "workgroup" && onRefreshThread) {
      cmds.push({
        id: "workgroup:refresh",
        group: "Workgroup",
        label: "Refresh thread",
        hint: "⇧⌘R",
        action: () => onRefreshThread(),
      });
    }

    if (activeProfileName) {
      if (onToggleProfilePause) {
        cmds.push({
          id: "profile:pause",
          group: "Profile",
          label: profilePaused ? "Resume profile" : "Pause profile",
          hint: "⇧⌘P",
          action: () => onToggleProfilePause(),
        });
      }
      cmds.push({
        id: "profile:tools",
        group: "Profile",
        label: "Tools",
        hint: "⇧⌘T",
        action: () => onBrowseTools?.(),
      });
      cmds.push({
        id: "profile:skills",
        group: "Profile",
        label: "Skills",
        hint: "⇧⌘S",
        action: () => onBrowseSkills?.(),
      });
      cmds.push({
        id: "profile:memory",
        group: "Profile",
        label: "Memory",
        hint: "⇧⌘M",
        action: () => onBrowseMemory?.(),
      });
      cmds.push({
        id: "profile:schedule",
        group: "Profile",
        label: "Schedule",
        hint: "⇧⌘E",
        action: () => onBrowseSchedule?.(),
      });
    }

    if (view.kind === "settings" ? Boolean(onCloseSettings) : Boolean(onOpenSettings)) {
      cmds.push({
        id: "view:settings",
        group: "General",
        label: view.kind === "settings" ? "Close settings" : "Open settings",
        hint: "⌘,",
        action: () =>
          view.kind === "settings" ? onCloseSettings?.() : onOpenSettings?.(),
      });
    }

    if (onToggleNotifications) {
      cmds.push({
        id: "view:notifications",
        group: "General",
        label: "Notifications",
        hint: "⌘O",
        action: () => onToggleNotifications(),
      });
    }

    if (onNewProfile) {
      cmds.push({
        id: "create:profile",
        group: "Create",
        label: "New profile",
        hint: "⇧⌘N",
        action: () => onNewProfile(),
      });
    }

    if (onNewWorkgroup) {
      cmds.push({
        id: "create:workgroup",
        group: "Create",
        label: "New workgroup",
        hint: "⇧⌘W",
        action: () => onNewWorkgroup(),
      });
    }

    [
      ["help:send", "Chat", "Send message", "⌘↵"],
      ["help:zoom-in", "View", "Zoom in", "⌘+"],
      ["help:zoom-out", "View", "Zoom out", "⌘-"],
      ["help:zoom-reset", "View", "Reset zoom", "⌘0"],
      ["help:close", "View", "Close / dismiss", "Esc"],
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
    activeProfileName,
    historyKind,
    onOpenSettings,
    onCloseSettings,
    onToggleSearch,
    onToggleSidebarSearch,
    sidebarSearchOpen,
    onNewProfile,
    onNewWorkgroup,
    onNewChat,
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
  ]);
}
