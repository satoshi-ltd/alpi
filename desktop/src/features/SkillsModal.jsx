import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { BrowseModal, Eyebrow, Icon, Lock, StatusPill as DSStatusPill } from "../primitives/index.js";
import Markdown from "../primitives/Markdown.jsx";
import CodeView from "../primitives/CodeView.jsx";
import shell from "../primitives/BrowseModal.module.css";
import styles from "./SkillsModal.module.css";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function formatBytes(n) {
  const b = Number(n) || 0;
  if (b < 1024) return `${b}b`;
  const kb = b / 1024;
  if (kb < 1024) return `${kb.toFixed(1)}kb`;
  return `${(kb / 1024).toFixed(1)}mb`;
}

export function fileIconName(ftype) {
  if (ftype === "skill") return "sparkle";
  if (ftype === "py") return "cpu";
  if (ftype === "md" || ftype === "text") return "eye";
  return "folder";
}

export function formatSkillDate(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || "").trim());
  if (!m) return String(iso || "").trim();
  const mi = Number(m[2]) - 1;
  if (mi < 0 || mi > 11) return iso.trim();
  return `${MONTHS[mi]} ${Number(m[3])}`;
}

export function matchesSkill(skill, query) {
  const needle = String(query || "").trim().toLowerCase();
  if (!needle) return true;
  const hay = [skill.name, skill.category, skill.description, ...(skill.keywords || [])]
    .filter(Boolean).join(" ").toLowerCase();
  return hay.includes(needle);
}

export function viewerKind(file) {
  if (!file) return "empty";
  if (file.binary) return "binary";
  if (file.ftype === "skill" || file.ftype === "md") return "markdown";
  return "code";
}

export function isMcpTool(name) {
  return String(name || "").includes("__");
}

export function displayTool(name) {
  return isMcpTool(name) ? String(name).replace("__", ".") : String(name);
}

export function orderTools(tools) {
  return [...(tools || [])].sort((a, b) => (isMcpTool(a) ? 1 : 0) - (isMcpTool(b) ? 1 : 0));
}

export function groupSkills(skills) {
  const byCat = new Map();
  for (const s of skills) {
    const cat = s.category || "uncategorized";
    if (!byCat.has(cat)) byCat.set(cat, []);
    byCat.get(cat).push(s);
  }
  return [...byCat.keys()]
    .sort((a, b) => (a === "uncategorized") - (b === "uncategorized") || a.localeCompare(b))
    .map((cat) => ({ cat, skills: byCat.get(cat) }));
}

function sameSkill(a, b) {
  return !!a && !!b && a.name === b.name && (a.category || null) === (b.category || null);
}

