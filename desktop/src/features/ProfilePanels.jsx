import { useMemo, useRef } from "react";
import { BrowseShell } from "../primitives/BrowseModal.jsx";
import { PROFILE_PANELS } from "../lib/profilePanels.js";
import { attentionLabel, flagCount } from "../../../common/attention.mjs";
import { useAttention } from "../lib/useAttention.js";
import { MemoryPanel } from "./MemoryModal.jsx";
import { SchedulePanel } from "./ScheduleModal.jsx";
import { SkillsPanel } from "./SkillsModal.jsx";
import { ToolsPanel } from "./ToolsModal.jsx";

export default function ProfilePanels({ section, onSection, onClose, owner, profile, connectionId, canEdit = false, openJob = null, guardRef = null }) {
  const found = PROFILE_PANELS.find((p) => p.id === section) ?? null;
  const last = useRef({ section, panel: found });
  if (found) last.current = { section, panel: found };
  const panel = found ?? last.current.panel;
  const shown = found ? section : last.current.section;
  const attention = useAttention({ open: !!found, profile, connectionId });
  const badges = useMemo(() => Object.fromEntries(PROFILE_PANELS.map((p) => [p.id, { count: flagCount(attention, p.id), label: attentionLabel(attention, p.id) }])), [attention]);
  const shared = { profile, connectionId, owner, onSection, attention };
  return (
    <BrowseShell open={!!found} onClose={onClose} guardRef={guardRef} badges={badges} label={panel ? [owner?.name ?? profile, panel.label].filter(Boolean).join(" · ") : ""}>
      {shown === "skills" ? <SkillsPanel key="skills" {...shared} /> : null}
      {shown === "tools" ? <ToolsPanel key="tools" {...shared} /> : null}
      {shown === "schedule" ? <SchedulePanel key="schedule" {...shared} openJob={openJob} /> : null}
      {shown === "memory" ? <MemoryPanel key="memory" {...shared} canEdit={canEdit} /> : null}
    </BrowseShell>
  );
}
