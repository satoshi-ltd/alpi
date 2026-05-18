import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import BrowsePanel from "../primitives/BrowsePanel.jsx";
import BrowseDetail from "../primitives/BrowseDetail.jsx";
import MarkdownBody from "../primitives/MarkdownBody.jsx";

// Skills layout on disk: `<profile>/skills/<category>/<skill>/SKILL.md`.
function formatCategory(raw) {
  if (!raw) return "Uncategorized";
  return raw.charAt(0).toUpperCase() + raw.slice(1).replace(/-/g, " ");
}

export default function SkillsPanel({ open, onClose, profile }) {
  const [skills, setSkills] = useState([]);

  useEffect(() => {
    if (!open || !profile) return;
    let cancelled = false;
    invoke("profile_skills", { profile })
      .then((rows) => {
        if (cancelled) return;
        const arr = Array.isArray(rows) ? rows : [];
        setSkills(
          arr.map((s) => ({
            ...s,
            category: formatCategory(s.category),
            description: s.description || "",
          })),
        );
      })
      .catch(() => !cancelled && setSkills([]));
    return () => {
      cancelled = true;
    };
  }, [open, profile]);

  const categoryOrder = [
    ...new Set(skills.map((s) => s.category).filter((c) => c !== "Uncategorized")),
  ]
    .sort()
    .concat("Uncategorized");

  return (
    <BrowsePanel
      open={open}
      onClose={onClose}
      title="skills"
      kicker="· instructions the agent loads on demand"
      items={skills}
      categoryOrder={categoryOrder}
      alwaysShowGroups
      emptyText="No skills installed"
      renderDetail={(s) => (
        <BrowseDetail name={s.name} description={s.description} path={s.path}>
          <MarkdownBody source={s.body} />
        </BrowseDetail>
      )}
    />
  );
}