export default function SkillsModal({ open, onClose, profile, connectionId }) {
  const [skills, setSkills] = useState([]);
  const [listLoading, setListLoading] = useState(false);
  const [listError, setListError] = useState(null);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [selectedPath, setSelectedPath] = useState("SKILL.md");
  const [file, setFile] = useState(null);
  const [fileLoading, setFileLoading] = useState(false);
  const [openDirs, setOpenDirs] = useState(() => new Set());

  useEffect(() => {
    if (!open || !profile) return undefined;
    let cancelled = false;
    setSkills([]);
    setSelected(null);
    setDetail(null);
    setFile(null);
    setListError(null);
    setListLoading(true);
    invoke("profile_skills", { profile, connectionId })
      .then((rows) => { if (!cancelled) setSkills(Array.isArray(rows) ? rows : []); })
      .catch((e) => {
        if (!cancelled) {
          setSkills([]);
          setListError(String(e));
        }
      })
      .finally(() => { if (!cancelled) setListLoading(false); });
    return () => { cancelled = true; };
  }, [open, profile, connectionId]);

  useEffect(() => {
    if (!skills.length) { if (selected) setSelected(null); return; }
    if (!skills.some((s) => sameSkill(s, selected))) {
      setSelected({ name: skills[0].name, category: skills[0].category || null });
    }
  }, [skills, selected]);

  useEffect(() => {
    if (!open || !selected || !profile) return undefined;
    let cancelled = false;
    setDetail(null);
    setDetailLoading(true);
    setSelectedPath("SKILL.md");
    setFile(null);
    invoke("profile_skill_read", { profile, name: selected.name, category: selected.category || null, connectionId })
      .then((d) => {
        if (cancelled) return;
        setDetail(d || null);
        const dirs = (d?.tree || []).filter((n) => n.kind === "dir" && !n.locked && (n.children || []).length);
        setOpenDirs(new Set(dirs.map((n) => n.name)));
      })
      .catch(() => { if (!cancelled) setDetail(null); })
      .finally(() => { if (!cancelled) setDetailLoading(false); });
    return () => { cancelled = true; };
  }, [open, selected, profile, connectionId]);

  useEffect(() => {
    if (!detail || !selectedPath || selectedPath === "SKILL.md") return undefined;
    let cancelled = false;
    setFileLoading(true);
    invoke("profile_skill_file", {
      profile, name: detail.name, category: detail.category || null, path: selectedPath, connectionId,
    })
      .then((f) => { if (!cancelled) setFile(f || null); })
      .catch(() => { if (!cancelled) setFile(null); })
      .finally(() => { if (!cancelled) setFileLoading(false); });
    return () => { cancelled = true; };
  }, [detail, selectedPath, profile, connectionId]);

  const filtered = useMemo(() => skills.filter((s) => matchesSkill(s, query)), [skills, query]);
  const groups = useMemo(() => groupSkills(filtered), [filtered]);

  const onToggleDir = useCallback((name) => {
    setOpenDirs((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name); else next.add(name);
      return next;
    });
  }, []);

  const currentFile = useMemo(() => {
    if (!detail) return null;
    if (selectedPath === "SKILL.md") return { ftype: "skill", binary: false, text: detail.body, size: 0 };
    return file;
  }, [detail, selectedPath, file]);

  const list = (
    <ul className={shell.list} role="listbox">
      {listLoading ? (
        <li className={shell.empty}>
          <span className={shell.emptyTitle}>Loading skills…</span>
        </li>
      ) : listError ? (
        <li className={shell.empty}>
          <span className={shell.emptyTitle}>Could not load skills</span>
          <span className={shell.emptyHint}>{listError}</span>
        </li>
      ) : skills.length === 0 ? (
        <li className={shell.empty}>
          <span className={shell.emptyTitle}>No skills installed</span>
          <span className={shell.emptyHint}>
            Skills are created by talking to the agent — ask it to build one.
          </span>
        </li>
      ) : filtered.length === 0 ? (
        <li className={shell.empty}>
          <span className={shell.emptyTitle}>No matches</span>
          <span className={shell.emptyHint}>Try a different query, or clear it.</span>
        </li>
      ) : (
        groups.map((g) => (
          <Fragment key={g.cat}>
            <Eyebrow as="li" className={shell.groupHeader} role="presentation">{g.cat}</Eyebrow>
            {g.skills.map((s) => (
              <SkillRow
                key={`${s.category || ""}/${s.name}`}
                skill={s}
                active={sameSkill(s, selected)}
                onSelect={() => setSelected({ name: s.name, category: s.category || null })}
              />
            ))}
          </Fragment>
        ))
      )}
    </ul>
  );

  return (
    <BrowseModal
      open={open}
      onClose={onClose}
      title="Skills"
      count={skills.length}
      kicker="instructions the agent loads on demand"
      search={{ value: query, onChange: setQuery, placeholder: "Search skills…", label: "Search skills" }}
      list={list}
      loading={listLoading || detailLoading}
      loadingLabel={listLoading ? "Loading skills" : "Loading skill detail"}
    >
      {detail ? (
        <DetailPane
          detail={detail}
          selectedPath={selectedPath}
          openDirs={openDirs}
          onToggleDir={onToggleDir}
          onSelectFile={setSelectedPath}
          file={currentFile}
          fileLoading={fileLoading && selectedPath !== "SKILL.md"}
        />
      ) : detailLoading ? (
        <div className={shell.detailEmpty}>Loading skill…</div>
      ) : (
        <div className={shell.detailEmpty}>Select a skill.</div>
      )}
    </BrowseModal>
  );
}

