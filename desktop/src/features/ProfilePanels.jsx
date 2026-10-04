import { BrowseShell } from "../primitives/BrowseModal.jsx";
import { PROFILE_PANELS } from "../lib/profilePanels.js";
import { MemoryPanel } from "./MemoryModal.jsx";
import { SchedulePanel } from "./ScheduleModal.jsx";
import { SkillsPanel } from "./SkillsModal.jsx";
import { ToolsPanel } from "./ToolsModal.jsx";

export default function ProfilePanels({ section, onSection, onClose, owner, profile, connectionId, canEdit = false, openJob = null, guardRef = null }) {
  const panel = PROFILE_PANELS.find((p) => p.id === section) ?? null;
  const shared = { profile, connectionId, owner, onSection };
  return (
    <BrowseShell open={!!panel} onClose={onClose} guardRef={guardRef} label={panel ? [owner?.name ?? profile, panel.label].filter(Boolean).join(" · ") : ""}>
      {section === "skills" ? <SkillsPanel key="skills" {...shared} /> : null}
      {section === "tools" ? <ToolsPanel key="tools" {...shared} /> : null}
      {section === "schedule" ? <SchedulePanel key="schedule" {...shared} openJob={openJob} /> : null}
      {section === "memory" ? <MemoryPanel key="memory" {...shared} canEdit={canEdit} /> : null}
    </BrowseShell>
  );
}
