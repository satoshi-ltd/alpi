import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { AlertBanner, Banner, Eyebrow, Icon } from "../primitives/index.js";
import Markdown from "../primitives/Markdown.jsx";
import CodeView from "../primitives/CodeView.jsx";
import shell from "../primitives/BrowseModal.module.css";
import { BrowseBody, BrowseDetailHead, BrowseRow, BrowseShell, FactTable } from "../primitives/BrowseModal.jsx";
import { PROFILE_PANELS } from "../lib/profilePanels.js";
import { SkeletonReader, SkeletonRows } from "../primitives/Skeleton.jsx";
import styles from "./SkillsModal.module.css";
import { skillBanner, skillItem, skillWord } from "../../../common/attention.mjs";
import { EMPTY } from "../../../common/emptyCopy.mjs";
import { skillFileIcon } from "../../../common/fileKind.mjs";
import { factLabel, sizeLabel, skillMeta } from "../../../common/panelRow.mjs";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function fileIconName(node) {
  return skillFileIcon(node);
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

export function SkillsPanel({ open = true, profile, connectionId, owner = null, onSection = null, attention = null }) {
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

  const pickedRef = useRef(false);
  const settledRef = useRef(false);
  useEffect(() => { pickedRef.current = false; settledRef.current = false; }, [open, profile, connectionId]);

  useEffect(() => {
    if (!skills.length) { if (selected) setSelected(null); return; }
    const flagged = skills.find((s) => skillItem(attention, s.category, s.name));
    const first = flagged ?? skills[0];
    const want = { name: first.name, category: first.category || null };
    const lost = !skills.some((s) => sameSkill(s, selected));
    const lift = !settledRef.current && !pickedRef.current && !!attention && !sameSkill(want, selected);
    if (attention) settledRef.current = true;
    if (lost || lift) setSelected(want);
  }, [skills, selected, attention]);

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
  const flagOf = useCallback((s) => skillItem(attention, s.category, s.name), [attention]);
  const needs = useMemo(() => filtered.filter((s) => flagOf(s)), [filtered, flagOf]);
  const groups = useMemo(() => groupSkills(filtered.filter((s) => !flagOf(s))), [filtered, flagOf]);
  const selectedFlag = selected ? skillItem(attention, selected.category, selected.name) : null;

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
        <SkeletonRows as="li" />
      ) : listError ? (
        <li className={shell.empty}>
          <span className={shell.emptyTitle}>Could not load skills</span>
          <span className={shell.emptyHint}>{listError}</span>
        </li>
      ) : skills.length === 0 ? (
        <li className={shell.empty}>
          <span className={shell.emptyTitle}>{EMPTY.skills.title}</span>
          <span className={shell.emptyHint}>{EMPTY.skills.hint}</span>
        </li>
      ) : filtered.length === 0 ? (
        <li className={shell.empty}>
          <span className={shell.emptyTitle}>{EMPTY.matches.title}</span>
          <span className={shell.emptyHint}>{EMPTY.matches.hint}</span>
        </li>
      ) : (
        <>
        {needs.length ? (
          <>
            <Eyebrow as="li" className={shell.groupHeader} role="presentation">{`Needs you · ${needs.length}`}</Eyebrow>
            {needs.map((s) => (
              <SkillRow
                key={`${s.category || ""}/${s.name}`}
                skill={s}
                flag={flagOf(s)}
                active={sameSkill(s, selected)}
                onSelect={() => { pickedRef.current = true; setSelected({ name: s.name, category: s.category || null }); }}
              />
            ))}
          </>
        ) : null}
        {groups.map((g) => (
          <Fragment key={g.cat}>
            <Eyebrow as="li" className={shell.groupHeader} role="presentation">{factLabel(g.cat)}</Eyebrow>
            {g.skills.map((s) => (
              <SkillRow
                key={`${s.category || ""}/${s.name}`}
                skill={s}
                active={sameSkill(s, selected)}
                onSelect={() => { pickedRef.current = true; setSelected({ name: s.name, category: s.category || null }); }}
              />
            ))}
          </Fragment>
        ))}
        </>
      )}
    </ul>
  );

  return (
    <BrowseBody
      owner={owner}
      sections={owner ? PROFILE_PANELS : null}
      section="skills"
      onSection={onSection}
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
          flag={selectedFlag}
        />
      ) : detailLoading ? (
        <SkeletonReader />
      ) : (
        <div className={shell.detailEmpty}>Select a skill.</div>
      )}
    </BrowseBody>
  );
}

