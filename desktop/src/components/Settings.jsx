import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { getVersion } from "@tauri-apps/api/app";
import ConnectionSwitcher from "./ConnectionSwitcher.jsx";
import Button from "../primitives/Button.jsx";
import Chip from "../primitives/Chip.jsx";
import Dropdown from "../primitives/Dropdown.jsx";
import NavRow, { Dot, Hash } from "../primitives/NavRow.jsx";
import Textarea from "../primitives/Textarea.jsx";
import Tooltip from "../primitives/Tooltip.jsx";
import useAutoPosition from "../primitives/useAutoPosition.js";
import { useNotify } from "../primitives/Notification.jsx";
import {
  applyPendingUpdate,
  checkForUpdates,
  subscribeUpdater,
} from "../lib/updater.js";
import styles from "./Settings.module.css";

const ACCENT_PALETTE = [
  "#c8a24e",
  "#cf6b3d",
  "#c14545",
  "#b04067",
  "#9a4593",
  "#7257a8",
  "#4d6db5",
  "#3d8aa3",
  "#4d8f7d",
  "#5f9750",
  "#6e5e54",
  "#888893",
];

const HEX_RE = /^#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})$/;

function VersionFooter() {
  const [version, setVersion] = useState("");
  const [updater, setUpdater] = useState({
    checking: false,
    available: false,
    version: null,
    error: null,
    installing: false,
  });
  const notify = useNotify();

  useEffect(() => {
    getVersion().then(setVersion).catch(() => setVersion("?"));
  }, []);

  useEffect(() => subscribeUpdater(setUpdater), []);

  async function checkNow() {
    if (updater.checking || updater.installing) return;
    try {
      const next = await checkForUpdates();
      if (next.available && next.version) {
        notify({
          message: `Update available: ${next.version}`,
          variant: "success",
          duration: 3500,
        });
      } else if (!next.error) {
        notify({ message: "You're on the latest version.", variant: "success" });
      }
    } catch (e) {
      notify({
        message: `Update check failed: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    }
  }

  async function installNow() {
    if (!updater.available || updater.installing) return;
    try {
      notify({
        message: `Installing ${updater.version}… app will restart when ready.`,
        variant: "success",
        duration: 4000,
      });
      await applyPendingUpdate();
    } catch (e) {
      notify({
        message: `Update install failed: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    }
  }

  if (!version) return null;
  return (
    <div className={styles.asideFooter}>
      <span>Alpi {version}</span>
      <span>·</span>
      <button
        type="button"
        className={styles.asideFooterButton}
        onClick={checkNow}
        disabled={updater.checking || updater.installing}
      >
        {updater.checking ? "checking…" : "check for updates"}
      </button>
      {updater.available && updater.version && (
        <>
          <span>·</span>
          <button
            type="button"
            className={styles.asideFooterButton}
            onClick={installNow}
            disabled={updater.installing}
          >
            {updater.installing
              ? "installing…"
              : `install ${updater.version}`}
          </button>
        </>
      )}
    </div>
  );
}

const FIELD_KEYS = {
  bio: "public_bio",
  workspace: "workspace",
  model: "model",
  accent: "tui.accent",
};

export default function Settings({
  profiles,
  workgroups = [],
  target,
  hostConnections,
  onSelectTarget,
  onRefresh,
  onSetHostConnection,
  onAddHostConnection,
  onForgetHostConnection,
  onRefreshHostConnectionStatus,
}) {
  const setTarget = onSelectTarget ?? (() => {});

  const selectedProfile = useMemo(() => {
    if (target?.kind !== "profile") return null;
    return profiles.find((p) => p.name === target.id) ?? null;
  }, [profiles, target]);

  const selectedWorkgroup = useMemo(() => {
    if (target?.kind !== "workgroup") return null;
    return workgroups.find((w) => w.id === target.id) ?? null;
  }, [workgroups, target]);

  useEffect(() => {
    if (!target || (target.kind === "profile" && !target.id)) {
      const first = profiles[0]?.name ?? null;
      if (first) setTarget({ kind: "profile", id: first });
    }
  }, [profiles, target, setTarget]);

  return (
    <div className={styles.wrap}>
      <aside className={styles.aside}>
        <div className={styles.asideTitle}>Connection</div>
        <ConnectionSwitcher
          className={styles.connectionSwitcher}
          state={hostConnections}
          onSetActive={onSetHostConnection}
          onAddRemote={onAddHostConnection}
          onForget={onForgetHostConnection}
          onOpen={onRefreshHostConnectionStatus}
        />

        <div className={styles.asideTitle}>Profiles</div>
        {profiles.map((p) => {
          const active =
            target?.kind === "profile" && target.id === p.name;
          return (
            <NavRow
              key={p.name}
              active={active}
              accent={p.accent || "var(--color-accent)"}
              muted={!p.model}
              leading={<Dot color={p.accent} />}
              trailing={
                !p.model && (
                  <span
                    className={styles.asideTag}
                    title="No model configured"
                  >
                    !
                  </span>
                )
              }
              onClick={() => setTarget({ kind: "profile", id: p.name })}
            >
              {p.name}
            </NavRow>
          );
        })}
        <NavRow
          active={target?.kind === "create-profile"}
          leading={<Hash>+</Hash>}
          onClick={() => setTarget({ kind: "create-profile" })}
        >
          New profile
        </NavRow>

        <div className={styles.asideTitle} style={{ marginTop: "var(--space-3)" }}>
          Workgroups
        </div>
        {workgroups.map((w) => {
          const active =
            target?.kind === "workgroup" && target.id === w.id;
          const hub = profiles.find(
            (p) => p.name === (w.hub_id ?? w.profile),
          );
          const accent = hub?.accent || "var(--color-accent)";
          return (
            <NavRow
              key={w.id}
              active={active}
              accent={accent}
              leading={<Hash />}
              onClick={() => setTarget({ kind: "workgroup", id: w.id })}
            >
              {w.name || w.id}
            </NavRow>
          );
        })}
        <NavRow
          active={target?.kind === "create-workgroup"}
          leading={<Hash>+</Hash>}
          onClick={() => setTarget({ kind: "create-workgroup" })}
        >
          New workgroup
        </NavRow>
        <VersionFooter />
      </aside>

      {selectedProfile && (
        <ProfileDetail
          key={selectedProfile.name}
          profile={selectedProfile}
          profiles={profiles}
          onSaved={onRefresh}
          onNavigate={setTarget}
        />
      )}
      {selectedWorkgroup && (
        <WorkgroupDetail
          key={selectedWorkgroup.id}
          workgroup={selectedWorkgroup}
          profiles={profiles}
          onSaved={onRefresh}
        />
      )}
      {target?.kind === "create-profile" && (
        <CreateProfileForm
          existingNames={profiles.map((p) => p.name)}
          onCreated={async (name) => {
            await onRefresh?.();
            setTarget({ kind: "profile", id: name });
          }}
          onCancel={() => {
            const first = profiles[0]?.name ?? null;
            if (first) setTarget({ kind: "profile", id: first });
          }}
        />
      )}
      {target?.kind === "create-workgroup" && (
        <CreateWorkgroupForm
          profiles={profiles}
          onCreated={async (wgId) => {
            await onRefresh?.();
            if (wgId) setTarget({ kind: "workgroup", id: wgId });
          }}
          onCancel={() => {
            const first = profiles[0]?.name ?? null;
            if (first) setTarget({ kind: "profile", id: first });
          }}
        />
      )}
      {!selectedProfile &&
        !selectedWorkgroup &&
        target?.kind !== "create-workgroup" &&
        target?.kind !== "create-profile" && (
          <div className={styles.empty}>No selection</div>
        )}
    </div>
  );
}

function initialDraft(profile) {
  return {
    bio: profile.bio ?? "",
    workspace: profile.workspace ?? "",
    model: profile.model ?? "",
    accent: (profile.accent ?? "").toLowerCase(),
  };
}

function ProfileDetail({ profile, profiles, onSaved, onNavigate }) {
  const baseline = useMemo(() => initialDraft(profile), [profile]);
  const [draft, setDraft] = useState(baseline);
  const notify = useNotify();
  const timersRef = useRef({});

  useEffect(() => {
    setDraft(baseline);
  }, [baseline]);

  useEffect(() => {
    const timers = timersRef.current;
    return () => {
      for (const t of Object.values(timers)) clearTimeout(t);
    };
  }, []);

  function persist(field, value) {
    invoke("set_config_field", {
      profile: profile.name,
      key: FIELD_KEYS[field],
      value,
    })
      .then(() => {
        onSaved?.();
      })
      .catch((e) => {
        notify({
          message: `${field}: ${String(e)}`,
          variant: "error",
          duration: 4000,
        });
      });
  }

  function update(field, value) {
    setDraft((d) => ({ ...d, [field]: value }));
    const timers = timersRef.current;
    if (timers[field]) clearTimeout(timers[field]);
    timers[field] = setTimeout(() => persist(field, value), 600);
  }

  return (
    <main className={styles.detail}>
      <div className={styles.body}>
        <Section title="Overview">
          <Row label="home">
            <span className={styles.inlineRow}>
              <span className={styles.mono}>{profile.home}</span>
              <Button
                size="sm"
                onClick={() =>
                  invoke("reveal_in_finder", { path: profile.home })
                }
              >
                Reveal
              </Button>
            </span>
          </Row>
          <Row label="model">
            <span className={styles.inlineRow}>
              {((profile.models?.length ?? 0) > 0 ||
                (profile.provider_ollama?.length ?? 0) > 0) ? (
                <ModelField
                  profile={profile}
                  value={draft.model}
                  onChange={(v) => update("model", v)}
                />
              ) : (
                <span className={styles.muted}>
                  no models — add a provider first
                </span>
              )}
              <AddProviderField profile={profile} onSaved={onSaved} />
            </span>
          </Row>
          <BudgetField profile={profile} onSaved={onSaved} />
          <Row label="workspace">
            <WorkspaceField
              value={draft.workspace}
              onChange={(v) => update("workspace", v)}
            />
          </Row>
          <Row label="accent">
            <AccentField
              value={draft.accent}
              onChange={(v) => update("accent", v)}
            />
          </Row>
        </Section>

        <Section title="Services">
          <Row label="subsystems">
            <SubsystemsCell profile={profile} onSaved={onSaved} />
          </Row>
          <Row label="gateways">
            <GatewaysCell profile={profile} />
          </Row>
        </Section>

        <Section title="ALP (Alpi Link Protocol)">
          {profile.pubkey_b64 && (
            <Row label="pubkey">
              <span className={styles.inlineRow}>
                <span className={`${styles.mono} ${styles.truncate}`}>
                  {profile.pubkey_b64}
                </span>
                <CopyButton
                  value={profile.pubkey_b64}
                  message="Pubkey copied"
                />
              </span>
            </Row>
          )}
          <Row label="identity">
            <Textarea
              className={styles.textarea}
              rows={3}
              value={draft.bio}
              onChange={(e) => update("bio", e.target.value)}
              placeholder="public identity — visible to peers"
            />
          </Row>
          <Row label="port">
            <span className={styles.inlineRow}>
              <Chip
                state="on"
                tooltip={
                  <>
                    <div>ALP unix socket</div>
                    <div className={styles.tooltipStatus}>
                      always on · for local peers
                    </div>
                  </>
                }
              >
                unix
              </Chip>
              <TcpPortField profile={profile} onSaved={onSaved} />
            </span>
          </Row>
          <Row label="peers">
            <PeersField
              profile={profile}
              profiles={profiles}
              onSaved={onSaved}
            />
          </Row>
          <Row label="workgroups">
            <WorkgroupsField
              profile={profile}
              profiles={profiles}
              onSelectWorkgroup={(id) =>
                onNavigate?.({ kind: "workgroup", id })
              }
            />
          </Row>
        </Section>

        <SchedulesSection profile={profile} />

        <Section
          title="Sandbox"
          tooltip="Wraps shell commands in sandbox-exec (macOS) or bubblewrap (Linux). Recommended for unattended profiles (gateway, scheduler, sub-agents). Trade-offs: SSH push, Homebrew on Apple Silicon, and docker may break — keep off in your main dev profile."
        >
          <SandboxField profile={profile} onSaved={onSaved} />
        </Section>

        <Section title="Voice">
          <VoiceField profile={profile} onSaved={onSaved} />
        </Section>

        <Section title="MCP servers">
          <McpField profile={profile} onSaved={onSaved} />
        </Section>

        <Section title="Skills">
          <SkillsField profile={profile} />
        </Section>

        <Section title="Storage">
          <StorageField profile={profile} />
        </Section>

        {profile.name !== "default" && (
          <Section title="Danger zone">
            <Row label="delete">
              <DeleteProfileAction
                profile={profile}
                onDeleted={onSaved}
              />
            </Row>
          </Section>
        )}

      </div>

    </main>
  );
}

function DeleteProfileAction({ profile, onDeleted }) {
  const notify = useNotify();
  const [busy, setBusy] = useState(false);
  return (
    <span className={styles.inlineRow}>
      <ConfirmButton
        label="Delete profile"
        confirmLabel={`Confirm · wipe @${profile.name}`}
        loading={busy}
        onConfirm={async () => {
          setBusy(true);
          try {
            await invoke("profile_delete", { name: profile.name });
            notify({
              message: `Profile @${profile.name} deleted`,
              variant: "success",
            });
            await onDeleted?.();
          } catch (e) {
            notify({
              message: `delete failed: ${String(e)}`,
              variant: "error",
              duration: 4000,
            });
          } finally {
            setBusy(false);
          }
        }}
      />
      <span className={styles.muted}>
        removes ~/.alpi/profiles/{profile.name}/ — daemon picks up the
        change on its next restart
      </span>
    </span>
  );
}

function CreateProfileForm({ existingNames, onCreated, onCancel }) {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const notify = useNotify();

  const trimmed = name.trim();
  const reserved = trimmed === "default";
  const formatValid = trimmed !== "" && /^[a-z0-9_-]+$/.test(trimmed);
  const duplicate = existingNames.includes(trimmed);
  const canSubmit =
    !busy && formatValid && !duplicate && !reserved;

  async function submit() {
    if (!canSubmit) return;
    setBusy(true);
    try {
      await invoke("profile_create", { name: trimmed });
      notify({
        message: `Profile @${trimmed} created`,
        variant: "success",
      });
      onCreated?.(trimmed);
    } catch (e) {
      notify({
        message: `create failed: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className={styles.detail}>
      <div className={styles.body}>
        <Section title="New profile">
          <Row label="name">
            <span className={styles.inlineRow}>
              <input
                className={styles.input}
                value={name}
                onChange={(e) => setName(e.target.value.toLowerCase())}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && canSubmit) submit();
                }}
                placeholder="work · personal · home-server"
                spellCheck={false}
                autoFocus
              />
            </span>
          </Row>
          {trimmed !== "" && !formatValid && (
            <Row label=" ">
              <span className={styles.error}>
                use a-z, 0-9, '-' and '_' only
              </span>
            </Row>
          )}
          {reserved && (
            <Row label=" ">
              <span className={styles.error}>
                'default' is reserved
              </span>
            </Row>
          )}
          {duplicate && (
            <Row label=" ">
              <span className={styles.error}>
                @{trimmed} already exists
              </span>
            </Row>
          )}
          <Row label=" ">
            <span className={styles.muted}>
              configure model, workspace, peers, etc. after.
            </span>
          </Row>
          <Row label=" ">
            <span className={styles.inlineRow}>
              <Button onClick={onCancel} disabled={busy}>
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={submit}
                disabled={!canSubmit}
                loading={busy}
              >
                Create
              </Button>
            </span>
          </Row>
        </Section>
      </div>
    </main>
  );
}

function CreateWorkgroupForm({ profiles, onCreated, onCancel }) {
  const [hubProfile, setHubProfile] = useState(profiles[0]?.name ?? "");
  const [name, setName] = useState("");
  const [memberIds, setMemberIds] = useState([]);
  const [budget, setBudget] = useState("");
  const [briefing, setBriefing] = useState("");
  const [busy, setBusy] = useState(false);
  const notify = useNotify();

  const peers = useMemo(
    () => profiles.find((x) => x.name === hubProfile)?.peers ?? [],
    [profiles, hubProfile],
  );

  useEffect(() => {
    setMemberIds([]);
  }, [hubProfile]);

  const budgetNum = budget.trim() === "" ? null : Number(budget);
  const budgetValid =
    budget.trim() === "" ||
    (Number.isFinite(budgetNum) && budgetNum > 0);
  const canSubmit =
    !busy && hubProfile && name.trim().length > 0 && budgetValid;

  function toggleMember(peerId) {
    setMemberIds((prev) =>
      prev.includes(peerId)
        ? prev.filter((id) => id !== peerId)
        : [...prev, peerId],
    );
  }

  async function submit() {
    if (!canSubmit) return;
    setBusy(true);
    try {
      const wgId = await invoke("workgroup_create", {
        profile: hubProfile,
        name: name.trim(),
        memberPeerIds: memberIds,
        budgetUsd: budgetNum,
        briefing: briefing.trim() || null,
      });
      notify({
        message: `Workgroup #${name.trim()} created`,
        variant: "success",
      });
      onCreated?.(wgId);
    } catch (e) {
      notify({
        message: `create failed: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className={styles.detail}>
      <div className={styles.body}>
        <Section title="New workgroup">
          <Row label="hub">
            <Dropdown
              trigger={{
                leading: hubProfile && (
                  <span
                    className={styles.peerAccentDot}
                    style={{
                      backgroundColor:
                        profiles.find((p) => p.name === hubProfile)?.accent ||
                        "var(--color-accent)",
                    }}
                  />
                ),
                label: hubProfile || "Pick profile…",
              }}
              direction="down"
              align="left"
              width={260}
              variant="outlined"
            >
              {({ close }) =>
                profiles.map((p) => (
                  <Dropdown.Row
                    key={p.name}
                    active={p.name === hubProfile}
                    leading={
                      <span
                        className={styles.peerAccentDot}
                        style={{
                          backgroundColor: p.accent || "var(--color-accent)",
                        }}
                      />
                    }
                    onClick={() => {
                      setHubProfile(p.name);
                      close();
                    }}
                  >
                    @{p.name}
                  </Dropdown.Row>
                ))
              }
            </Dropdown>
          </Row>
          <Row label="name">
            <input
              className={styles.input}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="team-alpha"
              spellCheck={false}
            />
          </Row>
          <Row label="members" alignTop>
            {peers.length === 0 ? (
              <span className={styles.muted}>
                @{hubProfile} has no pinned peers
              </span>
            ) : (
              <span className={styles.gatewayChips}>
                {peers.map((p) => {
                  const local = profiles.find((x) => x.name === p.id);
                  const accent =
                    local?.accent || "var(--color-accent)";
                  const selected = memberIds.includes(p.id);
                  return (
                    <Chip
                      key={p.id}
                      onClick={() => toggleMember(p.id)}
                      accent={selected ? accent : undefined}
                      tooltip={
                        <>
                          <div>@{p.id}</div>
                          <div className={styles.tooltipStatus}>
                            {(p.pubkey || "").slice(0, 16)}…
                          </div>
                        </>
                      }
                    >
                      @{p.id}
                    </Chip>
                  );
                })}
              </span>
            )}
          </Row>
          <Row label="budget">
            <span className={styles.inlineRow}>
              <input
                className={styles.input}
                value={budget}
                onChange={(e) => setBudget(e.target.value)}
                placeholder="USD lifetime cap (optional)"
                spellCheck={false}
                style={{ maxWidth: 220 }}
              />
              {!budgetValid && (
                <span className={styles.error}>must be a positive number</span>
              )}
            </span>
          </Row>
          <Row label="briefing" alignTop>
            <Textarea
              className={styles.textarea}
              rows={3}
              value={briefing}
              onChange={(e) => setBriefing(e.target.value)}
              placeholder="what is this workgroup about? who does what?"
            />
          </Row>
          <Row label=" ">
            <span className={styles.inlineRow}>
              <Button onClick={onCancel} disabled={busy}>
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={submit}
                disabled={!canSubmit}
                loading={busy}
              >
                Create
              </Button>
            </span>
          </Row>
        </Section>
      </div>
    </main>
  );
}

function renderMemberRow(m, profiles, styles) {
  const local = profiles.find((p) => p.pubkey_b64 === m.pubkey);
  const label = local
    ? `@${local.name}`
    : `${(m.pubkey || "").slice(0, 8)}…`;
  const accent = local?.accent || "var(--color-accent)";
  const memberLabel = (
    <span className={styles.memberLabel}>
      <span
        className={styles.peerAccentDot}
        style={{ backgroundColor: accent }}
      />
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

function WorkgroupDetail({ workgroup, profiles, onSaved }) {
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
      .then((list) => {
        if (!cancelled) setMembers(list);
      })
      .catch(() => {
        if (!cancelled) setMembers([]);
      });
    return () => {
      cancelled = true;
    };
  }, [workgroup.profile, workgroup.id]);

  const hubName = workgroup.hub_id ?? workgroup.profile;
  const hub = profiles.find((p) => p.name === hubName);
  const ownPubkey = profiles.find((p) => p.name === workgroup.profile)
    ?.pubkey_b64;

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
      notify({
        message: `Added ${label} · group rekeyed`,
        variant: "success",
      });
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
      if (action === "kick") {
        await reloadMembers();
      }
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
              <span
                className={styles.peerAccentDot}
                style={{
                  backgroundColor: hub?.accent || "var(--color-accent)",
                }}
              />
              <span className={styles.mono}>@{hubName}</span>
            </span>
          </Row>
          <Row label="status">
            <span className={styles.inlineRow}>
              {workgroup.paused ? (
                <Chip state="off" activity={busyAction === "resume"}>
                  paused
                </Chip>
              ) : (
                <Chip state="on" activity={busyAction === "pause"}>
                  active
                </Chip>
              )}
              <span className={styles.btnGroup}>
                {workgroup.is_hub ? (
                  workgroup.paused ? (
                    <Button
                      size="sm"
                      onClick={() => act("resume")}
                      disabled={busy}
                    >
                      Resume
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      onClick={() => act("pause")}
                      disabled={busy}
                    >
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
            <Row label="loading">
              <span className={styles.muted}>…</span>
            </Row>
          ) : members.filter((m) => m.joined).length === 0 ? (
            <Row label="list">
              <span className={styles.muted}>none</span>
            </Row>
          ) : (
            members
              .filter((m) => m.joined)
              .map((m) => renderMemberRow(m, profiles, styles))
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
                            leading={
                              <span
                                className={styles.peerAccentDot}
                                style={{
                                  backgroundColor:
                                    local?.accent || "var(--color-accent)",
                                }}
                              />
                            }
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
            members.filter((m) => m.joined && m.pubkey !== ownPubkey).length >
              0 && (
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
                            ? `@${local.name}`
                            : `${(m.pubkey || "").slice(0, 8)}…`;
                          return (
                            <Dropdown.Row
                              key={m.pubkey}
                              caption={(m.pubkey || "").slice(0, 16) + "…"}
                              leading={
                                <span
                                  className={styles.peerAccentDot}
                                  style={{
                                    backgroundColor:
                                      local?.accent || "var(--color-accent)",
                                  }}
                                />
                              }
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
              .map((m) => renderMemberRow(m, profiles, styles))}
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

function Section({ title, tooltip, children }) {
  const titleEl = (
    <div
      className={`${styles.sectionTitle} ${tooltip ? styles.sectionTitleHelp : ""}`}
    >
      {title}
      {tooltip && <span className={styles.sectionHelpMark}>?</span>}
    </div>
  );
  return (
    <section className={styles.section}>
      {tooltip ? (
        <Tooltip text={tooltip} direction="down">
          {titleEl}
        </Tooltip>
      ) : (
        titleEl
      )}
      <div className={styles.sectionBody}>{children}</div>
    </section>
  );
}

function Row({ label, alignTop, children }) {
  return (
    <div
      className={`${styles.row} ${alignTop ? styles.rowAlignTop : ""}`}
    >
      <span className={styles.rowLabel}>{label}</span>
      <div className={styles.rowValue}>{children}</div>
    </div>
  );
}

const SUBSYSTEMS = ["gateway", "schedule", "alp", "workgroups"];

const SUBSYSTEM_DESC = {
  gateway: "Telegram, IMAP & Gmail polling",
  schedule: "Cron jobs",
  alp: "Inter-machine peer protocol",
  workgroups: "Workgroup background poller",
};

const GATEWAY_DESC = {
  telegram: "Telegram bot",
  imap: "Email via IMAP",
  gmail: "Email via Gmail OAuth",
  matrix: "Matrix bot (no-E2EE MVP)",
};

function SubsystemsCell({ profile, onSaved }) {
  const notify = useNotify();
  const [busy, setBusy] = useState(null);
  const subs = profile.subsystems ?? {
    gateway: true,
    schedule: true,
    alp: true,
    workgroups: true,
  };
  async function toggle(key) {
    if (busy) return;
    const next = !subs[key];
    setBusy(key);
    try {
      await invoke("set_config_field", {
        profile: profile.name,
        key: `service.${key}`,
        value: String(next),
      });
      // Best-effort — config.yaml is already persisted on failure.
      if (profile.running) {
        invoke("daemon_restart").catch(() => {});
      }
      await onSaved?.();
      notify({
        message: profile.running
          ? `${key} ${next ? "enabled" : "disabled"} · daemon restarting`
          : `${key} ${next ? "enabled" : "disabled"}`,
        variant: "success",
        duration: profile.running ? 3000 : 2400,
      });
    } catch (e) {
      notify({
        message: `${key}: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    } finally {
      setBusy(null);
    }
  }
  return (
    <span className={styles.gatewayChips}>
      {SUBSYSTEMS.map((k) => {
        const enabled = subs[k];
        const state = !profile.running
          ? "off"
          : enabled
            ? "on"
            : "error";
        const desc = SUBSYSTEM_DESC[k];
        const status = !profile.running
          ? "daemon stopped"
          : enabled
            ? "running · click to disable"
            : "disabled · click to enable";
        const tooltip = (
          <>
            <div>{desc}</div>
            <div className={styles.tooltipStatus}>{status}</div>
          </>
        );
        return (
          <Chip
            key={k}
            state={state}
            tooltip={tooltip}
            onClick={busy ? undefined : () => toggle(k)}
          >
            {k}
          </Chip>
        );
      })}
    </span>
  );
}

function ConfirmButton({
  label,
  confirmLabel,
  disabled,
  loading,
  size,
  onConfirm,
  resetMs = 4000,
}) {
  const [armed, setArmed] = useState(false);
  const timerRef = useRef(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  useEffect(() => {
    if (loading && armed) setArmed(false);
  }, [loading, armed]);

  function click() {
    if (armed) {
      if (timerRef.current) clearTimeout(timerRef.current);
      setArmed(false);
      onConfirm?.();
      return;
    }
    setArmed(true);
    timerRef.current = setTimeout(() => setArmed(false), resetMs);
  }

  return (
    <Button
      size={size}
      variant={armed && !loading ? "danger" : "ghost"}
      active={armed && !loading}
      disabled={disabled}
      loading={loading}
      onClick={click}
    >
      {armed ? confirmLabel : label}
    </Button>
  );
}

function CopyButton({ value, message }) {
  const notify = useNotify();
  return (
    <Button
      size="sm"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value);
          notify({ message, variant: "success" });
        } catch (e) {
          notify({ message: `Copy failed: ${e}`, variant: "error" });
        }
      }}
    >
      Copy
    </Button>
  );
}

// ``ServiceCell`` was removed when the alpi daemon went one-per-
// machine. The desktop only renders if it can reach the host plane
// over a Unix socket — which means the daemon is by definition
// running. Install / start / stop / restart / uninstall live in the
// CLI (``alpi daemon ...``) and the ``alpi setup`` wizard.

function WorkspaceField({ value, onChange }) {
  async function browse() {
    try {
      const path = await invoke("pick_folder");
      if (path) onChange(path);
    } catch {}
  }
  return (
    <span
      className={styles.inlineRow}
      style={{ flex: 1, width: "100%", maxWidth: 520 }}
    >
      <input
        className={styles.input}
        style={{ maxWidth: "none", flex: 1, minWidth: 0 }}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="absolute path"
      />
      <Button size="sm" onClick={browse}>
        Browse…
      </Button>
    </span>
  );
}

function formatTcpLabel(host, port) {
  const h = (host || "").trim();
  if (!h || h === "127.0.0.1") return `tcp:${port}`;
  const truncated = h.length > 20 ? `${h.slice(0, 17)}…` : h;
  return `tcp:${truncated}:${port}`;
}

const VOICE_SHORTLIST = [
  { id: "en-US-AriaNeural", name: "Aria", desc: "English (US) · female" },
  { id: "en-US-GuyNeural", name: "Guy", desc: "English (US) · male" },
  { id: "en-GB-SoniaNeural", name: "Sonia", desc: "English (UK) · female" },
  { id: "es-ES-AlvaroNeural", name: "Alvaro", desc: "Spanish (ES) · male" },
  { id: "es-ES-ElviraNeural", name: "Elvira", desc: "Spanish (ES) · female" },
  { id: "es-MX-DaliaNeural", name: "Dalia", desc: "Spanish (MX) · female" },
  { id: "fr-FR-DeniseNeural", name: "Denise", desc: "French · female" },
  { id: "de-DE-KatjaNeural", name: "Katja", desc: "German · female" },
  { id: "it-IT-ElsaNeural", name: "Elsa", desc: "Italian · female" },
  { id: "pt-BR-FranciscaNeural", name: "Francisca", desc: "Portuguese (BR) · female" },
];

function McpField({ profile, onSaved }) {
  const [adding, setAdding] = useState(false);
  const [viewing, setViewing] = useState(null);
  const mcps = profile.mcps ?? [];

  return (
    <Row label="mcps">
      <span className={styles.gatewayChips}>
        {mcps.length === 0 && (
          <span className={styles.muted}>none</span>
        )}
        {mcps.map((m) => (
          <Chip
            key={m.name}
            state="on"
            onClick={() => setViewing(m.name)}
          >
            {m.name}
          </Chip>
        ))}
        <Button size="sm" onClick={() => setAdding(true)}>
          + Add MCP
        </Button>
      </span>
      {adding && (
        <McpAddModal
          profile={profile}
          existingNames={mcps.map((m) => m.name)}
          onClose={() => setAdding(false)}
          onSaved={async () => {
            await onSaved?.();
            setAdding(false);
          }}
        />
      )}
      {viewing && (
        <McpDetailModal
          profile={profile}
          mcp={mcps.find((m) => m.name === viewing)}
          onClose={() => setViewing(null)}
          onRemoved={async () => {
            await onSaved?.();
            setViewing(null);
          }}
        />
      )}
    </Row>
  );
}

function McpDetailModal({ profile, mcp, onClose, onRemoved }) {
  const notify = useNotify();
  const [busy, setBusy] = useState(false);
  const wrapRef = useRef(null);

  useEffect(() => {
    function onClick(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        onClose();
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [onClose]);

  if (!mcp) return null;

  async function remove() {
    setBusy(true);
    try {
      await invoke("mcp_remove", {
        profile: profile.name,
        name: mcp.name,
      });
      notify({
        message: `MCP @${mcp.name} removed`,
        variant: "success",
      });
      onRemoved();
    } catch (e) {
      notify({
        message: `remove: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={styles.gatewayBackdrop}>
      <div ref={wrapRef} className={styles.gatewayModal}>
        <div className={styles.gatewayModalTitle}>MCP · {mcp.name}</div>
        <div className={styles.tcpField}>
          <label className={styles.tcpLabel}>command</label>
          <span className={styles.mono}>{mcp.command || "(none)"}</span>
        </div>
        <div className={styles.tcpField}>
          <label className={styles.tcpLabel}>args</label>
          <span className={styles.mono}>
            {(mcp.args ?? []).length === 0
              ? "(none)"
              : (mcp.args ?? []).join(" ")}
          </span>
        </div>
        <div className={styles.tcpField}>
          <label className={styles.tcpLabel}>env</label>
          <span className={styles.inlineRow}>
            {(mcp.env_keys ?? []).length === 0 ? (
              <span className={styles.muted}>none</span>
            ) : (
              (mcp.env_keys ?? []).map((k) => (
                <Chip key={k} size="sm" state="on">
                  {k}
                </Chip>
              ))
            )}
          </span>
        </div>
        <div className={styles.muted} style={{ fontSize: "var(--font-size-tiny)" }}>
          To edit, remove and add again. Env values are never read back from disk.
        </div>
        <div className={styles.tcpActions}>
          <ConfirmButton
            size="sm"
            label="Remove"
            confirmLabel="Confirm remove"
            loading={busy}
            onConfirm={remove}
          />
          <Button size="sm" onClick={onClose} disabled={busy}>
            Close
          </Button>
        </div>
      </div>
    </div>
  );
}

function McpAddModal({ profile, existingNames, onClose, onSaved }) {
  const notify = useNotify();
  const [name, setName] = useState("");
  const [command, setCommand] = useState("");
  const [args, setArgs] = useState("");
  const [envText, setEnvText] = useState("");
  const [busy, setBusy] = useState(false);
  const wrapRef = useRef(null);

  useEffect(() => {
    function onClick(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        onClose();
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [onClose]);

  const trimmed = name.trim();
  const validName =
    trimmed !== "" && /^[a-z0-9_-]+$/.test(trimmed);
  const duplicate = existingNames.includes(trimmed);
  const validCommand = command.trim() !== "";
  const canSubmit = validName && validCommand && !duplicate && !busy;

  async function save() {
    if (!canSubmit) return;
    setBusy(true);
    try {
      const envPairs = envText
        .split("\n")
        .map((l) => l.trim())
        .filter((l) => l && l.includes("="));
      await invoke("mcp_add", {
        profile: profile.name,
        name: trimmed,
        command: command.trim(),
        args: args.trim(),
        env: envPairs,
      });
      notify({ message: `MCP @${trimmed} added`, variant: "success" });
      onSaved();
    } catch (e) {
      notify({
        message: `add MCP: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={styles.gatewayBackdrop}>
      <div ref={wrapRef} className={styles.gatewayModal}>
        <div className={styles.gatewayModalTitle}>Add MCP server</div>
        <div className={styles.muted} style={{ marginBottom: 4 }}>
          Example — GitHub MCP: command <code>npx</code>, args{" "}
          <code>-y @modelcontextprotocol/server-github</code>, env{" "}
          <code>GITHUB_TOKEN=ghp_…</code>.
        </div>
        <div className={styles.tcpField}>
          <label className={styles.tcpLabel}>name</label>
          <input
            className={styles.input}
            style={{ maxWidth: "none" }}
            value={name}
            onChange={(e) => setName(e.target.value.toLowerCase())}
            placeholder="github · notion · linear"
            spellCheck={false}
            autoFocus
          />
          {duplicate && (
            <span className={styles.error} style={{ marginTop: 4 }}>
              @{trimmed} already exists
            </span>
          )}
        </div>
        <div className={styles.tcpField}>
          <label className={styles.tcpLabel}>command</label>
          <input
            className={styles.input}
            style={{ maxWidth: "none" }}
            value={command}
            onChange={(e) => setCommand(e.target.value)}
            placeholder="npx · uvx · python · /path/to/server"
            spellCheck={false}
          />
        </div>
        <div className={styles.tcpField}>
          <label className={styles.tcpLabel}>args</label>
          <input
            className={styles.input}
            style={{ maxWidth: "none" }}
            value={args}
            onChange={(e) => setArgs(e.target.value)}
            placeholder="space-separated · use quotes for grouping"
            spellCheck={false}
          />
        </div>
        <div className={styles.tcpField}>
          <label className={styles.tcpLabel}>env (KEY=VALUE per line)</label>
          <Textarea
            className={styles.textarea}
            style={{ maxWidth: "none" }}
            rows={3}
            value={envText}
            onChange={(e) => setEnvText(e.target.value)}
            placeholder={"GITHUB_TOKEN=ghp_xxx\nFOO=bar"}
            spellCheck={false}
          />
        </div>
        <div className={styles.tcpActions}>
          <Button size="sm" onClick={onClose} disabled={busy}>
            Close
          </Button>
          <Button
            size="sm"
            variant="primary"
            onClick={save}
            disabled={!canSubmit}
            loading={busy}
          >
            Add
          </Button>
        </div>
      </div>
    </div>
  );
}

function VoiceField({ profile, onSaved }) {
  const notify = useNotify();
  const [busy, setBusy] = useState(null);
  const voiceId = profile.voice_id ?? "en-US-AriaNeural";
  const autoplay = !!profile.voice_autoplay;
  const current =
    VOICE_SHORTLIST.find((v) => v.id === voiceId) ?? {
      id: voiceId,
      name: voiceId,
      desc: "(custom)",
    };

  async function pickVoice(id) {
    setBusy("voice");
    try {
      await invoke("voice_set_voice", {
        profile: profile.name,
        voiceId: id,
      });
      await onSaved?.();
    } catch (e) {
      notify({
        message: `voice: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    } finally {
      setBusy(null);
    }
  }

  async function toggleAutoplay() {
    setBusy("autoplay");
    try {
      await invoke("voice_autoplay", {
        profile: profile.name,
        state: autoplay ? "off" : "on",
      });
      await onSaved?.();
    } catch (e) {
      notify({
        message: `autoplay: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    } finally {
      setBusy(null);
    }
  }

  async function testVoice() {
    setBusy("test");
    try {
      await invoke("voice_test", {
        profile: profile.name,
        voiceId: voiceId,
      });
    } catch (e) {
      notify({
        message: `voice test: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <Row label="voice">
        <span className={styles.inlineRow}>
          <Dropdown
            trigger={{ label: `${current.name} · ${current.desc}` }}
            direction="down"
            align="left"
            width={320}
            variant="outlined"
          >
            {({ close }) =>
              VOICE_SHORTLIST.map((v) => (
                <Dropdown.Row
                  key={v.id}
                  active={v.id === voiceId}
                  caption={v.desc}
                  onClick={() => {
                    close();
                    if (v.id !== voiceId) pickVoice(v.id);
                  }}
                >
                  {v.name}
                </Dropdown.Row>
              ))
            }
          </Dropdown>
          <Button
            size="sm"
            onClick={testVoice}
            disabled={!!busy}
            loading={busy === "test"}
            title="play a localized greeting in this voice"
          >
            Test
          </Button>
        </span>
      </Row>
      <Row label="autoplay">
        <span className={styles.inlineRow}>
          <Chip
            state={autoplay ? "on" : "off"}
            tooltip={
              autoplay
                ? "speak the assistant's reply through your speakers"
                : "TTS available on demand only — no autoplay"
            }
          >
            {autoplay ? "on" : "off"}
          </Chip>
          <Button
            size="sm"
            onClick={toggleAutoplay}
            disabled={!!busy}
            loading={busy === "autoplay"}
          >
            {autoplay ? "Disable" : "Enable"}
          </Button>
        </span>
      </Row>
    </>
  );
}

function SandboxField({ profile, onSaved }) {
  const notify = useNotify();
  const [busy, setBusy] = useState(null);
  const sandbox = !!profile.sandbox;
  const network = !!profile.sandbox_allow_network;

  async function setSandbox(state) {
    setBusy("sandbox");
    try {
      await invoke("sandbox_set", { profile: profile.name, state });
      await onSaved?.();
    } catch (e) {
      notify({
        message: `sandbox: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    } finally {
      setBusy(null);
    }
  }

  async function setNetwork(state) {
    setBusy("network");
    try {
      await invoke("sandbox_network", {
        profile: profile.name,
        state,
      });
      await onSaved?.();
    } catch (e) {
      notify({
        message: `network: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <Row label="terminal">
        <span className={styles.inlineRow}>
          <Chip
            state={sandbox ? "on" : "off"}
            tooltip={
              <>
                <div>Wraps shell commands in sandbox-exec / bubblewrap</div>
                <div className={styles.tooltipStatus}>
                  blocks writes outside workspace + ~/.alpi
                </div>
              </>
            }
          >
            {sandbox ? "sandboxed" : "off"}
          </Chip>
          <Button
            size="sm"
            onClick={() => setSandbox(sandbox ? "off" : "on")}
            disabled={!!busy}
            loading={busy === "sandbox"}
          >
            {sandbox ? "Disable" : "Enable"}
          </Button>
        </span>
      </Row>
      <Row label="network">
        <span className={styles.inlineRow}>
          <Chip
            state={!sandbox ? "off" : network ? "on" : "error"}
            tooltip={
              !sandbox
                ? "enable sandbox first"
                : network
                  ? "sub-processes can reach the internet (git push, pip install, …)"
                  : "denied — sub-processes can't open sockets (safest)"
            }
          >
            {!sandbox ? "n/a" : network ? "allowed" : "denied"}
          </Chip>
          <Button
            size="sm"
            onClick={() => setNetwork(network ? "off" : "on")}
            disabled={!sandbox || !!busy}
            loading={busy === "network"}
          >
            {network ? "Deny" : "Allow"}
          </Button>
        </span>
      </Row>
    </>
  );
}

function BudgetField({ profile, onSaved }) {
  const notify = useNotify();
  const usd = profile.budget_daily_usd;
  const tokens = profile.budget_daily_tokens;

  let chip;
  if (usd != null) {
    chip = <Chip>${usd.toFixed(2)}/day</Chip>;
  } else if (tokens != null) {
    chip = <Chip>{formatTokenCount(tokens)}/day</Chip>;
  } else {
    chip = <span className={styles.muted}>unlimited</span>;
  }

  async function save({ kind, value }) {
    try {
      if (value == null) {
        await invoke("unset_config_field", {
          profile: profile.name,
          key: "budget.daily_usd",
        });
        await invoke("unset_config_field", {
          profile: profile.name,
          key: "budget.daily_tokens",
        });
      } else if (kind === "usd") {
        await invoke("unset_config_field", {
          profile: profile.name,
          key: "budget.daily_tokens",
        });
        await invoke("set_config_field", {
          profile: profile.name,
          key: "budget.daily_usd",
          value: String(value),
        });
      } else {
        await invoke("unset_config_field", {
          profile: profile.name,
          key: "budget.daily_usd",
        });
        await invoke("set_config_field", {
          profile: profile.name,
          key: "budget.daily_tokens",
          value: String(value),
        });
      }
      await onSaved?.();
    } catch (e) {
      notify({
        message: `budget: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
      throw e;
    }
  }

  return (
    <Row label="budget">
      <span className={styles.inlineRow}>
        {chip}
        <ProfileBudgetEditor
          currentUsd={usd}
          currentTokens={tokens}
          onSave={save}
        />
      </span>
    </Row>
  );
}

function formatTokenCount(n) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M tokens`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(n < 10_000 ? 1 : 0)}K tokens`;
  return `${n} tokens`;
}

function ProfileBudgetEditor({ currentUsd, currentTokens, onSave }) {
  const [open, setOpen] = useState(false);
  const anchorRef = useRef(null);
  const popoverRef = useRef(null);
  const wrapRef = useRef(null);
  const initialKind = currentTokens != null ? "tokens" : "usd";
  const [kind, setKind] = useState(initialKind);
  const [value, setValue] = useState(
    currentUsd != null
      ? String(currentUsd)
      : currentTokens != null
        ? String(currentTokens)
        : "",
  );
  const [saving, setSaving] = useState(false);
  const pos = useAutoPosition({
    open,
    anchorRef,
    popoverRef,
    direction: "down",
    align: "left",
  });

  useEffect(() => {
    if (open) {
      setKind(currentTokens != null ? "tokens" : "usd");
      setValue(
        currentUsd != null
          ? String(currentUsd)
          : currentTokens != null
            ? String(currentTokens)
            : "",
      );
    }
  }, [open, currentUsd, currentTokens]);

  useEffect(() => {
    if (!open) return;
    function onClick(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  const trimmed = value.trim();
  let parsed = null;
  let valid = trimmed === "";
  if (trimmed !== "") {
    if (kind === "usd") {
      const n = Number(trimmed);
      valid = Number.isFinite(n) && n > 0;
      if (valid) parsed = n;
    } else {
      const n = parseInt(trimmed, 10);
      valid =
        Number.isFinite(n) && n > 0 && /^\d+$/.test(trimmed);
      if (valid) parsed = n;
    }
  }

  async function save() {
    if (!valid || saving) return;
    setSaving(true);
    try {
      await onSave?.({ kind, value: parsed });
      setOpen(false);
    } catch {
    } finally {
      setSaving(false);
    }
  }

  const hasAny = currentUsd != null || currentTokens != null;

  return (
    <span ref={wrapRef} className={styles.tcpWrap}>
      <span ref={anchorRef}>
        <Button size="sm" onClick={() => setOpen((o) => !o)}>
          {hasAny ? "Edit" : "Set cap"}
        </Button>
      </span>
      {open && (
        <div
          ref={popoverRef}
          className={styles.tcpPopover}
          style={{
            minWidth: 280,
            maxWidth: pos.maxWidth ?? undefined,
            position: "fixed",
            top: pos.top,
            left: pos.left,
            right: "auto",
            bottom: "auto",
            visibility: pos.ready ? "visible" : "hidden",
          }}
        >
          <div className={styles.tcpField}>
            <label className={styles.tcpLabel}>cap type</label>
            <span className={styles.inlineRow}>
              <Chip
                size="sm"
                state={kind === "usd" ? "on" : "off"}
                onClick={() => setKind("usd")}
                tooltip="for paid models — daily USD spend"
              >
                USD
              </Chip>
              <Chip
                size="sm"
                state={kind === "tokens" ? "on" : "off"}
                onClick={() => setKind("tokens")}
                tooltip="for local / free models — daily token count"
              >
                tokens
              </Chip>
            </span>
          </div>
          <div className={styles.tcpField}>
            <label className={styles.tcpLabel}>
              {kind === "usd" ? "daily USD" : "daily tokens"}
            </label>
            <input
              className={styles.input}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="empty = unlimited"
              spellCheck={false}
              autoFocus
            />
          </div>
          {!valid && (
            <div className={styles.tcpWarn}>
              {kind === "usd"
                ? "must be a positive number"
                : "must be a positive integer"}
            </div>
          )}
          <div className={styles.tcpActions}>
            <Button
              size="sm"
              variant="primary"
              onClick={save}
              disabled={!valid}
              loading={saving}
            >
              Save
            </Button>
          </div>
        </div>
      )}
    </span>
  );
}

function TcpPortField({ profile, onSaved }) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const notify = useNotify();
  const [host, setHost] = useState(profile.tcp_host || "127.0.0.1");
  const [port, setPort] = useState(
    profile.tcp_port ? String(profile.tcp_port) : "",
  );
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setHost(profile.tcp_host || "127.0.0.1");
    setPort(profile.tcp_port ? String(profile.tcp_port) : "");
  }, [profile.tcp_host, profile.tcp_port]);

  useEffect(() => {
    if (!open) return;
    function onClick(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  const portTrim = port.trim();
  const portValid = portTrim === "" || /^[0-9]+$/.test(portTrim);
  const portNum = portTrim === "" ? 0 : Number(portTrim);
  const portInRange =
    portTrim === "" || (portNum >= 1 && portNum <= 65535);
  const dirty =
    host.trim() !== (profile.tcp_host || "127.0.0.1") ||
    portTrim !== (profile.tcp_port ? String(profile.tcp_port) : "");

  const [portFree, setPortFree] = useState(null);
  useEffect(() => {
    if (!open || !portInRange || portTrim === "") {
      setPortFree(null);
      return;
    }
    if (portNum === profile.tcp_port) {
      setPortFree(true);
      return;
    }
    let cancelled = false;
    const id = setTimeout(() => {
      invoke("port_available", {
        host: host.trim() || "127.0.0.1",
        port: portNum,
      })
        .then((ok) => {
          if (!cancelled) setPortFree(ok);
        })
        .catch(() => {
          if (!cancelled) setPortFree(null);
        });
    }, 350);
    return () => {
      cancelled = true;
      clearTimeout(id);
    };
  }, [open, portTrim, portNum, host, portInRange, profile.tcp_port]);

  async function save() {
    if (!portValid || !portInRange || saving) return;
    if (portTrim !== "" && portFree === false) return;
    setSaving(true);
    try {
      if (portTrim === "") {
        await invoke("unset_config_field", {
          profile: profile.name,
          key: "alp.tcp_port",
        });
        await invoke("unset_config_field", {
          profile: profile.name,
          key: "alp.tcp_host",
        });
      } else {
        await invoke("set_config_field", {
          profile: profile.name,
          key: "alp.tcp_host",
          value: host.trim() || "127.0.0.1",
        });
        await invoke("set_config_field", {
          profile: profile.name,
          key: "alp.tcp_port",
          value: portTrim,
        });
      }
      invoke("daemon_restart").catch(() => {});
      await onSaved?.();
      notify({
        message: portTrim
          ? `TCP listener ${host.trim()}:${portTrim} · daemon restarting`
          : "TCP listener disabled · daemon restarting",
        variant: "success",
        duration: 3000,
      });
      setOpen(false);
    } catch (e) {
      notify({
        message: `tcp: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <span ref={wrapRef} className={styles.tcpWrap}>
      <Chip
        state={profile.tcp_port ? "on" : "off"}
        onClick={() => setOpen((o) => !o)}
        tooltip={
          <>
            <div>ALP TCP listener</div>
            <div className={styles.tooltipStatus}>
              {profile.tcp_port
                ? `${profile.tcp_host || "127.0.0.1"}:${profile.tcp_port} · click to edit`
                : "disabled · click to enable"}
            </div>
          </>
        }
      >
        {profile.tcp_port
          ? formatTcpLabel(profile.tcp_host, profile.tcp_port)
          : "tcp off"}
      </Chip>
      {open && (
        <div className={styles.tcpPopover}>
          <div className={styles.tcpField}>
            <label className={styles.tcpLabel}>host</label>
            <input
              className={styles.input}
              value={host}
              onChange={(e) => setHost(e.target.value)}
              placeholder="127.0.0.1"
              spellCheck={false}
            />
          </div>
          <div className={styles.tcpField}>
            <label className={styles.tcpLabel}>port</label>
            <input
              className={styles.input}
              value={port}
              onChange={(e) => setPort(e.target.value)}
              placeholder="empty to disable"
              spellCheck={false}
            />
          </div>
          {host.trim() === "0.0.0.0" && (
            <div className={styles.tcpWarn}>
              0.0.0.0 exposes the port to all interfaces. Use only behind a
              VPN.
            </div>
          )}
          {!portInRange && (
            <div className={styles.tcpWarn}>Port must be 1-65535.</div>
          )}
          {portInRange && portTrim !== "" && portFree === false && (
            <div className={styles.tcpWarn}>
              Port {portTrim} is in use on {host.trim() || "127.0.0.1"}.
            </div>
          )}
          <div className={styles.tcpActions}>
            <Button
              size="sm"
              onClick={save}
              disabled={
                !dirty ||
                !portInRange ||
                (portTrim !== "" && portFree === false)
              }
              loading={saving}
              variant="primary"
            >
              Save
            </Button>
          </div>
        </div>
      )}
    </span>
  );
}

function GatewaysCell({ profile }) {
  const [statuses, setStatuses] = useState([]);
  const [probes, setProbes] = useState(null);
  const [tick, setTick] = useState(0);
  const [editing, setEditing] = useState(null);
  // The chips are dead config when the parent ``gateway`` service
  // is off — the daemon won't poll telegram/imap/gmail, so editing
  // credentials goes nowhere. Disable + retag the tooltip so the
  // user understands they need to enable the service first.
  const gatewayServiceOff = profile.subsystems?.gateway === false;

  useEffect(() => {
    let cancelled = false;
    setProbes(null);
    invoke("gateway_status", { profile: profile.name })
      .then((s) => {
        if (cancelled) return;
        setStatuses(s);
        const toProbe = s.filter((g) => g.configured).map((g) => g.name);
        if (toProbe.length === 0) {
          setProbes({});
          return;
        }
        invoke("probe_gateways", { profile: profile.name, only: toProbe })
          .then((r) => {
            if (cancelled) return;
            const map = {};
            for (const p of r) map[p.name] = p;
            setProbes(map);
          })
          .catch(() => {
            if (!cancelled) setProbes({});
          });
      })
      .catch(() => {
        if (!cancelled) {
          setStatuses([]);
          setProbes({});
        }
      });
    return () => {
      cancelled = true;
    };
  }, [profile.name, tick]);

  return (
    <span className={styles.gatewayChips}>
      {(statuses.length > 0 ? statuses : [
        { name: "telegram", configured: false },
        { name: "imap", configured: false },
        { name: "gmail", configured: false },
        { name: "matrix", configured: false },
      ]).map((g) => {
        const desc = GATEWAY_DESC[g.name] ?? g.name;
        const probe = probes?.[g.name];
        const probing = g.configured && !probe;
        let status;
        let state;
        if (!g.configured) {
          state = "off";
          status = "not configured";
        } else if (probing) {
          state = undefined;
          status = "probing…";
        } else if (probe?.status === "on") {
          state = "on";
          status = "reachable";
        } else if (probe?.status === "error") {
          state = "error";
          status = probe.reason || "unreachable";
        } else {
          state = "off";
          status = "not configured";
        }
        const tooltip = (
          <>
            <div>{desc}</div>
            <div className={styles.tooltipStatus}>
              {gatewayServiceOff
                ? "gateway service is off — enable it to configure"
                : `${status} · click to edit`}
            </div>
          </>
        );
        return (
          <Chip
            key={g.name}
            state={state}
            activity={probing}
            tooltip={tooltip}
            disabled={gatewayServiceOff}
            onClick={() => setEditing(g.name)}
          >
            {g.name}
          </Chip>
        );
      })}
      {editing && (
        <GatewayEditorModal
          profile={profile}
          gateway={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setTick((t) => t + 1);
            setEditing(null);
          }}
        />
      )}
    </span>
  );
}

function SchedulesSection({ profile }) {
  const [jobs, setJobs] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const notify = useNotify();

  async function load() {
    try {
      const list = await invoke("schedules", { profile: profile.name });
      setJobs(Array.isArray(list) ? list : []);
    } catch {
      setJobs([]);
    }
  }

  useEffect(() => {
    load();
  }, [profile.name]);

  async function fire(id) {
    setBusyId(`fire:${id}`);
    try {
      await invoke("schedule_fire", { profile: profile.name, id });
      notify({ message: `fired ${id}`, variant: "success", duration: 2400 });
      await load();
    } catch (e) {
      notify({
        message: `fire failed: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    } finally {
      setBusyId(null);
    }
  }

  async function setPaused(id, paused) {
    setBusyId(`pause:${id}`);
    try {
      await invoke("schedule_set_paused", {
        profile: profile.name,
        id,
        paused,
      });
      await load();
    } catch (e) {
      notify({
        message: `${paused ? "pause" : "resume"} failed: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    } finally {
      setBusyId(null);
    }
  }

  async function remove(id) {
    setBusyId(`del:${id}`);
    try {
      await invoke("schedule_remove", { profile: profile.name, id });
      await load();
    } catch (e) {
      notify({
        message: `delete failed: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    } finally {
      setBusyId(null);
    }
  }

  if (jobs === null || jobs.length === 0) {
    return null;
  }
  return (
    <Section title="Schedule">
      {jobs.map((j) => (
        <Row key={j.id} label={j.id}>
          <ScheduleRowBody
            job={j}
            busyId={busyId}
            onFire={() => fire(j.id)}
            onTogglePause={() => setPaused(j.id, !j.paused)}
            onRemove={() => remove(j.id)}
          />
        </Row>
      ))}
    </Section>
  );
}

function ScheduleRowBody({ job, busyId, onFire, onTogglePause, onRemove }) {
  const fireBusy = busyId === `fire:${job.id}`;
  const pauseBusy = busyId === `pause:${job.id}`;
  const delBusy = busyId === `del:${job.id}`;
  const anyBusy = !!busyId;
  const tooltip = (
    <>
      <div>{scheduleSummary(job)}</div>
      <div className={styles.tooltipStatus}>
        {[
          job.paused ? "paused" : "active",
          job.platform || "telegram",
          job.chat_id || null,
          job.last_run_at ? `last ${job.last_run_at}` : null,
        ]
          .filter(Boolean)
          .join(" · ")}
      </div>
    </>
  );
  return (
    <span
      className={styles.inlineRow}
      style={{ justifyContent: "space-between", gap: 12, flex: 1, minWidth: 0 }}
    >
      <span
        className={styles.inlineRow}
        style={{ gap: 8, minWidth: 0, flex: 1 }}
      >
        <Chip state={job.paused ? "off" : "on"} tooltip={tooltip}>
          {scheduleSummary(job)}
        </Chip>
        <span
          style={{
            fontSize: "var(--font-size-small)",
            color: "var(--color-fg-muted)",
            opacity: job.paused ? 0.55 : 1,
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
            minWidth: 0,
            flex: 1,
          }}
          title={job.prompt || ""}
        >
          {job.prompt || ""}
        </span>
      </span>
      <span className={styles.btnGroup}>
        <Button
          size="sm"
          onClick={onFire}
          loading={fireBusy}
          disabled={anyBusy}
        >
          Fire
        </Button>
        <Button
          size="sm"
          onClick={onTogglePause}
          loading={pauseBusy}
          disabled={anyBusy}
        >
          {job.paused ? "Enable" : "Disable"}
        </Button>
        <ConfirmButton
          size="sm"
          label="Delete"
          confirmLabel="Confirm"
          disabled={anyBusy && !delBusy}
          loading={delBusy}
          onConfirm={onRemove}
        />
      </span>
    </span>
  );
}

function scheduleSummary(j) {
  if (j.kind === "cron") return `cron ${j.expression || "?"}`;
  if (j.kind === "once") return `once ${j.run_at || "?"}`;
  if (j.kind === "inactivity") return `after ${j.after_hours ?? "?"}h`;
  return j.kind || "?";
}

const GATEWAY_FIELDS = {
  telegram: [
    {
      env: "TELEGRAM_BOT_TOKEN",
      label: "Bot token",
      secret: true,
      hint: "from @BotFather",
    },
    {
      env: "TELEGRAM_ALLOWED_CHAT_IDS",
      label: "Allowed chat IDs",
      secret: false,
      hint: "comma-separated · empty = anyone (not recommended)",
    },
  ],
  imap: [
    {
      env: "IMAP_ADDRESS",
      label: "Email address",
      secret: false,
      hint: "you@domain.com",
    },
    {
      env: "IMAP_PASSWORD",
      label: "Password",
      secret: true,
      hint: "app password if 2FA",
    },
    {
      env: "IMAP_HOST",
      label: "Host",
      secret: false,
      hint: "imap.gmail.com · imap.fastmail.com · …",
    },
    {
      env: "IMAP_PORT",
      label: "Port",
      secret: false,
      hint: "993 (SSL) · 143 (STARTTLS)",
    },
    {
      env: "IMAP_ALLOWED_SENDERS",
      label: "Allowed senders",
      secret: false,
      hint: "comma-separated emails · empty = anyone",
    },
  ],
  matrix: [
    {
      env: "MATRIX_HOMESERVER_URL",
      label: "Homeserver URL",
      secret: false,
      hint: "http://umbrel.local:8008 · https://matrix.example.com",
    },
    {
      env: "MATRIX_USER_ID",
      label: "Bot user id",
      secret: false,
      hint: "@alpi-bot:server",
    },
    {
      env: "MATRIX_ACCESS_TOKEN",
      label: "Access token",
      secret: true,
      hint: "from /_matrix/client/r0/login",
    },
    {
      env: "MATRIX_DEVICE_ID",
      label: "Device id",
      secret: false,
      hint: "from the login response · optional but recommended",
    },
    {
      env: "MATRIX_ALLOWED_ROOMS",
      label: "Allowed rooms",
      secret: false,
      hint: "comma-separated room IDs (!abc:server) · fail-closed",
    },
    {
      env: "MATRIX_ALLOWED_SENDERS",
      label: "Allowed senders",
      secret: false,
      hint: "comma-separated user IDs (@user:server) · empty = all room members",
    },
  ],
};

function GatewayEditorModal({ profile, gateway, onClose, onSaved }) {
  const notify = useNotify();
  const [config, setConfig] = useState(null);
  const [values, setValues] = useState({});
  const [busy, setBusy] = useState(false);
  const wrapRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    invoke("gateway_config", {
      profile: profile.name,
      name: gateway,
    })
      .then((c) => {
        if (cancelled) return;
        setConfig(c);
        // Pre-fill non-secret fields; keep secrets blank.
        const fields = GATEWAY_FIELDS[gateway] ?? [];
        const initial = {};
        for (const f of fields) {
          if (!f.secret) initial[f.env] = c[f.env] ?? "";
          else initial[f.env] = "";
        }
        setValues(initial);
      })
      .catch(() => {
        if (!cancelled) setConfig({});
      });
    return () => {
      cancelled = true;
    };
  }, [profile.name, gateway]);

  useEffect(() => {
    function onClick(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        onClose();
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [onClose]);

  if (gateway === "gmail") {
    return (
      <div className={styles.gatewayBackdrop}>
        <div ref={wrapRef} className={styles.gatewayModal}>
          <div className={styles.gatewayModalTitle}>Gmail gateway</div>
          <div className={styles.muted}>
            {config?.GMAIL_CLIENT_ID
              ? "Configured · OAuth completed"
              : "Not configured"}
          </div>
          <div
            className={styles.muted}
            style={{ marginTop: "var(--space-2)" }}
          >
            Gmail uses OAuth and needs an interactive browser flow. Run:
          </div>
          <code className={styles.mono} style={{ display: "block", marginTop: 4 }}>
            alpi -p {profile.name} setup
          </code>
          <div
            className={styles.muted}
            style={{ marginTop: 4, fontSize: "var(--font-size-tiny)" }}
          >
            Settings → Services → gateways → Gmail
          </div>
          <div className={styles.tcpActions}>
            {config?.GMAIL_CLIENT_ID && (
              <ConfirmButton
                size="sm"
                label="Remove"
                confirmLabel="Confirm"
                onConfirm={async () => {
                  setBusy(true);
                  try {
                    await invoke("gateway_remove", {
                      profile: profile.name,
                      name: "gmail",
                    });
                    notify({
                      message: "Gmail gateway removed",
                      variant: "success",
                    });
                    onSaved();
                  } catch (e) {
                    notify({
                      message: `remove: ${String(e)}`,
                      variant: "error",
                      duration: 4000,
                    });
                  } finally {
                    setBusy(false);
                  }
                }}
              />
            )}
            <Button size="sm" onClick={onClose}>
              Close
            </Button>
          </div>
        </div>
      </div>
    );
  }

  const fields = GATEWAY_FIELDS[gateway] ?? [];
  const isConfigured = !!config && Object.keys(config).length > 0;

  async function save() {
    setBusy(true);
    try {
      for (const f of fields) {
        const next = (values[f.env] ?? "").trim();
        if (f.secret) {
          // Only write a secret when it changes.
          if (next) {
            await invoke("provider_set_key", {
              profile: profile.name,
              key: f.env,
              value: next,
            });
          }
        } else {
          // Empty clears plain keys; non-empty writes them.
          if (next === "") {
            const had = config?.[f.env];
            if (had) {
              await invoke("provider_unset_key", {
                profile: profile.name,
                key: f.env,
              });
            }
          } else if (next !== (config?.[f.env] ?? "")) {
            await invoke("provider_set_key", {
              profile: profile.name,
              key: f.env,
              value: next,
            });
          }
        }
      }
      invoke("daemon_restart").catch(() => {});
      notify({
        message: `${gateway} saved · daemon restarting`,
        variant: "success",
        duration: 3000,
      });
      onSaved();
    } catch (e) {
      notify({
        message: `save: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    try {
      await invoke("gateway_remove", {
        profile: profile.name,
        name: gateway,
      });
      notify({
        message: `${gateway} gateway removed`,
        variant: "success",
      });
      onSaved();
    } catch (e) {
      notify({
        message: `remove: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={styles.gatewayBackdrop}>
      <div ref={wrapRef} className={styles.gatewayModal}>
        <div className={styles.gatewayModalTitle}>
          {gateway} gateway
        </div>
        {fields.map((f) => {
          const preview = f.secret ? config?.[f.env] : null;
          return (
            <div key={f.env} className={styles.tcpField}>
              <label className={styles.tcpLabel}>{f.label}</label>
              <input
                className={styles.input}
                style={{ maxWidth: "none" }}
                type={f.secret ? "password" : "text"}
                value={values[f.env] ?? ""}
                onChange={(e) =>
                  setValues((v) => ({ ...v, [f.env]: e.target.value }))
                }
                placeholder={
                  f.secret && preview
                    ? `current: ${preview} (paste to replace)`
                    : f.hint
                }
                spellCheck={false}
              />
            </div>
          );
        })}
        <div className={styles.tcpActions}>
          {isConfigured && (
            <ConfirmButton
              size="sm"
              label="Remove"
              confirmLabel="Confirm"
              loading={busy}
              onConfirm={remove}
            />
          )}
          <Button size="sm" onClick={onClose} disabled={busy}>
            Close
          </Button>
          <Button
            size="sm"
            variant="primary"
            onClick={save}
            loading={busy}
          >
            Save
          </Button>
        </div>
      </div>
    </div>
  );
}

function AccentField({ value, onChange }) {
  const current = (value ?? "").toLowerCase();
  const valid = HEX_RE.test(current);
  return (
    <Dropdown
      trigger={{
        leading: (
          <span
            className={styles.accentTriggerDot}
            style={{ backgroundColor: valid ? current : "transparent" }}
          />
        ),
        label: current || "—",
      }}
      direction="down"
      align="left"
      width={220}
      variant="outlined"
    >
      {({ close }) => (
        <div className={styles.accentMenu}>
          <div
            className={`${styles.accentGrid} ${
              current ? styles.hasSelection : ""
            }`}
          >
            {ACCENT_PALETTE.map((hex) => (
              <button
                key={hex}
                className={`${styles.swatch} ${
                  hex.toLowerCase() === current ? styles.swatchActive : ""
                }`}
                style={{ backgroundColor: hex }}
                onClick={() => {
                  onChange(hex.toLowerCase());
                  close();
                }}
                aria-label={hex}
              />
            ))}
          </div>
          <input
            className={styles.accentHex}
            value={current}
            onChange={(e) => onChange(e.target.value)}
            placeholder="#hex"
            spellCheck={false}
          />
        </div>
      )}
    </Dropdown>
  );
}

const PAID_PROVIDERS = [
  { id: "anthropic", env: "ANTHROPIC_API_KEY", label: "Anthropic" },
  { id: "openai", env: "OPENAI_API_KEY", label: "OpenAI" },
  { id: "openrouter", env: "OPENROUTER_API_KEY", label: "OpenRouter" },
  { id: "gemini", env: "GEMINI_API_KEY", label: "Gemini" },
];

function AddProviderField({ profile, onSaved }) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const anchorRef = useRef(null);
  const popoverRef = useRef(null);
  const pos = useAutoPosition({
    open,
    anchorRef,
    popoverRef,
    direction: "down",
    align: "right",
  });

  useEffect(() => {
    if (!open) return;
    function onClick(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  return (
    <span ref={wrapRef} className={styles.tcpWrap}>
      <span ref={anchorRef}>
        <Button size="sm" onClick={() => setOpen((o) => !o)}>
          Providers
        </Button>
      </span>
      {open && (
        <div
          ref={popoverRef}
          className={styles.tcpPopover}
          style={{
            minWidth: 360,
            maxWidth: pos.maxWidth ?? undefined,
            width: 440,
            position: "fixed",
            top: pos.top,
            left: pos.left,
            right: "auto",
            bottom: "auto",
            visibility: pos.ready ? "visible" : "hidden",
          }}
        >
          <ProviderEditor
            profile={profile}
            onClose={() => setOpen(false)}
            onSaved={onSaved}
          />
        </div>
      )}
    </span>
  );
}

function ProviderEditor({ profile, onClose, onSaved }) {
  const notify = useNotify();
  const configured = profile.provider_keys ?? [];
  const configuredEnvs = new Set(configured.map((k) => k.env));
  const ollamas = profile.provider_ollama ?? [];
  const [pick, setPick] = useState("ollama");
  const [keyValue, setKeyValue] = useState("");
  const [ollamaName, setOllamaName] = useState("");
  const [ollamaUrl, setOllamaUrl] = useState("http://localhost:11434");
  const [orModel, setOrModel] = useState("");
  const [busy, setBusy] = useState(false);

  const isOllama = pick === "ollama";
  const isOpenRouter = pick === "openrouter";
  const provider = PAID_PROVIDERS.find((p) => p.id === pick);
  const savedOpenRouterModels = (profile.models ?? [])
    .filter((m) => m.startsWith("openrouter/"))
    .map((m) => m.slice("openrouter/".length));

  async function save() {
    if (busy) return;
    setBusy(true);
    try {
      if (isOllama) {
        const name = ollamaName.trim();
        const url = ollamaUrl.trim().replace(/\/$/, "");
        if (!name || !/^[a-z0-9_-]+$/.test(name)) {
          throw new Error("name must be lowercase letters, digits, - or _");
        }
        if (!url) throw new Error("url required");
        await invoke("provider_add_ollama", {
          profile: profile.name,
          name,
          url,
        });
        notify({
          message: `Ollama @${name} added`,
          variant: "success",
        });
      } else {
        const keyAlreadySet = configuredEnvs.has(provider.env);
        const trimmedKey = keyValue.trim();
        if (!keyAlreadySet && !trimmedKey) {
          throw new Error("API key required");
        }
        const trimmedModel = orModel.trim().replace(/^openrouter\//, "");
        if (isOpenRouter && !trimmedModel) {
          throw new Error("model required");
        }
        if (trimmedKey) {
          await invoke("provider_set_key", {
            profile: profile.name,
            key: provider.env,
            value: keyValue,
          });
        }
        if (isOpenRouter && trimmedModel) {
          await invoke("provider_add_openrouter_model", {
            profile: profile.name,
            model: trimmedModel,
          });
        }
        notify({
          message: isOpenRouter
            ? `OpenRouter ${trimmedModel} ready`
            : `${provider.label} key saved`,
          variant: "success",
        });
      }
      await onSaved?.();
      onClose?.();
    } catch (e) {
      notify({
        message: `add provider: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    } finally {
      setBusy(false);
    }
  }

  async function removePaid(env, label) {
    try {
      await invoke("provider_unset_key", {
        profile: profile.name,
        key: env,
      });
      notify({ message: `${label} key cleared`, variant: "success" });
      await onSaved?.();
    } catch (e) {
      notify({
        message: `clear: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    }
  }

  async function removeOllama(name) {
    try {
      await invoke("provider_remove_ollama", {
        profile: profile.name,
        name,
      });
      notify({ message: `Ollama @${name} removed`, variant: "success" });
      await onSaved?.();
    } catch (e) {
      notify({
        message: `remove: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    }
  }

  const hasAnyConfigured = configured.length > 0 || ollamas.length > 0;

  return (
    <>
      {hasAnyConfigured && (
        <div className={styles.tcpField}>
          <label className={styles.tcpLabel}>configured</label>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {PAID_PROVIDERS.filter((p) => configuredEnvs.has(p.env)).map(
              (p) => {
                const preview =
                  configured.find((k) => k.env === p.env)?.preview ?? "";
                return (
                  <span
                    key={p.env}
                    className={styles.inlineRow}
                    style={{ justifyContent: "space-between" }}
                  >
                    <span>
                      <strong>{p.label}</strong>{" "}
                      <span className={`${styles.muted} ${styles.mono}`}>
                        · {preview}
                      </span>
                    </span>
                    <ConfirmButton
                      size="sm"
                      label="Remove"
                      confirmLabel="Confirm"
                      onConfirm={() => removePaid(p.env, p.label)}
                    />
                  </span>
                );
              },
            )}
            {ollamas.map((o) => (
              <span
                key={o.name}
                className={styles.inlineRow}
                style={{ justifyContent: "space-between" }}
              >
                <span>
                  <strong>Ollama @{o.name}</strong>{" "}
                  <span className={styles.muted}>· {o.url}</span>
                </span>
                <ConfirmButton
                  size="sm"
                  label="Remove"
                  confirmLabel="Confirm"
                  onConfirm={() => removeOllama(o.name)}
                />
              </span>
            ))}
          </div>
        </div>
      )}

      <div className={styles.tcpField}>
        <label className={styles.tcpLabel}>add new</label>
        <span className={styles.inlineRow}>
          <Chip
            size="sm"
            state={pick === "ollama" ? "on" : "off"}
            onClick={() => setPick("ollama")}
            tooltip="local-first · run models on your own hardware"
          >
            Ollama
          </Chip>
          {PAID_PROVIDERS.map((p) => (
            <Chip
              key={p.id}
              size="sm"
              state={pick === p.id ? "on" : "off"}
              onClick={() => setPick(p.id)}
            >
              {p.label}
            </Chip>
          ))}
        </span>
      </div>

      {isOllama ? (
        <>
          <div className={styles.tcpField}>
            <label className={styles.tcpLabel}>name</label>
            <input
              className={styles.input}
              value={ollamaName}
              onChange={(e) => setOllamaName(e.target.value.toLowerCase())}
              placeholder="local · home-gpu · cloud-a"
              spellCheck={false}
              autoFocus
            />
          </div>
          <div className={styles.tcpField}>
            <label className={styles.tcpLabel}>url</label>
            <input
              className={styles.input}
              value={ollamaUrl}
              onChange={(e) => setOllamaUrl(e.target.value)}
              placeholder="http://localhost:11434"
              spellCheck={false}
            />
          </div>
        </>
      ) : (
        <>
          <div className={styles.tcpField}>
            <label className={styles.tcpLabel}>{provider.env}</label>
            <input
              className={styles.input}
              type="password"
              value={keyValue}
              onChange={(e) => setKeyValue(e.target.value)}
              placeholder={
                configuredEnvs.has(provider.env)
                  ? "(replace existing key)"
                  : "paste API key"
              }
              spellCheck={false}
              autoFocus
            />
          </div>
          {isOpenRouter && (
            <div className={styles.tcpField}>
              <label className={styles.tcpLabel}>model</label>
              <input
                className={styles.input}
                value={orModel}
                onChange={(e) => setOrModel(e.target.value)}
                placeholder="anthropic/claude-3.5-sonnet"
                spellCheck={false}
              />
              {savedOpenRouterModels.length > 0 && (
                <span
                  className={styles.inlineRow}
                  style={{ flexWrap: "wrap", marginTop: 6 }}
                >
                  {savedOpenRouterModels.map((m) => (
                    <Chip
                      key={m}
                      size="sm"
                      state={orModel === m ? "on" : "off"}
                      onClick={() => setOrModel(m)}
                    >
                      {m}
                    </Chip>
                  ))}
                </span>
              )}
            </div>
          )}
        </>
      )}

      <div className={styles.tcpActions}>
        <Button size="sm" onClick={onClose}>
          Close
        </Button>
        <Button
          size="sm"
          variant="primary"
          onClick={save}
          loading={busy}
        >
          Save
        </Button>
      </div>
    </>
  );
}

function ModelField({ profile, value, onChange }) {
  const [models, setModels] = useState([]);
  useEffect(() => {
    invoke("ollama_models", { profile: profile.name })
      .then((list) =>
        setModels([
          ...(profile.models ?? []),
          ...(Array.isArray(list) ? list : []),
        ]),
      )
      .catch(() => setModels(profile.models ?? []));
  }, [profile.name, profile.models]);

  const seen = new Set();
  const unique = models.filter((m) => (seen.has(m) ? false : seen.add(m)));
  const items = unique.includes(value) || !value ? unique : [value, ...unique];

  const groups = useMemo(() => {
    const m = new Map();
    for (const id of items) {
      const slash = id.indexOf("/");
      const provider = slash > 0 ? id.slice(0, slash) : "ollama";
      const label = slash > 0 ? id.slice(slash + 1) : id;
      if (!m.has(provider)) m.set(provider, []);
      m.get(provider).push({ id, label });
    }
    return m;
  }, [items]);

  return (
    <Dropdown
      trigger={{ label: value || "Select model…" }}
      direction="down"
      align="left"
      width={320}
      variant="outlined"
    >
      {({ close }) =>
        items.length === 0 ? (
          <Dropdown.Empty>No models available</Dropdown.Empty>
        ) : groups.size === 1 ? (
          items.map((m) => (
            <Dropdown.Row
              key={m}
              active={m === value}
              onClick={() => {
                onChange(m);
                close();
              }}
            >
              {m}
            </Dropdown.Row>
          ))
        ) : (
          [...groups.entries()].map(([provider, list]) => (
            <Dropdown.Group key={provider} label={provider}>
              {list.map(({ id, label }) => (
                <Dropdown.Row
                  key={id}
                  active={id === value}
                  onClick={() => {
                    onChange(id);
                    close();
                  }}
                >
                  {label}
                </Dropdown.Row>
              ))}
            </Dropdown.Group>
          ))
        )
      }
    </Dropdown>
  );
}

function PeersField({ profile, profiles, onSaved }) {
  const peers = profile.peers ?? [];
  const [statusById, setStatusById] = useState({});
  const [reasonById, setReasonById] = useState({});
  const [addOpen, setAddOpen] = useState(false);
  const [selectedPeerId, setSelectedPeerId] = useState(null);
  const [pending, setPending] = useState([]);
  const [pendingTick, setPendingTick] = useState(0);
  const wrapRef = useRef(null);
  const addAnchorRef = useRef(null);
  const detailAnchorRef = useRef(null);
  const notify = useNotify();

  useEffect(() => {
    let cancelled = false;
    invoke("peers_pending_list", { profile: profile.name })
      .then((rows) => !cancelled && setPending(Array.isArray(rows) ? rows : []))
      .catch(() => !cancelled && setPending([]));
    return () => {
      cancelled = true;
    };
  }, [profile.name, pendingTick, peers.length]);

  async function acceptPending(pubkey, suggestedId) {
    let id = (suggestedId || "").trim();
    if (!id) {
      const entered = window.prompt(
        `Pin this peer (pubkey ${pubkey.slice(0, 12)}…) under what id?`,
        "",
      );
      if (entered === null) return;  // cancelled
      id = (entered || "").trim();
      if (!id) {
        notify({ message: "id required to pin", variant: "error" });
        return;
      }
    }
    try {
      await invoke("peers_pending_accept", {
        profile: profile.name,
        peerId: id,
        pubkey,
      });
      notify({ message: `peer @${id} pinned`, variant: "success" });
      setPendingTick((t) => t + 1);
      await onSaved?.();
    } catch (e) {
      notify({
        message: `accept: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    }
  }

  async function discardPending(pubkey) {
    try {
      await invoke("peers_pending_discard", {
        profile: profile.name,
        pubkey,
      });
      setPendingTick((t) => t + 1);
    } catch (e) {
      notify({
        message: `discard: ${String(e)}`,
        variant: "error",
        duration: 3000,
      });
    }
  }

  useEffect(() => {
    if (peers.length === 0) return;
    let cancelled = false;
    invoke("probe_peers", {
      profile: profile.name,
      ids: peers.map((p) => p.id),
    })
      .then((results) => {
        if (cancelled) return;
        const sMap = {};
        const rMap = {};
        for (const r of results) {
          sMap[r.id] = r.status;
          if (r.reason) rMap[r.id] = r.reason;
        }
        setStatusById(sMap);
        setReasonById(rMap);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [profile.name, peers.length]);

  useEffect(() => {
    if (!addOpen && !selectedPeerId) return;
    function onClick(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        setAddOpen(false);
        setSelectedPeerId(null);
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [addOpen, selectedPeerId]);

  const onlineCount = Object.values(statusById).filter(
    (s) => s === "on",
  ).length;

  async function removePeer(peerId) {
    try {
      await invoke("peer_remove", { profile: profile.name, peerId });
      await onSaved?.();
      notify({
        message: `peer @${peerId} removed`,
        variant: "success",
        duration: 2500,
      });
    } catch (e) {
      notify({
        message: `peer remove: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    }
  }

  return (
    <span ref={wrapRef} className={styles.inlineRow}>
      {peers.length === 0 ? (
        <span className={styles.muted}>none</span>
      ) : (
        <span ref={detailAnchorRef} className={styles.tcpWrap}>
          <Dropdown
            trigger={{
              label:
                peers.length === 1
                  ? `1 peer · ${onlineCount} online`
                  : `${peers.length} peers · ${onlineCount} online`,
            }}
            direction="down"
            align="left"
            width={320}
            variant="outlined"
          >
            {({ close }) => (
              <>
                {peers.map((p) => {
                  const status = statusById[p.id] ?? "?";
                  const localProfile = profiles?.find(
                    (x) => x.name === p.id,
                  );
                  const accent =
                    localProfile?.accent || "var(--color-accent)";
                  return (
                    <Dropdown.Row
                      key={p.id}
                      onClick={() => {
                        close?.();
                        setSelectedPeerId(p.id);
                      }}
                      leading={
                        <span
                          className={styles.peerAccentDot}
                          style={{ backgroundColor: accent }}
                        />
                      }
                      caption={(p.pubkey || "").slice(0, 16) + "…"}
                      trailing={renderPeerStatusChip(
                        status,
                        reasonById[p.id],
                      )}
                    >
                      @{p.alias || p.id}
                    </Dropdown.Row>
                  );
                })}
              </>
            )}
          </Dropdown>
          {selectedPeerId && (
            <PeerDetailPopover
              peer={peers.find((p) => p.id === selectedPeerId)}
              status={statusById[selectedPeerId] ?? "?"}
              reason={reasonById[selectedPeerId]}
              anchorRef={detailAnchorRef}
              onClose={() => setSelectedPeerId(null)}
              onRemove={async () => {
                await removePeer(selectedPeerId);
                setSelectedPeerId(null);
              }}
            />
          )}
        </span>
      )}
      <span ref={addAnchorRef} className={styles.tcpWrap}>
        <Button size="sm" onClick={() => setAddOpen((o) => !o)}>
          + Add peer
        </Button>
        {addOpen && (
          <AddPeerPopover
            profile={profile}
            existingIds={peers.map((p) => p.id)}
            anchorRef={addAnchorRef}
            onClose={() => setAddOpen(false)}
            onAdded={onSaved}
          />
        )}
      </span>
      {pending.length > 0 && (
        <Dropdown
          trigger={{
            label:
              pending.length === 1
                ? "1 pending invite"
                : `${pending.length} pending invites`,
            variant: "warning",
          }}
          direction="down"
          align="left"
          width={360}
          variant="outlined"
        >
          {({ close }) =>
            pending.map((p) => (
              <Dropdown.Row
                key={p.pubkey}
                caption={
                  p.local_profile
                    ? `${(p.pubkey || "").slice(0, 16)}… · first seen ${new Date(
                        (p.first_seen ?? 0) * 1000,
                      ).toLocaleString()}`
                    : `first seen ${new Date(
                        (p.first_seen ?? 0) * 1000,
                      ).toLocaleString()}`
                }
                trailing={
                  <span style={{ display: "inline-flex", gap: 6 }}>
                    <Button
                      size="sm"
                      variant="primary"
                      onClick={(e) => {
                        e.stopPropagation();
                        acceptPending(p.pubkey, p.local_profile);
                        close?.();
                      }}
                    >
                      Accept
                    </Button>
                    <Button
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        discardPending(p.pubkey);
                      }}
                    >
                      Discard
                    </Button>
                  </span>
                }
              >
                {(p.pubkey || "").slice(0, 16)}…
              </Dropdown.Row>
            ))
          }
        </Dropdown>
      )}
    </span>
  );
}

function renderPeerStatusChip(status, reason) {
  if (status === "on") {
    return (
      <Chip size="sm" state="on" tooltip="link.ping ok — mutual pinning, service up">
        online
      </Chip>
    );
  }
  if (status === "unverified") {
    return (
      <Chip
        size="sm"
        state="warn"
        tooltip={
          reason
            ? `handshake failed — peer may not have us pinned, or our pubkey is wrong.\n\n${reason}`
            : "handshake failed — peer may not have us pinned, or our pubkey is wrong."
        }
      >
        unverified
      </Chip>
    );
  }
  if (status === "off") {
    return (
      <Chip
        size="sm"
        state="error"
        tooltip={reason ? `peer service unreachable.\n\n${reason}` : "peer service unreachable."}
      >
        offline
      </Chip>
    );
  }
  return null;
}

function isValidEd25519Pubkey(s) {
  if (!s) return false;
  if (!/^[A-Za-z0-9+/]+={0,2}$/.test(s)) return false;
  try {
    const raw = atob(s);
    return raw.length === 32;
  } catch {
    return false;
  }
}

const ALLOW_METHODS = [
  { id: "link.ping", desc: "health probe — `alpi peers ping`" },
  { id: "link.ask", desc: "one-shot turn — peer can mention this profile" },
  { id: "link.cancel", desc: "abort an in-flight turn started via link.ask" },
];

function BudgetEditor({ current, onSave }) {
  const [open, setOpen] = useState(false);
  const anchorRef = useRef(null);
  const popoverRef = useRef(null);
  const wrapRef = useRef(null);
  const [value, setValue] = useState(current != null ? String(current) : "");
  const [saving, setSaving] = useState(false);
  const pos = useAutoPosition({
    open,
    anchorRef,
    popoverRef,
    direction: "down",
    align: "left",
  });

  useEffect(() => {
    if (open) setValue(current != null ? String(current) : "");
  }, [open, current]);

  useEffect(() => {
    if (!open) return;
    function onClick(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  const trimmed = value.trim();
  const parsed = trimmed === "" ? null : Number(trimmed);
  const valid =
    trimmed === "" || (Number.isFinite(parsed) && parsed > 0);
  const dirty =
    valid && (parsed ?? null) !== (current ?? null);

  async function save() {
    if (!valid || !dirty || saving) return;
    setSaving(true);
    try {
      await onSave?.(parsed);
      setOpen(false);
    } catch {
    } finally {
      setSaving(false);
    }
  }

  return (
    <span ref={wrapRef} className={styles.tcpWrap}>
      <span ref={anchorRef}>
        <Button size="sm" onClick={() => setOpen((o) => !o)}>
          {current != null ? "Edit" : "Set cap"}
        </Button>
      </span>
      {open && (
        <div
          ref={popoverRef}
          className={styles.tcpPopover}
          style={{
            minWidth: 260,
            maxWidth: pos.maxWidth ?? undefined,
            position: "fixed",
            top: pos.top,
            left: pos.left,
            right: "auto",
            bottom: "auto",
            visibility: pos.ready ? "visible" : "hidden",
          }}
        >
          <div className={styles.tcpField}>
            <label className={styles.tcpLabel}>USD lifetime cap</label>
            <input
              className={styles.input}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="empty = unlimited"
              spellCheck={false}
              autoFocus
            />
          </div>
          {!valid && (
            <div className={styles.tcpWarn}>must be a positive number</div>
          )}
          <div className={styles.tcpActions}>
            <Button
              size="sm"
              variant="primary"
              onClick={save}
              disabled={!valid || !dirty}
              loading={saving}
            >
              Save
            </Button>
          </div>
        </div>
      )}
    </span>
  );
}

function PeerDetailPopover({
  peer,
  status,
  reason,
  anchorRef,
  onClose,
  onRemove,
}) {
  const popoverRef = useRef(null);
  const [removing, setRemoving] = useState(false);
  const pos = useAutoPosition({
    open: true,
    anchorRef,
    popoverRef,
    direction: "down",
    align: "left",
  });

  if (!peer) return null;

  return (
    <div
      ref={popoverRef}
      className={styles.tcpPopover}
      style={{
        minWidth: 320,
        maxWidth: pos.maxWidth ?? undefined,
        position: "fixed",
        top: pos.top,
        left: pos.left,
        right: "auto",
        bottom: "auto",
        visibility: pos.ready ? "visible" : "hidden",
      }}
    >
      <div className={styles.tcpField}>
        <label className={styles.tcpLabel}>peer</label>
        <span className={styles.peerRowName}>
          @{peer.alias || peer.id}
        </span>
      </div>
      <div className={styles.tcpField}>
        <label className={styles.tcpLabel}>status</label>
        <span>{renderPeerStatusChip(status, reason)}</span>
        {reason && status !== "on" && (
          <span className={styles.muted} style={{ marginTop: 4 }}>
            {reason}
          </span>
        )}
      </div>
      <div className={styles.tcpField}>
        <label className={styles.tcpLabel}>pubkey</label>
        <span className={styles.mono}>{peer.pubkey}</span>
      </div>
      {peer.address && (
        <div className={styles.tcpField}>
          <label className={styles.tcpLabel}>address</label>
          <span className={styles.mono}>{peer.address}</span>
        </div>
      )}
      <div className={styles.tcpField}>
        <label className={styles.tcpLabel}>allow</label>
        <span className={styles.inlineRow}>
          {(peer.allow ?? []).length === 0 ? (
            <span className={styles.muted}>none</span>
          ) : (
            (peer.allow ?? []).map((m) => (
              <Chip key={m} size="sm" state="on">
                {m}
              </Chip>
            ))
          )}
        </span>
      </div>
      <div className={styles.tcpActions}>
        <Button size="sm" onClick={onClose}>
          Close
        </Button>
        <ConfirmButton
          size="sm"
          label="Remove peer"
          confirmLabel="Confirm remove"
          loading={removing}
          onConfirm={async () => {
            setRemoving(true);
            try {
              await onRemove?.();
            } finally {
              setRemoving(false);
            }
          }}
        />
      </div>
    </div>
  );
}

function AddPeerPopover({
  profile,
  existingIds,
  anchorRef,
  onClose,
  onAdded,
}) {
  const notify = useNotify();
  const popoverRef = useRef(null);
  const [peerId, setPeerId] = useState("");
  const [pubkey, setPubkey] = useState("");
  const [address, setAddress] = useState("");
  const [alias, setAlias] = useState("");
  const [allow, setAllow] = useState([
    "link.ping",
    "link.ask",
    "link.cancel",
  ]);
  const [saving, setSaving] = useState(false);
  const pos = useAutoPosition({
    open: true,
    anchorRef,
    popoverRef,
    direction: "down",
    align: "left",
  });

  const idTrim = peerId.trim();
  const pubkeyTrim = pubkey.trim();
  const idDuplicate = existingIds.includes(idTrim);
  const idFormatValid = idTrim !== "" && /^[a-z0-9_-]+$/.test(idTrim);
  const pubkeyValid = isValidEd25519Pubkey(pubkeyTrim);
  const valid =
    idFormatValid && pubkeyTrim !== "" && pubkeyValid && !idDuplicate;

  function toggleAllow(id) {
    setAllow((curr) =>
      curr.includes(id) ? curr.filter((x) => x !== id) : [...curr, id],
    );
  }

  async function save() {
    if (!valid || saving) return;
    setSaving(true);
    try {
      await invoke("peer_add", {
        profile: profile.name,
        peerId: idTrim,
        pubkey: pubkeyTrim,
        address: address.trim() || null,
        alias: alias.trim() || null,
        allow: allow.join(","),
      });
      await onAdded?.();
      notify({
        message: `peer @${idTrim} pinned`,
        variant: "success",
        duration: 2500,
      });
      onClose?.();
    } catch (e) {
      notify({
        message: `peer add: ${String(e)}`,
        variant: "error",
        duration: 4000,
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      ref={popoverRef}
      className={styles.tcpPopover}
      style={{
        minWidth: 320,
        maxWidth: pos.maxWidth ?? undefined,
        position: "fixed",
        top: pos.top,
        left: pos.left,
        right: "auto",
        bottom: "auto",
        visibility: pos.ready ? "visible" : "hidden",
      }}
    >
      <div className={styles.tcpField}>
        <label className={styles.tcpLabel}>id</label>
        <input
          className={styles.input}
          value={peerId}
          onChange={(e) => setPeerId(e.target.value.toLowerCase())}
          placeholder="peer handle (a-z, 0-9, -, _)"
          spellCheck={false}
          autoFocus
        />
      </div>
      <div className={styles.tcpField}>
        <label className={styles.tcpLabel}>pubkey</label>
        <Textarea
          className={styles.textarea}
          rows={2}
          value={pubkey}
          onChange={(e) => setPubkey(e.target.value)}
          placeholder="base64 ed25519 pubkey"
          spellCheck={false}
        />
      </div>
      <div className={styles.tcpField}>
        <label className={styles.tcpLabel}>address (optional)</label>
        <input
          className={styles.input}
          value={address}
          onChange={(e) => setAddress(e.target.value)}
          placeholder="host:port — leave empty for intra-machine"
          spellCheck={false}
        />
      </div>
      <div className={styles.tcpField}>
        <label className={styles.tcpLabel}>alias (optional)</label>
        <input
          className={styles.input}
          value={alias}
          onChange={(e) => setAlias(e.target.value)}
          placeholder="display label"
          spellCheck={false}
        />
      </div>
      <div className={styles.tcpField}>
        <label className={styles.tcpLabel}>allow</label>
        <span className={styles.inlineRow}>
          {ALLOW_METHODS.map((m) => (
            <Chip
              key={m.id}
              size="sm"
              state={allow.includes(m.id) ? "on" : "off"}
              onClick={() => toggleAllow(m.id)}
              tooltip={m.desc}
            >
              {m.id}
            </Chip>
          ))}
        </span>
      </div>
      {idTrim !== "" && !idFormatValid && (
        <div className={styles.tcpWarn}>
          id can only contain a-z, 0-9, - and _.
        </div>
      )}
      {idDuplicate && (
        <div className={styles.tcpWarn}>
          @{idTrim} is already pinned.
        </div>
      )}
      {pubkeyTrim !== "" && !pubkeyValid && (
        <div className={styles.tcpWarn}>
          invalid pubkey — expected a base64 Ed25519 key (32 bytes / 44 chars).
        </div>
      )}
      <div className={styles.tcpActions}>
        <Button
          size="sm"
          variant="primary"
          onClick={save}
          disabled={!valid}
          loading={saving}
        >
          Add peer
        </Button>
      </div>
    </div>
  );
}

function WorkgroupsField({ profile, profiles, onSelectWorkgroup }) {
  const [groups, setGroups] = useState([]);
  useEffect(() => {
    invoke("workgroups", { profile: profile.name })
      .then(setGroups)
      .catch(() => setGroups([]));
  }, [profile.name]);

  if (groups.length === 0) {
    return <span className={styles.muted}>none</span>;
  }

  const hubCount = groups.filter((g) => g.is_hub).length;
  const countLabel =
    groups.length === 1 ? "1 workgroup" : `${groups.length} workgroups`;
  const hubLabel =
    hubCount === 0
      ? ""
      : ` · ${hubCount} ${hubCount === 1 ? "hub" : "hubs"}`;

  return (
    <Dropdown
      trigger={{ label: `${countLabel}${hubLabel}` }}
      direction="down"
      align="left"
      width={320}
      variant="outlined"
    >
      {({ close }) => (
        <>
          {groups.map((g) => {
            const hubAccent =
              profiles?.find((p) => p.name === (g.hub_id ?? profile.name))
                ?.accent || "var(--color-accent)";
            return (
              <Dropdown.Row
                key={g.id}
                onClick={() => {
                  onSelectWorkgroup?.(g.id);
                  close?.();
                }}
                caption={`${g.members} ${g.members === 1 ? "member" : "members"}`}
                trailing={
                  g.is_hub ? (
                    <Chip size="sm" accent={hubAccent}>
                      hub
                    </Chip>
                  ) : (
                    <Chip size="sm">member</Chip>
                  )
                }
              >
                #{g.name || g.id}
              </Dropdown.Row>
            );
          })}
        </>
      )}
    </Dropdown>
  );
}

function StorageField({ profile }) {
  const [items, setItems] = useState([]);
  useEffect(() => {
    invoke("profile_storage", { profile: profile.name })
      .then(setItems)
      .catch(() => setItems([]));
  }, [profile.name]);

  const visible = items.filter(
    (it) => it.size_bytes > 0 || it.file_count > 0,
  );

  if (visible.length === 0) {
    return (
      <Row label="size">
        <span className={styles.muted}>nothing yet</span>
      </Row>
    );
  }

  return (
    <>
      {visible.map((it) => (
        <Row key={it.key} label={it.label}>
          <span className={styles.inlineRow}>
            <Chip size="sm" tooltip={STORAGE_SCOPE[it.key]}>
              {formatBytes(it.size_bytes)}
            </Chip>
            <Chip size="sm">
              {it.file_count} {it.file_count === 1 ? "file" : "files"}
            </Chip>
            <Button
              size="sm"
              onClick={() =>
                invoke("reveal_in_finder", { path: it.path })
              }
            >
              Reveal
            </Button>
          </span>
        </Row>
      ))}
    </>
  );
}

const STORAGE_SCOPE = {
  sessions: "chat transcripts",
  audio: "TTS output + inbound voice notes",
  logs: "gateway, schedule, agent, approval",
  schedule: "stdout/stderr of past jobs",
  workgroups: "encrypted transcripts + turn telemetry",
};

function SkillsField({ profile }) {
  const [items, setItems] = useState([]);
  useEffect(() => {
    invoke("skills", { profile: profile.name })
      .then(setItems)
      .catch(() => setItems([]));
  }, [profile.name]);

  if (items.length === 0) {
    return (
      <Row label="installed">
        <span className={styles.muted}>none</span>
      </Row>
    );
  }

  const grouped = new Map();
  for (const s of items) {
    const cat = s.category ?? "—";
    if (!grouped.has(cat)) grouped.set(cat, []);
    grouped.get(cat).push(s.name);
  }

  return (
    <>
      {[...grouped.entries()].map(([category, names]) => (
        <Row key={category} label={category} alignTop>
          <span className={styles.gatewayChips}>
            {names.map((n) => {
              const skill = items.find(
                (s) => s.name === n && (s.category ?? "—") === category,
              );
              return (
                <Chip
                  key={n}
                  size="sm"
                  tooltip={skill?.description || undefined}
                >
                  {n}
                </Chip>
              );
            })}
          </span>
        </Row>
      ))}
    </>
  );
}

function Stat({ label, value }) {
  return (
    <div className={styles.stat}>
      <div className={styles.statValue}>{value}</div>
      <div className={styles.statLabel}>{label}</div>
    </div>
  );
}

function formatBytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  if (n < 1024 ** 3) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  return `${(n / 1024 ** 3).toFixed(2)} GB`;
}
