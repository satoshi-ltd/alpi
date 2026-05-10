import { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import Button from "../../primitives/Button.jsx";
import Chip from "../../primitives/Chip.jsx";
import Dropdown from "../../primitives/Dropdown.jsx";
import Textarea from "../../primitives/Textarea.jsx";
import { AccentDot } from "../../primitives/NavRow.jsx";
import Skeleton from "../../primitives/Skeleton.jsx";
import { useNotify } from "../../primitives/Notification.jsx";
import { profileLabel } from "../../lib/profile-display.js";
import { Section, Row, ConfirmButton, CopyButton } from "./primitives.jsx";
import { BudgetEditor } from "./fields/alp.jsx";
import styles from "../Settings.module.css";

function renderMemberRow(m, profiles) {
  const local = profiles.find((p) => p.pubkey_b64 === m.pubkey);
  const label = local
    ? `@${profileLabel(local.name)}`
    : `${(m.pubkey || "").slice(0, 8)}…`;
  const memberLabel = (
    <span className={styles.memberLabel}>
      <AccentDot color={local?.accent} />
      <span className={styles.mono}>{label}</span>
    </span>
  );
  const bio = m.bio || local?.bio || "";
  return (
    <Row key={m.pubkey} label={memberLabel} alignTop>
      <span className={styles.memberBio}>
        {bio || <span className={styles.muted}>—</span>}
      </span>
    </Row>
  );
}

export default function WorkgroupDetail({ workgroup, profiles, onSaved }) {
  const [members, setMembers] = useState(null);
  const [busyAction, setBusyAction] = useState(null);
  const [briefing, setBriefing] = useState(workgroup.briefing ?? "");
  const briefingTimer = useRef(null);
  const notify = useNotify();

  useEffect(() => {
    setBriefing(workgroup.briefing ?? "");
  }, [workgroup.id]);

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
  const hub = profiles.find((p) => p.name === hubName);
  const ownPubkey = profiles.find((p) => p.name === workgroup.profile)?.pubkey_b64;

  function updateBriefing(text) {
    setBriefing(text);
    if (briefingTimer.current) clearTimeout(briefingTimer.current);
    briefingTimer.current = setTimeout(() => {
      invoke("workgroup_update", {
        profile: workgroup.profile,
        wgId: workgroup.id,
        briefing: text,
      })
        .then(() => onSaved?.())
        .catch((e) =>
          notify({
            message: `briefing: ${String(e)}`,
            variant: "error",
            duration: 4000,
          }),
        );
    }, 600);
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

  return (
    <main className={styles.detail}>
      <div className={styles.body}>
        <Section title="Overview">
          <Row label="name">
            <span className={styles.mono}>#{workgroup.name || workgroup.id}</span>
          </Row>
          <Row label="id">
            <span className={styles.inlineRow}>
              <span className={styles.mono}>{workgroup.id}</span>
              <CopyButton value={workgroup.id} message="Workgroup id copied" />
            </span>
          </Row>
          <Row label="hub">
            <span className={styles.inlineRow}>
              <AccentDot color={hub?.accent} />
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
              <span className={styles.btnGroup}>
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
                  <ConfirmButton
                    size="sm"
                    label="Leave"
                    confirmLabel="Confirm leave"
                    disabled={busy}
                    loading={busyAction === "leave"}
                    onConfirm={() => act("leave")}
                  />
                )}
              </span>
            </span>
          </Row>
          <Row label="budget">
            <span className={styles.inlineRow}>
              {workgroup.budget_usd != null ? (
                <Chip>
                  {workgroup.spent_usd > 0 && workgroup.spent_usd < 0.01
                    ? `$${workgroup.spent_usd.toFixed(4)}`
                    : `$${workgroup.spent_usd.toFixed(2)}`}{" / "}
                  ${workgroup.budget_usd.toFixed(2)}
                </Chip>
              ) : (
                <span className={styles.muted}>unlimited</span>
              )}
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
            </span>
          </Row>
          <Row label="briefing" alignTop>
            {workgroup.is_hub ? (
              <Textarea
                className={styles.textarea}
                rows={3}
                value={briefing}
                onChange={(e) => updateBriefing(e.target.value)}
                placeholder="what is this workgroup about? who does what?"
              />
            ) : workgroup.briefing ? (
              <pre className={styles.briefing}>{workgroup.briefing}</pre>
            ) : (
              <span className={styles.muted}>no briefing yet</span>
            )}
          </Row>
        </Section>

        <Section title="Members" alignTop>
          {members === null ? (
            <>
              <Row label={<Skeleton width="60px" height="0.7em" />}>
                <Skeleton width="220px" />
              </Row>
              <Row label={<Skeleton width="60px" height="0.7em" />}>
                <Skeleton width="180px" />
              </Row>
            </>
          ) : members.filter((m) => m.joined).length === 0 ? (
            <Row label="list">
              <span className={styles.muted}>none</span>
            </Row>
          ) : (
            members
              .filter((m) => m.joined)
              .map((m) => renderMemberRow(m, profiles))
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
                  variant="outlined"
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
                            leading={<AccentDot color={local?.accent} />}
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
          {workgroup.is_hub &&
            members &&
            members.filter((m) => m.joined && m.pubkey !== ownPubkey).length > 0 && (
              <Row label="kick">
                <Dropdown
                  trigger={{ label: "Kick member…" }}
                  direction="down"
                  align="left"
                  width={300}
                  variant="outlined"
                >
                  {({ close }) => (
                    <>
                      {members
                        .filter((m) => m.joined && m.pubkey !== ownPubkey)
                        .map((m) => {
                          const local = profiles.find(
                            (p) => p.pubkey_b64 === m.pubkey,
                          );
                          const label = local
                            ? `@${profileLabel(local.name)}`
                            : `${(m.pubkey || "").slice(0, 8)}…`;
                          return (
                            <Dropdown.Row
                              key={m.pubkey}
                              caption={(m.pubkey || "").slice(0, 16) + "…"}
                              leading={<AccentDot color={local?.accent} />}
                              onClick={() => {
                                close();
                                act("kick", m.pubkey);
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
            )}
        </Section>

        {members && members.some((m) => !m.joined) && (
          <Section title="Invitations" alignTop>
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
              .map((m) => renderMemberRow(m, profiles))}
          </Section>
        )}

        {workgroup.is_hub && (
          <Section title="Danger zone">
            <Row label="remove">
              <ConfirmButton
                label="Remove workgroup"
                confirmLabel={`Confirm · wipe #${workgroup.name || workgroup.id}`}
                disabled={busy}
                loading={busyAction === "remove"}
                onConfirm={() => act("remove")}
              />
            </Row>
          </Section>
        )}
      </div>
    </main>
  );
}
