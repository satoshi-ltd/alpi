import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import Button from "../../primitives/Button.jsx";
import Chip from "../../primitives/Chip.jsx";
import Dropdown from "../../primitives/Dropdown.jsx";
import Textarea from "../../primitives/Textarea.jsx";
import { MemberRow as DsMemberRow } from "../../primitives/SettingsLayout.jsx";
import Skeleton from "../../primitives/Skeleton.jsx";
import { useNotify } from "../../primitives/Notification.jsx";
import { profileLabel } from "../../lib/profile-display.js";
import { Section, Row, CopyButton } from "./primitives.jsx";
import { ConfirmDelete, ConfirmDeleteAction } from "../../primitives/index.js";
import { SettingsHero } from "../../primitives/index.js";
import { Diamond, Dot, Mono } from "../../primitives/index.js";
import { BudgetEditor } from "./fields/alp.jsx";
import { useProfileDetail } from "../../hooks/useProfileDetail.js";
import styles from "./Settings.module.css";

function renderMemberRow(m, profiles, workgroup, hubPubkey, onRemove) {
  const local = profiles.find((p) => p.pubkey_b64 === m.pubkey);
  const id = local ? profileLabel(local.name) : (m.pubkey || "").slice(0, 8);
  const bio = m.bio || local?.bio || `${id} — no description.`;
  const isHub = hubPubkey ? m.pubkey === hubPubkey : local?.name === workgroup.hub_id;
  return (
    <DsMemberRow
      key={m.pubkey}
      member={{ id, color: local?.accent || "var(--ink-3)" }}
      isHub={isHub}
      note={bio}
      onRemove={() => onRemove?.(m)}
    />
  );
}

