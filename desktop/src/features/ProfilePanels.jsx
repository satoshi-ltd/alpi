import { useMemo } from "react";
import { BrowseShell } from "../primitives/BrowseModal.jsx";
import { PROFILE_PANELS } from "../lib/profilePanels.js";
import { attentionLabel, flagCount } from "../../../common/attention.mjs";
import { useAttention } from "../lib/useAttention.js";
import { MemoryPanel } from "./MemoryModal.jsx";
import { SchedulePanel } from "./ScheduleModal.jsx";
import { SkillsPanel } from "./SkillsModal.jsx";
import { ToolsPanel } from "./ToolsModal.jsx";

export default function ProfilePanels({ section, onSection, onClose, owner, profile, connectionId, canEdit = false, openJob = null, guardRef = null }) {
  const panel = PROFILE_PANELS.find((p) => p.id === section) ?? null;
  const attention = useAttention({ open: !!panel, profile, connectionId });
  const badges = useMemo(() => Object.fromEntries(PROFILE_PANELS.map((p) => [p.id, { count: flagCount(attention, p.id), label: attentionLabel(attention, p.id) }])), [attention]);
  const shared = { profile, connectionId, owner, onSection, attention };
  return (
    <BrowseShell open={!!panel} onClose={onClose} guardRef={guardRef} badges={badges} label={panel ? [owner?.name ?? profile, panel.label].filter(Boolean).join(" · ") : ""}>
      {section === "skills" ? <SkillsPanel key="skills" {...shared} /> : null}
      {section === "tools" ? <ToolsPanel key="tools" {...shared} /> : null}
      {section === "schedule" ? <SchedulePanel key="schedule" {...shared} openJob={openJob} /> : null}
      {section === "memory" ? <MemoryPanel key="memory" {...shared} canEdit={canEdit} /> : null}
    </BrowseShell>
  );
}
