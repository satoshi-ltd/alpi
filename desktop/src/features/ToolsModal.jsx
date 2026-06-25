import { Fragment, useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { BrowseModal, Eyebrow } from "../primitives/index.js";
import shell from "../primitives/BrowseModal.module.css";
import MarkdownBody from "../primitives/MarkdownBody.jsx";
import styles from "./ToolsModal.module.css";

const CATEGORY_ORDER = [
  "Filesystem", "Workspace", "Web", "Memory", "Comms", "Agent", "Media", "System", "Collab",
];

export function formatType(schema) {
  if (!schema) return "any";
  if (schema.enum) return `enum: ${schema.enum.join(" | ")}`;
  if (schema.type === "array" && schema.items?.type) return `${schema.items.type}[]`;
  return schema.type || "any";
}

export function matchesTool(tool, query) {
  const needle = String(query || "").trim().toLowerCase();
  if (!needle) return true;
  return [tool.name, tool.category, tool.description].filter(Boolean).join(" ").toLowerCase().includes(needle);
}

export function groupTools(tools, order) {
  const byCat = new Map();
  for (const t of tools) {
    const cat = t.category || "Other";
    if (!byCat.has(cat)) byCat.set(cat, []);
    byCat.get(cat).push(t);
  }
  const rank = (c) => { const i = order.indexOf(c); return i === -1 ? order.length : i; };
  return [...byCat.keys()]
    .sort((a, b) => rank(a) - rank(b) || a.localeCompare(b))
    .map((cat) => ({ cat, tools: byCat.get(cat) }));
}

export default function ToolsModal({ open, onClose, profile, connectionId }) {
  const [tools, setTools] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    if (!open || !profile) return undefined;
    let cancelled = false;
    setTools([]);
    setSelected(null);
    setError(null);
    setLoading(true);
    invoke("profile_tools", { profile, connectionId })
      .then((rows) => { if (!cancelled) setTools(Array.isArray(rows) ? rows : []); })
      .catch((e) => {
        if (!cancelled) {
          setTools([]);
          setError(String(e));
        }
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [open, profile, connectionId]);

  useEffect(() => {
    if (!tools.length) { if (selected) setSelected(null); return; }
    if (!tools.some((t) => t.name === selected?.name)) setSelected(tools[0]);
  }, [tools, selected]);

  const filtered = useMemo(() => tools.filter((t) => matchesTool(t, query)), [tools, query]);
  const groups = useMemo(() => groupTools(filtered, CATEGORY_ORDER), [filtered]);
  const active = tools.find((t) => t.name === selected?.name) || null;

  const list = (
    <ul className={shell.list} role="listbox">
      {loading ? (
        <li className={shell.empty}>
          <span className={shell.emptyTitle}>Loading tools…</span>
        </li>
      ) : error ? (
        <li className={shell.empty}>
          <span className={shell.emptyTitle}>Could not load tools</span>
          <span className={shell.emptyHint}>{error}</span>
        </li>
      ) : tools.length === 0 ? (
        <li className={shell.empty}><span className={shell.emptyTitle}>No tools registered</span></li>
      ) : filtered.length === 0 ? (
        <li className={shell.empty}>
          <span className={shell.emptyTitle}>No matches</span>
          <span className={shell.emptyHint}>Try a different query, or clear it.</span>
        </li>
      ) : groups.map((g) => (
        <Fragment key={g.cat}>
          <Eyebrow as="li" className={shell.groupHeader} role="presentation">{g.cat}</Eyebrow>
          {g.tools.map((t) => (
            <li key={t.name}>
              <button
                type="button"
                className={`${shell.row} ${styles.toolRow} ${t.name === selected?.name ? shell.rowActive : ""}`}
                onClick={() => setSelected(t)}
                role="option"
                aria-selected={t.name === selected?.name}
              >
                <span className={`${styles.toolName} ${t.denied ? styles.toolMuted : ""}`}>{t.name}</span>
                <span className={styles.toolCount}>{t.denied ? "denied" : t.tag}</span>
              </button>
            </li>
          ))}
        </Fragment>
      ))}
    </ul>
  );

  return (
    <BrowseModal
      open={open}
      onClose={onClose}
      title="tools"
      count={tools.length}
      kicker="native callable functions"
      search={{ value: query, onChange: setQuery, placeholder: "Search tools…", label: "Search tools" }}
      list={list}
      loading={loading}
      loadingLabel="Loading tools"
    >
      {active ? (
        <ToolDetail tool={active} />
      ) : loading ? (
        <div className={shell.detailEmpty}>Loading tools…</div>
      ) : (
        <div className={shell.detailEmpty}>Select a tool.</div>
      )}
    </BrowseModal>
  );
}

function ToolDetail({ tool }) {
  const props = tool.parameters?.properties || {};
  const required = new Set(tool.parameters?.required || []);
  const rows = Object.entries(props);
  return (
    <>
      <div className={shell.detailMeta}>
        <span className={styles.toolNameLg}>
          {tool.category ? <span className={styles.detailCat}>{tool.category}/</span> : null}
          <span>{tool.name}</span>
        </span>
        <span className={shell.detailMetaSpacer} />
      </div>
      <div className={shell.detailScroll}>
        {tool.denied ? (
          <div className={styles.denyBanner}>
            Denied for this profile via <code>tools.deny</code> in <code>config.yaml</code>. The agent does not see this tool.
          </div>
        ) : null}
        {tool.description ? <MarkdownBody source={tool.description} mono /> : null}
        {rows.length > 0 ? (
          <table className={styles.params}>
            <thead>
              <tr><th>Parameter</th><th>Type</th><th>Required</th><th>Default</th></tr>
            </thead>
            <tbody>
              {rows.map(([key, schema]) => (
                <tr key={key}>
                  <td className={styles.paramName}>{key}</td>
                  <td className={styles.paramType}>{formatType(schema)}</td>
                  <td className={styles.paramReq}>{required.has(key) ? "yes" : "—"}</td>
                  <td className={styles.paramDef}>{schema?.default !== undefined ? String(schema.default) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className={styles.noParams}>No parameters</div>
        )}
      </div>
    </>
  );
}