export default function WorkgroupDetail({ workgroup, profiles, connectionId = null, onSaved, onOpenChat }) {
  const [members, setMembers] = useState(null);
  const [busyAction, setBusyAction] = useState(null);
  const [briefing, setBriefing] = useState(workgroup.briefing ?? "");
  const [stages, setStages] = useState(workgroup.pipeline ?? []);
  const [newStage, setNewStage] = useState("");
  const [deleteOpen, setDeleteOpen] = useState(false);
  const briefingTimer = useRef(null);
  const notify = useNotify();

  useEffect(() => {
    setBriefing(workgroup.briefing ?? "");
    setStages(workgroup.pipeline ?? []);
  }, [workgroup.id, workgroup.briefing, workgroup.pipeline]);

  useEffect(() => {
    return () => {
      if (briefingTimer.current) clearTimeout(briefingTimer.current);
    };
  }, []);

  const reloadMembers = useCallback(async () => {
    try {
      const list = await invoke("workgroup_members", {
        profile: workgroup.profile,
        wgId: workgroup.id,
      });
      setMembers(list);
    } catch {
      setMembers([]);
    }
  }, [workgroup.profile, workgroup.id]);

  useEffect(() => {
    let cancelled = false;
    invoke("workgroup_members", {
      profile: workgroup.profile,
      wgId: workgroup.id,
    })
      .then((list) => { if (!cancelled) setMembers(list); })
      .catch(() => { if (!cancelled) setMembers([]); });
    return () => { cancelled = true; };
  }, [workgroup.profile, workgroup.id]);

  const hubName = workgroup.hub_id ?? workgroup.profile;
  const hubSummary = profiles.find((p) => p.name === hubName);
  // Lazy hub peer list, scoped per connection.
  const { detail: hubDetail } = useProfileDetail(connectionId, hubName || null);
  const hub = hubSummary
    ? { ...hubSummary, ...(hubDetail || {}) }
    : (hubDetail || null);
  const ownPubkey = profiles.find((p) => p.name === workgroup.profile)?.pubkey_b64;

  function updateBriefing(text) {
    setBriefing(text);
  }
  const briefingDirty = briefing !== (workgroup.briefing ?? "");
  function discardBriefing() {
    setBriefing(workgroup.briefing ?? "");
  }
  async function saveBriefing() {
    try {
      await invoke("workgroup_update", {
        profile: workgroup.profile,
        wgId: workgroup.id,
        briefing,
      });
      await onSaved?.();
    } catch (e) {
      notify({
        message: `briefing: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    }
  }

  // Local edits; reorder with ◀ ▶; persist on Save (comma-joined, host splits +
  // validates; empty clears). Same draft→Save pattern as the briefing above.
  function addStage() {
    const slug = newStage.trim().replace(/^#/, "").toLowerCase();
    if (!slug) return;
    if (!/^[a-z0-9][a-z0-9_-]*$/.test(slug)) {
      notify({ message: `invalid stage slug "${slug}"`, variant: "error" });
      return;
    }
    if (stages.includes(slug)) {
      notify({ message: `"${slug}" is already a stage`, variant: "error" });
      return;
    }
    setStages([...stages, slug]);
    setNewStage("");
  }
  function removeStage(i) {
    setStages(stages.filter((_, j) => j !== i));
  }
  function moveStage(i, dir) {
    const j = i + dir;
    if (j < 0 || j >= stages.length) return;
    const next = [...stages];
    [next[i], next[j]] = [next[j], next[i]];
    setStages(next);
  }
  const pipelineDirty = stages.join(",") !== (workgroup.pipeline ?? []).join(",");
  function discardPipeline() {
    setStages(workgroup.pipeline ?? []);
  }
  async function savePipeline() {
    try {
      await invoke("workgroup_update", {
        profile: workgroup.profile,
        wgId: workgroup.id,
        pipeline: stages.join(","),
      });
      await onSaved?.();
    } catch (e) {
      notify({ message: `pipeline: ${String(e)}`, variant: "error", duration: 4000 });
    }
  }

  async function addMember(memberArg, label) {
    setBusyAction("add-member");
    try {
      await invoke("workgroup_add_member", {
        profile: workgroup.profile,
        wgId: workgroup.id,
        member: memberArg,
      });
      notify({ message: `Added ${label} · group rekeyed`, variant: "success" });
      await reloadMembers();
      await onSaved?.();
    } catch (e) {
      notify({
        message: `add member failed: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    } finally {
      setBusyAction(null);
    }
  }

  async function act(action, memberPubkey = null) {
    setBusyAction(action);
    try {
      await invoke("workgroup_action", {
        profile: workgroup.profile,
        wgId: workgroup.id,
        action,
        memberPubkey,
      });
      notify({
        message:
          {
            pause: "Workgroup paused",
            resume: "Workgroup resumed",
            leave: "Left workgroup",
            kick: "Member kicked",
            remove: "Workgroup removed",
          }[action] ?? `${action} done`,
        variant: "success",
      });
      if (action === "kick") await reloadMembers();
      await onSaved?.();
    } catch (e) {
      notify({
        message: `${action} failed: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    } finally {
      setBusyAction(null);
    }
  }
  const busy = !!busyAction;

  const statusKind = workgroup.paused ? "paused" : "active";
  const statusDotColor = workgroup.paused ? "var(--c-warning)" : "var(--c-success)";
  const heroMeta = (
    <>
      <span className={styles.heroMetaGroup}>
        <span className={styles.heroMetaLabel}>hub</span>
        <span
          className={`diamond ${styles.heroMetaDiamond}`}
          style={{ "--c": hub?.accent || "var(--accent)" }}
        />
        <Mono className={styles.heroMetaValue}>@{profileLabel(hubName)}</Mono>
      </span>
      <span aria-hidden className={styles.heroMetaSep} />
      <span>
        <span className={styles.heroMetaLabel}>members </span>
        <Mono className={`tnum ${styles.heroMetaValue}`}>
          {members?.length ?? workgroup.members?.length ?? 0}
        </Mono>
      </span>
      <span aria-hidden className={styles.heroMetaSep} />
      <span className={styles.heroMetaGroup}>
        <Dot color={statusDotColor} pulse />
        <span className={styles.heroMetaValue}>{statusKind}</span>
      </span>
      <span aria-hidden className={styles.heroMetaSep} />
      <Mono className={styles.heroMetaMuted}>{workgroup.id}</Mono>
    </>
  );

  return (
    <main className={styles.detail}>
      <SettingsHero
        kind="workgroup"
        id={workgroup.name || workgroup.id}
        accent={hub?.accent || "var(--accent)"}
        meta={heroMeta}
        paused={!!workgroup.paused}
        onTogglePause={async () => {
          try {
            await invoke("workgroup_action", {
              profile: workgroup.profile,
              wgId: workgroup.id,
              action: workgroup.paused ? "resume" : "pause",
              memberPubkey: null,
            });
            await onSaved?.();
          } catch (e) {
            notify({ message: String(e), variant: "error", duration: 4000 });
          }
        }}
        onOpenChat={onOpenChat ? () => onOpenChat(workgroup) : undefined}
      />
      <div className={styles.body}>
        {/* Overview — Hub / Status / ID (3 rows, per v2 §8 canonical) */}
        <Section title="Overview">
          <Row label="hub">
            <span className={styles.inlineRow}>
              <Diamond color={hub?.accent} />
              <span className={styles.mono}>@{profileLabel(hubName)}</span>
            </span>
          </Row>
          <Row label="status">
            <span className={styles.inlineRow}>
              {workgroup.paused ? (
                <Chip state="off" activity={busyAction === "resume"}>paused</Chip>
              ) : (
                <Chip state="on" activity={busyAction === "pause"}>active</Chip>
              )}
              {workgroup.is_hub ? (
                workgroup.paused ? (
                  <Button size="sm" onClick={() => act("resume")} disabled={busy}>
                    Resume
                  </Button>
                ) : (
                  <Button size="sm" onClick={() => act("pause")} disabled={busy}>
                    Pause
                  </Button>
                )
              ) : (
                <ConfirmDeleteAction
                  label="Leave"
                  title={`Leave workgroup #${workgroup.name || workgroup.id}?`}
                  consequence="Your subscription is removed and you stop receiving messages. The hub can re-invite you later."
                  confirmLabel="Leave"
                  disabled={busy}
                  loading={busyAction === "leave"}
                  onConfirm={() => act("leave")}
                />
              )}
            </span>
          </Row>
          <Row label="id">
            <span className={styles.inlineRow}>
              <span className={styles.mono}>{workgroup.id}</span>
              <CopyButton value={workgroup.id} message="Workgroup id copied" />
            </span>
          </Row>
        </Section>

        {/* Budget — hero metric ($X.XX display 28 + sublabel + Edit cap) + bar.
            1:1 with v2 §8 Budget section in WorkgroupDetail. */}
        <Section title="Budget" tooltip="workgroup spend cap">
          <Row label="used" alignTop>
            <div className={styles.budgetHero}>
              <div className={styles.budgetHeroLine}>
                <span className={`${styles.budgetUsed} tnum`}>
                  ${(workgroup.spent_usd ?? 0).toFixed(2)}
                </span>
                {workgroup.budget_usd != null ? (
                  <Mono className={styles.budgetCap}>
                    of{" "}
                    <span className={`tnum ${styles.budgetCapValue}`}>
                      ${workgroup.budget_usd.toFixed(2)}
                    </span>{" "}
                    ·{" "}
                    {Math.round(
                      (workgroup.spent_usd ?? 0) / workgroup.budget_usd * 100,
                    )}
                    %
                  </Mono>
                ) : (
                  <Mono className={styles.budgetCap}>no cap</Mono>
                )}
                <span className={styles.budgetSpacer} />
                {workgroup.is_hub && (
                  <BudgetEditor
                    current={workgroup.budget_usd}
                    onSave={async (next) => {
                      try {
                        await invoke("workgroup_update", {
                          profile: workgroup.profile,
                          wgId: workgroup.id,
                          budgetUsd: next,
                          clearBudget: next === null,
                        });
                        await onSaved?.();
                      } catch (e) {
                        notify({
                          message: `budget: ${String(e)}`,
                          variant: "error",
                          duration: 4000,
                        });
                        throw e;
                      }
                    }}
                  />
                )}
              </div>
              {workgroup.budget_usd != null && (
                <div className={styles.budgetBar}>
                  <div
                    className={styles.budgetBarFill}
                    style={{
                      width: `${Math.min(
                        100,
                        ((workgroup.spent_usd ?? 0) / workgroup.budget_usd) * 100,
                      )}%`,
                      background: hub?.accent || "var(--accent)",
                    }}
                  />
                </div>
              )}
            </div>
          </Row>
        </Section>

        {/* Briefing — textarea with draft tag pattern (v2 §12.5). */}
        <Section title="Briefing" tooltip="what this workgroup decides">
          <Row label="brief" alignTop>
            {workgroup.is_hub ? (
              <div className={styles.briefingWrap}>
                <Textarea
                  className={styles.textarea}
                  rows={4}
                  value={briefing}
                  onChange={(e) => updateBriefing(e.target.value)}
                  placeholder="what is this workgroup about? who does what?"
                />
                {briefingDirty && (
                  <div className={styles.draftRow}>
                    <span className={styles.draftTag}>draft</span>
                    <button
                      type="button"
                      className="alink"
                      onClick={discardBriefing}
                    >
                      Discard
                    </button>
                    <button
                      type="button"
                      className="alink"
                      onClick={saveBriefing}
                    >
                      Save
                    </button>
                  </div>
                )}
              </div>
            ) : workgroup.briefing ? (
              <pre className={styles.briefing}>{workgroup.briefing}</pre>
            ) : (
              <span className={styles.muted}>no briefing yet</span>
            )}
          </Row>
        </Section>

        {/* Pipeline — ordered stage chips the hub advances in order. */}
        <Section title="Pipeline" tooltip="task order the hub runs">
          <Row label="stages" alignTop>
            {workgroup.is_hub ? (
              <div className={styles.stagesWrap}>
                {stages.length > 0 && (
                  <div className={styles.stagesRow}>
                    {stages.map((s, i) => (
                      <span key={s} className={styles.stageChip}>
                        <span className={styles.stageNum}>{i + 1}</span>
                        <code className={styles.stageSlug}>#{s}</code>
                        <button
                          type="button"
                          className={styles.stageMove}
                          disabled={i === 0}
                          onClick={() => moveStage(i, -1)}
                          aria-label={`move ${s} left`}
                        >
                          ‹
                        </button>
                        <button
                          type="button"
                          className={styles.stageMove}
                          disabled={i === stages.length - 1}
                          onClick={() => moveStage(i, 1)}
                          aria-label={`move ${s} right`}
                        >
                          ›
                        </button>
                        <button
                          type="button"
                          className={styles.stageRemove}
                          onClick={() => removeStage(i)}
                          aria-label={`remove ${s}`}
                        >
                          ×
                        </button>
                      </span>
                    ))}
                  </div>
                )}
                <div className={styles.stageAdd}>
                  <input
                    className="ds-field"
                    value={newStage}
                    onChange={(e) => setNewStage(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addStage(); } }}
                    placeholder="add a stage slug — e.g. research"
                    autoCapitalize="none"
                    autoCorrect="off"
                  />
                  <Button size="sm" onClick={addStage}>Add</Button>
                </div>
                {pipelineDirty && (
                  <div className={styles.draftRow}>
                    <span className={styles.draftTag}>draft</span>
                    <button type="button" className="alink" onClick={discardPipeline}>
                      Discard
                    </button>
                    <button type="button" className="alink" onClick={savePipeline}>
                      Save
                    </button>
                  </div>
                )}
                <p className={styles.stageHint}>
                  Stages run in order. When <code>#{stages[0] ?? "research"} #done</code> fires,
                  the hub opens the next stage automatically.
                </p>
              </div>
            ) : stages.length ? (
              <div className={styles.stagesRow}>
                {stages.map((s, i) => (
                  <Fragment key={s}>
                    <span className={styles.stageChip}>
                      <span className={styles.stageNum}>{i + 1}</span>
                      <code className={styles.stageSlug}>#{s}</code>
                    </span>
                    {i < stages.length - 1 && <span className={styles.stageArrow}>→</span>}
                  </Fragment>
                ))}
              </div>
            ) : (
              <span className={styles.muted}>no pipeline (deliberation workgroup)</span>
            )}
          </Row>
        </Section>

        <Section title="Members" kicker={members ? `${members.filter((m) => m.joined).length} alpis` : null} alignTop>
          {members === null ? (
            <>
              <Skeleton width="220px" />
              <Skeleton width="180px" />
            </>
          ) : members.filter((m) => m.joined).length === 0 ? (
            <span className={styles.muted}>none</span>
          ) : (
            members
              .filter((m) => m.joined)
              .map((m) =>
                renderMemberRow(m, profiles, workgroup, hub?.pubkey_b64, (target) =>
                  act("kick", target.pubkey),
                ),
              )
          )}
          {workgroup.is_hub && members && (() => {
            const memberPubkeys = new Set(members.map((m) => m.pubkey));
            const candidates = (hub?.peers ?? []).filter(
              (p) => !memberPubkeys.has(p.pubkey),
            );
            if (candidates.length === 0) return null;
            return (
              <Row label="add">
                <Dropdown
                  trigger={{ label: "Add member…" }}
                  direction="down"
                  align="left"
                  width={300}
                  variant="field"
                >
                  {({ close }) => (
                    <>
                      {candidates.map((p) => {
                        const local = profiles.find(
                          (x) => x.pubkey_b64 === p.pubkey,
                        );
                        const label = `@${p.alias || p.id}`;
                        return (
                          <Dropdown.Row
                            key={p.id}
                            caption={(p.pubkey || "").slice(0, 16) + "…"}
                            leading={<Diamond color={local?.accent} />}
                            onClick={() => {
                              close();
                              addMember(p.id, label);
                            }}
                          >
                            {label}
                          </Dropdown.Row>
                        );
                      })}
                    </>
                  )}
                </Dropdown>
              </Row>
            );
          })()}
        </Section>

        {members && members.some((m) => !m.joined) && (
          <Section title="Invitations" tooltip="pending member invites" alignTop>
            {workgroup.is_hub && (
              <Row label="join command" alignTop>
                <span className={styles.inlineRow}>
                  <code className={styles.mono}>
                    alpi workgroup join {hubName} {workgroup.id}
                  </code>
                  <CopyButton
                    value={`alpi workgroup join ${hubName} ${workgroup.id}`}
                    message="Join command copied"
                  />
                </span>
              </Row>
            )}
            {members
              .filter((m) => !m.joined)
              .map((m) => renderMemberRow(m, profiles, workgroup, hub?.pubkey_b64))}
          </Section>
        )}

        {workgroup.is_hub && (
          <Section title="Danger zone">
            <Row label="delete">
              <button
                type="button"
                className="alink danger"
                onClick={() => setDeleteOpen(true)}
                disabled={busy}
              >
                Delete workgroup…
              </button>
              <ConfirmDelete
                mode="typed"
                open={deleteOpen}
                onClose={() => setDeleteOpen(false)}
                onConfirm={() => act("remove")}
                title={`Delete workgroup #${workgroup.name || workgroup.id}`}
                consequence={
                  <>
                    This removes the channel and all thread history, tasks, and
                    decisions. Members keep their own copies of past messages.
                    This action <strong>cannot be undone</strong>.
                  </>
                }
                typeToConfirm={workgroup.name || workgroup.id}
                confirmLabel="Delete workgroup"
              />
            </Row>
          </Section>
        )}
      </div>
    </main>
  );
}
