import { useMemo } from "react";
import { profileLabel } from "../lib/profile-display.js";
import { orderedJumpTargets } from "../lib/profile-order.js";

export function useCommands({
  view,
  profiles,
  workgroups,
  pinned,
  searchOpen,
  activeProfileName = null,
  historyKind = null,
  onSelectProfile,
  onSelectWorkgroup,
  onOpenSettings,
  onCloseSettings,
  onToggleSearch,
  onNewProfile,
  onNewWorkgroup,
  onNewChat,
  onBrowseTools,
  onBrowseSkills,
  onBrowseMemory,
  onOpenHistory,
  onToggleNotifications,
  onToggleShortcuts,
}) {
  return useMemo(() => {
    const cmds = [];

    const jumpTargets = orderedJumpTargets({
      profiles,
      workgroups,
      pinnedProfiles: pinned?.profiles ?? [],
      pinnedWorkgroups: pinned?.workgroups ?? [],
    });

    jumpTargets.slice(0, 9).forEach((item, i) => {
      const hint = `⌘${i + 1}`;
      if (item.kind === "profile") {
        cmds.push({
          id: `nav:profile:${item.target.name}`,
          group: "Navigate",
          label: `Open @${profileLabel(item.target.name)}`,
          hint,
          action: () => onSelectProfile?.(item.target),
        });
      } else if (item.kind === "workgroup") {
        cmds.push({
          id: `nav:workgroup:${item.target.profile}/${item.target.id}`,
          group: "Navigate",
          label: `Open #${item.target.name || item.target.id}`,
          hint,
          action: () => onSelectWorkgroup?.(item.target),
        });
      }
    });

    if (historyKind === "sessions" && activeProfileName && onOpenHistory) {
      cmds.push({
        id: "chat:sessions",
        group: "Chat",
        label: `Switch @${profileLabel(activeProfileName)} sessions`,
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

    if (activeProfileName) {
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
    }

    if (view.kind === "settings" ? Boolean(onCloseSettings) : Boolean(onOpenSettings)) {
      cmds.push({
        id: "view:settings",
        group: "View",
        label: view.kind === "settings" ? "Close settings" : "Open settings",
        hint: "⌘,",
        action: () =>
          view.kind === "settings" ? onCloseSettings?.() : onOpenSettings?.(),
      });
    }

    if (onToggleNotifications) {
      cmds.push({
        id: "view:notifications",
        group: "View",
        label: "Notifications",
        hint: "⌘O",
        action: () => onToggleNotifications(),
      });
    }

    if (onToggleShortcuts) {
      cmds.push({
        id: "view:shortcuts",
        group: "View",
        label: "Keyboard shortcuts",
        hint: "⌘/",
        action: () => onToggleShortcuts(),
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

    return cmds;
  }, [
    view,
    profiles,
    workgroups,
    pinned,
    searchOpen,
    activeProfileName,
    historyKind,
    onSelectProfile,
    onSelectWorkgroup,
    onOpenSettings,
    onCloseSettings,
    onToggleSearch,
    onNewProfile,
    onNewWorkgroup,
    onNewChat,
    onBrowseTools,
    onBrowseSkills,
    onBrowseMemory,
    onOpenHistory,
    onToggleNotifications,
    onToggleShortcuts,
  ]);
}
