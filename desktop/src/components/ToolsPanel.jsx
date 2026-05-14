import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import BrowsePanel from "../primitives/BrowsePanel.jsx";
import BrowseDetail from "../primitives/BrowseDetail.jsx";
import styles from "./ToolsPanel.module.css";

// MCP categories (``MCP · <server>``) and ``Other`` fall through to the
// end of the panel in registration order, after the static ones below.
const CATEGORY_ORDER = [
  "Filesystem",
  "Workspace",
  "Web",
  "Memory",
  "Comms",
  "Agent",
  "Media",
  "System",
  "Collab",
];

export default function ToolsPanel({ open, onClose, profile }) {
  const [tools, setTools] = useState([]);

  useEffect(() => {
    if (!open || !profile) return;
    let cancelled = false;
    invoke("profile_tools", { profile })
      .then((rows) => {
        if (cancelled) return;
        const arr = Array.isArray(rows) ? rows : [];
        setTools(arr);
      })
      .catch(() => !cancelled && setTools([]));
    return () => {
      cancelled = true;
    };
  }, [open, profile]);

  return (
    <BrowsePanel
      open={open}
      onClose={onClose}
      title="Tools"
      items={tools}
      categoryOrder={CATEGORY_ORDER}
      emptyText="No tools registered"
      renderDetail={(t) => <ToolDetail tool={t} />}
    />
  );
}

function ToolDetail({ tool }) {
  const props = tool.parameters?.properties || {};
  const required = new Set(tool.parameters?.required || []);
  const rows = Object.entries(props);

  return (
    <BrowseDetail name={tool.name} description={tool.description}>
      {rows.length > 0 ? (
        <table className={styles.params}>
          <thead>
            <tr>
              <th>Parameter</th>
              <th>Type</th>
              <th>Required</th>
              <th>Description</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([key, schema]) => (
              <tr key={key}>
                <td className={styles.paramName}>{key}</td>
                <td className={styles.paramType}>{formatType(schema)}</td>
                <td className={styles.paramReq}>{required.has(key) ? "yes" : "—"}</td>
                <td className={styles.paramDesc}>{schema.description || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className={styles.noParams}>No parameters</div>
      )}
    </BrowseDetail>
  );
}

function formatType(schema) {
  if (!schema) return "any";
  if (schema.enum) return `enum: ${schema.enum.join(" | ")}`;
  if (schema.type === "array" && schema.items?.type) return `${schema.items.type}[]`;
  return schema.type || "any";
}
