import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import BrowsePanel from "../primitives/BrowsePanel.jsx";
import BrowseDetail from "../primitives/BrowseDetail.jsx";
import MarkdownBody from "../primitives/MarkdownBody.jsx";

const FILES = [
  { name: "USER.md", label: "Things alpi knows about you" },
  { name: "MEMORY.md", label: "Things alpi has learned" },
  { name: "AGENT.md", label: "Things alpi is" },
];

export default function MemoryPanel({ open, onClose, profile }) {
  const [files, setFiles] = useState([]);

  useEffect(() => {
    if (!open || !profile) return;
    let cancelled = false;
    invoke("profile_memory", { profile })
      .then((data) => {
        if (cancelled) return;
        const rows = FILES.map(({ name, label }) => {
          const raw = data?.[name] || "";
          const content = stripMemoryDelimiters(raw);
          return {
            name,
            category: "Files",
            description: label,
            content,
            tag: humanBytes(raw.length),
          };
        });
        setFiles(rows);
      })
      .catch(() => !cancelled && setFiles([]));
    return () => {
      cancelled = true;
    };
  }, [open, profile]);

  return (
    <BrowsePanel
      open={open}
      onClose={onClose}
      title="memory"
      kicker="· files read on every turn"
      items={files}
      categoryOrder={["Files"]}
      emptyText="No memory files"
      renderDetail={(f) => (
        <BrowseDetail name={f.name} description={f.description}>
          {f.content ? <MarkdownBody source={f.content} /> : <em>(empty)</em>}
        </BrowseDetail>
      )}
    />
  );
}

// `§` on its own line is alpi's v2 memory entry delimiter (alpi/memory.py).
function stripMemoryDelimiters(text) {
  return text.replace(/^§$/gm, "").replace(/\n{3,}/g, "\n\n");
}

function humanBytes(n) {
  if (n < 1024) return `${n}b`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)}kb`;
  return `${(n / (1024 * 1024)).toFixed(1)}mb`;
}
