import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import BrowsePanel from "../primitives/BrowsePanel.jsx";
import BrowseDetail from "../primitives/BrowseDetail.jsx";
import MarkdownBody from "../primitives/MarkdownBody.jsx";

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
            category: s.category || "Top-level",
            description: s.description || "",
          })),
        );
      })
      .catch(() => !cancelled && setSkills([]));
    return () => {
      cancelled = true;
    };
  }, [open, profile]);

  return (
    <BrowsePanel
      open={open}
      onClose={onClose}
      title="Skills"
      items={skills}
      emptyText="No skills installed"
      renderDetail={(s) => (
        <BrowseDetail name={s.name} description={s.description} path={s.path}>
          <MarkdownBody source={s.body} />
        </BrowseDetail>
      )}
    />
  );
}