function StatusDot({ status }) {
  const tone = status === "active" ? styles.dotActive
    : status === "invalid" ? styles.dotInvalid : styles.dotInactive;
  return <span aria-hidden className={`${styles.dot} ${tone}`} />;
}

function SkillRow({ skill, active, onSelect }) {
  return (
    <li>
      <button
        type="button"
        className={`${shell.row} ${styles.skillRow} ${active ? shell.rowActive : ""} ${skill.status !== "active" ? shell.rowMuted : ""}`}
        onClick={onSelect}
        role="option"
        aria-selected={active}
      >
        <span className={styles.rowHead}>
          <StatusDot status={skill.status} />
          <span className={styles.rowId}>{skill.name}</span>
          <span className={shell.sizeTag}>{formatBytes(skill.size)}</span>
        </span>
        {skill.description ? <span className={styles.rowBlurb}>{skill.description}</span> : null}
      </button>
    </li>
  );
}

function DetailPane({ detail, selectedPath, openDirs, onToggleDir, onSelectFile, file, fileLoading }) {
  const inactive = detail.status === "inactive";
  const invalid = detail.status === "invalid";
  return (
    <>
      <div className={shell.detailMeta}>
        <span className={styles.detailName}>
          {detail.category ? <span className={styles.detailCat}>{detail.category}/</span> : null}
          <span>{detail.name}</span>
        </span>
        <StatusPill status={detail.status} reason={detail.reason} />
        <span className={shell.detailMetaSpacer} />
        <SkillMeta detail={detail} />
      </div>

      <div className={styles.article}>
        {inactive || invalid ? (
          <div className={`${styles.callout} ${invalid ? styles.calloutInvalid : ""}`}>
            <span className={styles.calloutDot} aria-hidden />
            <span>
              {invalid ? "Invalid — " : "Inactive — "}
              <span className={styles.calloutReason}>{detail.reason}</span>
              {invalid ? "." : ". Resolve it and the skill activates next session."}
            </span>
          </div>
        ) : null}

        <Frontmatter detail={detail} />

        {detail.tree?.length ? (
          <div className={styles.dirBox}>
            <SkillTree
              tree={detail.tree}
              selectedPath={selectedPath}
              openDirs={openDirs}
              onToggle={onToggleDir}
              onSelectFile={onSelectFile}
            />
            <div className={styles.viewer}>
              <FileViewer file={file} loading={fileLoading} />
            </div>
          </div>
        ) : null}
      </div>
    </>
  );
}

function StatusPill({ status, reason }) {
  const tone = status === "active" ? "on" : status === "invalid" ? "bad" : "off";
  const label = status === "active" ? "active" : status === "invalid" ? "invalid" : "inactive";
  return (
    <DSStatusPill tone={tone} title={status === "active" ? undefined : reason || undefined}>
      {label}
    </DSStatusPill>
  );
}

function SkillMeta({ detail }) {
  const parts = [];
  if (detail.version) parts.push(<Fragment key="v">v{detail.version}</Fragment>);
  parts.push(<Fragment key="o">{detail.origin || "agent"}</Fragment>);
  const date = formatSkillDate(detail.created_at);
  if (date) parts.push(<Fragment key="d">{date}</Fragment>);
  return (
    <span className={styles.detailInfo}>
      {parts.map((p, i) => (
        <Fragment key={i}>
          {i > 0 ? <span className={styles.detailInfoDot} aria-hidden>·</span> : null}
          {p}
        </Fragment>
      ))}
    </span>
  );
}

function Frontmatter({ detail }) {
  return (
    <div className={styles.card}>
      {detail.description ? (
        <FmRow label="about"><span className={styles.about}>{detail.description}</span></FmRow>
      ) : null}
      {detail.requires?.length ? (
        <FmRow label="requires">
          <span className={styles.reqList}>
            {detail.requires.map((r) => (
              <span key={`${r.kind}:${r.name}`} className={styles.req}>
                <span aria-hidden className={`${styles.reqDot} ${r.resolved ? styles.reqOk : styles.reqNo}`} />
                <span className={`${styles.reqName} ${r.resolved ? "" : styles.reqMissing}`}>{r.name}</span>
              </span>
            ))}
          </span>
        </FmRow>
      ) : null}
      {detail.tools?.length ? (
        <FmRow label="tools">
          <span className={styles.kwFlow}>
            {orderTools(detail.tools).map((t) => <span key={t} className={styles.kw}>{displayTool(t)}</span>)}
          </span>
        </FmRow>
      ) : null}
      {detail.platforms?.length ? (
        <FmRow label="platforms">
          <span className={styles.kwFlow}>
            {detail.platforms.map((p) => <span key={p} className={styles.kw}>{p}</span>)}
          </span>
        </FmRow>
      ) : null}
      {detail.keywords?.length ? (
        <FmRow label="keywords">
          <span className={styles.kwFlow}>
            {detail.keywords.map((k) => <span key={k} className={styles.kw}>{k}</span>)}
          </span>
        </FmRow>
      ) : null}
    </div>
  );
}

