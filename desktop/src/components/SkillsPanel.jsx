import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import BrowsePanel from "../primitives/BrowsePanel.jsx";
import { renderMarkdown } from "../lib/markdown.js";
import styles from "./SkillsPanel.module.css";

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
      renderDetail={(s) => <SkillDetail skill={s} />}
    />
  );
}

function SkillDetail({ skill }) {
  return (
    <div className={styles.wrap}>
      <h3 className={styles.name}>{skill.name}</h3>
      {skill.description && (
        <p className={styles.description}>{skill.description}</p>
      )}
      {skill.path && <div className={styles.path}>{skill.path}</div>}
      {skill.body && (
        <div
          className={styles.body}
          dangerouslySetInnerHTML={{ __html: renderMarkdown(skill.body) }}
        />
      )}
    </div>
  );
}