function SkillRow({ skill, active, onSelect, flag = null }) {
  const { meta, tone } = skillMeta(skill, flag ? skillWord(flag) : null);
  return (
    <BrowseRow
      title={skill.name}
      sub={skill.description || null}
      meta={meta}
      metaTone={tone}
      off={skill.status !== "active"}
      active={active}
      onSelect={onSelect}
    />
  );
}

function DetailPane({ detail, selectedPath, openDirs, onToggleDir, onSelectFile, file, fileLoading, flag = null }) {
  const inactive = detail.status === "inactive";
  const invalid = detail.status === "invalid";
  const state = invalid ? "invalid" : inactive ? "inactive" : "active";
  return (
    <>
      <BrowseDetailHead
        title={detail.name}
        state={state}
        stateTone={invalid ? "danger" : null}
        id={detail.category ? `${detail.category}/${detail.name}` : detail.name}
      />

      <div className={styles.article}>
        {flag ? <AlertBanner {...skillBanner(flag)} /> : null}
        {!flag && (inactive || invalid) ? (
          <Banner kind={invalid ? "danger" : "warning"}>
            {invalid ? "Invalid — " : "Inactive — "}
            <strong>{detail.reason}</strong>
            {invalid ? "." : ". Resolve it and the skill activates next session."}
          </Banner>
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

export function skillVersion(detail) {
  return [detail.version ? `v${detail.version}` : null, detail.origin || "agent", formatSkillDate(detail.created_at) || null].filter(Boolean).join(" · ");
}

function Ids({ items }) {
  return items.map((it, i) => (
    <Fragment key={it.key}>
      {i > 0 ? ", " : null}
      <code className={it.missing ? styles.idMissing : undefined}>{it.name}</code>
      {it.missing ? <span className={styles.missing}> missing</span> : null}
    </Fragment>
  ));
}

function Frontmatter({ detail }) {
  const requires = detail.requires || [];
  return (
    <FactTable
      rows={[
        { label: "About", value: detail.description || null },
        { label: "Requires", value: requires.length ? <Ids items={requires.map((r) => ({ key: `${r.kind}:${r.name}`, name: r.name, missing: !r.resolved }))} /> : null },
        { label: "Tools", value: detail.tools?.length ? <Ids items={orderTools(detail.tools).map(displayTool).map((n) => ({ key: n, name: n, missing: false }))} /> : null },
        { label: "Platforms", value: detail.platforms?.length ? detail.platforms.join(", ") : null },
        { label: "Keywords", value: detail.keywords?.length ? detail.keywords.join(", ") : null },
        { label: "Version", value: skillVersion(detail) },
      ]}
    />
  );
}

function SkillTree({ tree, selectedPath, openDirs, onToggle, onSelectFile }) {
  return (
    <div className={styles.tree}>
      <Eyebrow className={styles.treeRoot}>Files</Eyebrow>
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
              <Icon name={fileIconName(node)} size="sm" className={styles.treeIcon} />
              <span className={styles.treeName}>{node.name}/</span>
              <span className={styles.treeMeta}>{node.count ? `${node.count} · ${node.mode}` : "Empty"}</span>
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
      <Icon name={fileIconName(node)} size="sm" className={styles.treeIcon} />
      <span className={styles.treeName}>{node.name}</span>
    </button>
  );
}

function FileViewer({ file, loading }) {
  if (loading) return <SkeletonReader heading={false} label="Loading file" className={styles.viewerSkeleton} />;
  const kind = viewerKind(file);
  if (kind === "binary") {
    return (
      <div className={styles.viewerBinary}>
        <Icon name={file.name ? fileIconName(file) : "file"} size="md" />
        <span>binary · {sizeLabel(file.size)}</span>
      </div>
    );
  }
  if (kind === "markdown") {
    return (
      <div className={styles.mdBox}>
        {file.text ? (
          <Markdown source={file.text} className="alpi-md" />
        ) : (
          <div className={styles.viewerNote}>Empty file.</div>
        )}
      </div>
    );
  }
  if (kind === "code") return <CodeView text={file.text || ""} lang={file.ftype} />;
  return <div className={styles.viewerNote}>Select a file.</div>;
}

export default function SkillsModal({ open, onClose, ...panel }) {
  return (
    <BrowseShell open={open} onClose={onClose} label="Skills">
      <SkillsPanel {...panel} />
    </BrowseShell>
  );
}