function FmRow({ label, children }) {
  return (
    <div className={styles.fmRow}>
      <Eyebrow className={styles.fmLabel}>{label}</Eyebrow>
      <span className={styles.fmValue}>{children}</span>
    </div>
  );
}

function SkillTree({ tree, selectedPath, openDirs, onToggle, onSelectFile }) {
  return (
    <div className={styles.tree}>
      <Eyebrow className={styles.treeRoot}>files</Eyebrow>
      {tree.map((node) => {
        if (node.kind === "file") {
          return (
            <FileRow
              key={node.name}
              node={node}
              path={node.name}
              active={selectedPath === node.name}
              nested={false}
              onSelect={onSelectFile}
            />
          );
        }
        if (node.locked) {
          return (
            <div key={node.name} className={`${styles.treeRow} ${styles.treeSecrets}`}>
              <Lock className={styles.treeIcon} size="sm" />
              <span className={styles.treeName}>{node.name}/</span>
              <span className={styles.treeMeta}>{node.count ? `${node.count} · ${node.mode}` : "empty"}</span>
            </div>
          );
        }
        const children = node.children || [];
        const empty = children.length === 0;
        const expanded = openDirs.has(node.name) && !empty;
        return (
          <Fragment key={node.name}>
            <button
              type="button"
              className={`${styles.treeRow} ${empty ? styles.treeRowStatic : ""}`.trim()}
              onClick={() => !empty && onToggle(node.name)}
            >
              <Icon
                name="chevron-right"
                size="sm"
                className={`${styles.treeChevron} ${expanded ? styles.treeChevronOpen : ""} ${empty ? styles.treeChevronEmpty : ""}`.trim()}
              />
              <span className={styles.treeName}>{node.name}/</span>
              {empty ? <span className={styles.treeMeta}>empty</span> : null}
            </button>
            {expanded ? children.map((c) => (
              <FileRow
                key={c.name}
                node={c}
                path={`${node.name}/${c.name}`}
                active={selectedPath === `${node.name}/${c.name}`}
                nested
                onSelect={onSelectFile}
              />
            )) : null}
          </Fragment>
        );
      })}
    </div>
  );
}

function FileRow({ node, path, active, nested, onSelect }) {
  return (
    <button
      type="button"
      className={`${styles.treeRow} ${styles.treeFile} ${active ? styles.treeFileActive : ""} ${nested ? styles.treeFileNested : ""}`.trim()}
      onClick={() => onSelect(path)}
    >
      <Icon name={fileIconName(node.ftype)} size="sm" className={styles.treeIcon} />
      <span className={styles.treeName}>{node.name}</span>
    </button>
  );
}

function FileViewer({ file, loading }) {
  if (loading) return <div className={styles.viewerLoading}>Loading…</div>;
  const kind = viewerKind(file);
  if (kind === "binary") {
    return (
      <div className={styles.viewerBinary}>
        <Icon name="folder" size="lg" />
        <span>binary · {formatBytes(file.size)}</span>
      </div>
    );
  }
  if (kind === "markdown") {
    return (
      <div className={styles.mdBox}>
        {file.text ? (
          <Markdown source={file.text} className="alpi-md" />
        ) : (
          <div className={styles.viewerLoading}>Empty file.</div>
        )}
      </div>
    );
  }
  if (kind === "code") return <CodeView text={file.text || ""} lang={file.ftype} />;
  return <div className={styles.viewerLoading}>Select a file.</div>;
}
