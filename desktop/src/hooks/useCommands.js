import { useMemo } from "react";
import { profileLabel } from "../lib/profile-display.js";
import { orderedJumpTargets } from "../lib/profile-order.js";

export function useCommands({
  view,
  profiles,
  workgroups,
  pinned,
  searchOpen,
  collapsed,
  onSelectProfile,
  onSelectWorkgroup,
  onOpenSettings,
  onCloseSettings,
  onToggleSidebar,
  onToggleSearch,
  onNewProfile,
  onNewWorkgroup,
  onNewChat,
  onBrowseTools,
  onBrowseSkills,
  onBrowseMemory,
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

    if (view.kind !== "settings") {
      cmds.push({
        id: "view:sidebar",
        group: "View",
        label: collapsed ? "Show sidebar" : "Hide sidebar",
        hint: "⌘B",
        action: () => onToggleSidebar?.(),
      });
    }

    if (view.kind === "profile" || view.kind === "workgroup") {
      cmds.push({
        id: "view:find",
        group: "View",
        label: searchOpen ? "Close find" : "Find in transcript",
        hint: "⌘F",
        action: () => onToggleSearch?.(),
      });
    }

    if (view.kind === "profile" && view.profile) {
      cmds.push({
        id: "browse:tools",
        group: "Browse",
        label: "Tools",
        hint: "⇧⌘T",
        action: () => onBrowseTools?.(),
      });
      cmds.push({
        id: "browse:skills",
        group: "Browse",
        label: "Skills",
        hint: "⇧⌘S",
        action: () => onBrowseSkills?.(),
      });
      cmds.push({
        id: "browse:memory",
        group: "Browse",
        label: "Memory",
        hint: "⇧⌘M",
        action: () => onBrowseMemory?.(),
      });
    }

    if (view.kind === "profile") {
      cmds.push({
        id: "create:chat",
        group: "Create",
        label: "New chat",
        hint: "⌘N",
        action: () => onNewChat?.(),
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
    collapsed,
    onSelectProfile,
    onSelectWorkgroup,
    onOpenSettings,
    onCloseSettings,
    onToggleSidebar,
    onToggleSearch,
    onNewProfile,
    onNewWorkgroup,
    onNewChat,
    onBrowseTools,
    onBrowseSkills,
    onBrowseMemory,
  ]);
}
