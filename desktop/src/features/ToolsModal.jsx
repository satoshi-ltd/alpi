import { Fragment, useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { Banner, Eyebrow } from "../primitives/index.js";
import shell from "../primitives/BrowseModal.module.css";
import { BrowseBody, BrowseDetailHead, BrowseRow, BrowseShell, FactTable } from "../primitives/BrowseModal.jsx";
import { PROFILE_PANELS } from "../lib/profilePanels.js";
import { SkeletonReader, SkeletonRows } from "../primitives/Skeleton.jsx";
import MarkdownBody from "../primitives/MarkdownBody.jsx";
import styles from "./ToolsModal.module.css";
import { EMPTY } from "../../../common/emptyCopy.mjs";
import { firstSentence } from "../../../common/panelRow.mjs";

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

export function ToolsPanel({ open = true, profile, connectionId, owner = null, onSection = null }) {
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
        <SkeletonRows as="li" mark={false} />
      ) : error ? (
        <li className={shell.empty}>
          <span className={shell.emptyTitle}>Could not load tools</span>
          <span className={shell.emptyHint}>{error}</span>
        </li>
      ) : tools.length === 0 ? (
        <li className={shell.empty}>
          <span className={shell.emptyTitle}>{EMPTY.tools.title}</span>
          <span className={shell.emptyHint}>{EMPTY.tools.hint}</span>
        </li>
      ) : filtered.length === 0 ? (
        <li className={shell.empty}>
          <span className={shell.emptyTitle}>{EMPTY.matches.title}</span>
          <span className={shell.emptyHint}>{EMPTY.matches.hint}</span>
        </li>
      ) : groups.map((g) => (
        <Fragment key={g.cat}>
          <Eyebrow as="li" className={shell.groupHeader} role="presentation">{g.cat}</Eyebrow>
          {g.tools.map((t) => (
            <BrowseRow
              key={t.name}
              title={t.name}
              sub={firstSentence(t.description)}
              meta={t.denied ? "denied" : null}
              off={!!t.denied}
              active={t.name === selected?.name}
              onSelect={() => setSelected(t)}
            />
          ))}
        </Fragment>
      ))}
    </ul>
  );

  return (
    <BrowseBody
      owner={owner}
      sections={owner ? PROFILE_PANELS : null}
      section="tools"
      onSection={onSection}
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
        <SkeletonReader />
      ) : (
        <div className={shell.detailEmpty}>Select a tool.</div>
      )}
    </BrowseBody>
  );
}

function ToolDetail({ tool }) {
  const props = tool.parameters?.properties || {};
  const required = new Set(tool.parameters?.required || []);
  const rows = Object.entries(props);
  return (
    <>
      <BrowseDetailHead
        title={tool.name}
        state={tool.denied ? "denied" : null}
        id={tool.name}
      />
      <div className={shell.detailBody}>
        {tool.denied ? (
          <div className={styles.deny}>
            <Banner kind="warning">
              Denied for this profile via <code>tools.deny</code> in <code>config.yaml</code>. The agent does not see this tool.
            </Banner>
          </div>
        ) : null}
        <FactTable
          rows={[
            { label: "About", value: tool.description ? <MarkdownBody source={tool.description} className={shell.factMd} /> : null },
            { label: "Category", value: tool.category || null },
          ]}
        />
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

export default function ToolsModal({ open, onClose, ...panel }) {
  return (
    <BrowseShell open={open} onClose={onClose} label="Tools">
      <ToolsPanel {...panel} />
    </BrowseShell>
  );
}
