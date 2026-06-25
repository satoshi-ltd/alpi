import { useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import Button from "../../primitives/Button.jsx";
import Chip from "../../primitives/Chip.jsx";
import Textarea from "../../primitives/Textarea.jsx";
import { useNotify } from "../../primitives/Notification.jsx";
import { useProfileDetail } from "../../hooks/useProfileDetail.js";
import { useUsageDaily } from "../../hooks/useUsage.js";
import { Section, Row, CopyButton } from "./primitives.jsx";
import Usage from "./Usage.jsx";
import { SettingsHero } from "../../primitives/index.js";
import { CopyIcon, Mono } from "../../primitives/index.js";
import RefreshBar from "../../primitives/RefreshBar.jsx";
import { FIELD_KEYS } from "./util.js";
import { mergeProfileDraft } from "../../lib/profile-draft.js";
import {
  AccentField,
  BudgetField,
  SandboxField,
  WorkspaceField,
} from "./fields/boundaries.jsx";
import {
  AddProviderField,
  McpField,
  ModelField,
  ReasoningEffortField,
  VoiceField,
} from "./fields/agent.jsx";
import {
  PeersField,
  TcpPortField,
  WorkgroupsField,
} from "./fields/alp.jsx";
import {
  GatewaysCell,
  SchedulesSection,
  SubsystemsCell,
} from "./fields/services.jsx";
import { DevicesField } from "./fields/devices.jsx";
import { DaemonField } from "./fields/DaemonField.jsx";
import { NetworkAddressField, PairingNameField, HostPortField } from "./fields/network.jsx";
import {
  DeleteProfileAction,
  StorageField,
} from "./fields/maintenance.jsx";
import styles from "./Settings.module.css";
import { copyText } from "../../lib/clipboard.js";

function initialDraft(profile) {
  return {
    bio: profile.bio ?? "",
    workspace: profile.workspace ?? "",
    model: profile.model ?? "",
    accent: (profile.accent ?? "").toLowerCase(),
    reasoningEffort: profile.model_reasoning_effort ?? "",
  };
}

export default function ProfileDetail({
  profile: profileSummary,
  profiles,
  activeConnection,
  intent,
  onSaved,
  onDelete,
  onNavigate,
  onOpenChat,
}) {
  // Lazy heavy fields (peers/models/mcps/provider_keys/sandbox/voice/tcp_*) — scoped per connection so two daemons with the same profile name never share state.
  const { detail, loading: detailLoading, refresh } = useProfileDetail(
    activeConnection?.id ?? null,
    profileSummary?.name ?? null,
    { refreshOnMount: true },
  );
  const profile = useMemo(
    () => ({ ...profileSummary, ...(detail || {}) }),
    [profileSummary, detail],
  );
  const usage = useUsageDaily(
    profileSummary?.name ?? null,
    activeConnection?.id ?? null,
  );
  const baseline = useMemo(() => initialDraft(profile), [profile]);
  const [draft, setDraft] = useState(baseline);
  const [devicesLoading, setDevicesLoading] = useState(false);
  const [gatewaysLoading, setGatewaysLoading] = useState(false);
  const [schedulesLoading, setSchedulesLoading] = useState(false);
  const [modelLoading, setModelLoading] = useState(false);
  const [peersLoading, setPeersLoading] = useState(false);
  const [workgroupsLoading, setWorkgroupsLoading] = useState(false);
  const [storageLoading, setStorageLoading] = useState(false);
  const notify = useNotify();
  const timersRef = useRef({});
  const prevBaselineRef = useRef(baseline);
  const profileKey = `${profile.name}|${activeConnection?.id ?? ""}`;
  const prevProfileKeyRef = useRef(profileKey);

  useEffect(() => {
    setDraft((d) => mergeProfileDraft({
      draft: d,
      baseline,
      prevBaseline: prevBaselineRef.current,
      profileKey,
      prevProfileKey: prevProfileKeyRef.current,
    }));
    prevBaselineRef.current = baseline;
    prevProfileKeyRef.current = profileKey;
  }, [baseline, profileKey]);

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
      .then(() => { onSaved?.(); })
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

  function updateBio(value) {
    setDraft((d) => ({ ...d, bio: value }));
  }
  const bioDirty = draft.bio !== baseline.bio;
  function discardBio() {
    setDraft((d) => ({ ...d, bio: baseline.bio }));
  }
  function saveBio() {
    persist("bio", draft.bio);
  }

  const [drafting, setDrafting] = useState(false);
  async function draftIdentity() {
    setDrafting(true);
    try {
      const bio = await invoke("draft_identity", { profile: profile.name });
      update("bio", bio);
      notify({ message: "Identity drafted from AGENT.md", variant: "success", duration: 2500 });
    } catch (e) {
      notify({ message: String(e), variant: "error", duration: 4000 });
    } finally {
      setDrafting(false);
    }
  }

  const capUsd = profile.budget_daily_usd;
  const usedUsd = profile.budget_used_usd ?? 0;
  const heroMeta = (
    <>
      {profile.model && (
        <Mono className={styles.heroMetaValue}>{profile.model}</Mono>
      )}
      {capUsd != null && (
        <>
          <span aria-hidden className={styles.heroMetaSep} />
          <span>
            <span className={styles.heroMetaLabel}>budget </span>
            <Mono className={`tnum ${styles.heroMetaValue}`}>
              ${usedUsd.toFixed(2)}/${capUsd.toFixed(2)}
            </Mono>
          </span>
        </>
      )}
    </>
  );

  return (
    <main className={styles.detail}>
      <RefreshBar
        active={
          detailLoading || devicesLoading || gatewaysLoading || schedulesLoading
          || modelLoading || peersLoading || workgroupsLoading || storageLoading
          || usage.loading
        }
        accent={profile.accent || null}
        controlled
        label="Fetching latest settings"
      />
      <SettingsHero
        kind="profile"
        id={profile.name}
        accent={profile.accent || "var(--accent)"}
        bio={profile.bio || profile.public_bio}
        meta={heroMeta}
        onOpenChat={onOpenChat ? () => onOpenChat(profile) : undefined}
      />
      <div className={styles.body}>
        <Section title="Overview">
          <Row label="home">
            <span className={styles.inlineRow}>
              <span className={styles.mono}>{profile.home}</span>
              {activeConnection?.kind === "local" && (
                <Button
                  size="sm"
                  onClick={() => invoke("reveal_in_finder", { path: profile.home })}
                >
                  Reveal
                </Button>
              )}
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
                  onLoadingChange={setModelLoading}
                />
              ) : (
                <span className={styles.muted}>
                  no models — add a provider first
                </span>
              )}
              <AddProviderField profile={profile} onSaved={onSaved} />
            </span>
          </Row>
          {profile.model_reasoning_supported && (
            <Row label="reasoning">
              <ReasoningEffortField
                value={draft.reasoningEffort}
                onChange={(v) => update("reasoningEffort", v)}
              />
            </Row>
          )}
          <BudgetField profile={profile} onSaved={onSaved} />
          <Row label="workspace">
            <WorkspaceField
              value={draft.workspace}
              onChange={(v) => update("workspace", v)}
              isLocal={activeConnection?.kind === "local"}
            />
          </Row>
          <Row label="accent">
            <AccentField
              value={draft.accent}
              onChange={(v) => update("accent", v)}
            />
          </Row>
        </Section>

        {usage.days.length > 0 && (
          <Section title="Usage" kicker="last 14 days">
            <Usage
              days={usage.days}
              accent={profile.accent || "var(--accent)"}
              capLine={capUsd}
            />
          </Section>
        )}

        <Section title="Service" tooltip="always-on subsystems">
          {(activeConnection?.kind === "local" || activeConnection?.role === "admin") && (
            <Row label="daemon">
              <DaemonField />
            </Row>
          )}
          {activeConnection?.kind === "local" && <NetworkAddressField />}
          <Row label="subsystems">
            <SubsystemsCell profile={profile} onSaved={onSaved} />
          </Row>
          <Row label="gateways">
            <GatewaysCell
              profile={profile}
              connectionId={activeConnection?.id ?? null}
              onLoadingChange={setGatewaysLoading}
            />
          </Row>
        </Section>

        <Section title="ALP" tooltip="peers + workgroups">
          {profile.pubkey_b64 && (
            <Row label="pubkey">
              <span className={styles.inlineRow}>
                <code className={`${styles.codeChip} ${styles.truncate}`}>
                  {profile.pubkey_b64}
                </code>
                <button
                  type="button"
                  className={`alink ${styles.copyBtn}`}
                  onClick={async () => {
                    if (await copyText(profile.pubkey_b64)) {
                      notify({ message: "Pubkey copied", variant: "success" });
                    } else {
                      notify({
                        message: "Copy failed",
                        variant: "error",
                      });
                    }
                  }}
                >
                  <CopyIcon style={{ width: 12, height: 12 }} />{" "}
                  Copy
                </button>
              </span>
            </Row>
          )}
          <Row label="identity" alignTop>
            <div className={`${styles.briefingWrap} ${styles.identityBlock}`}>
              <Textarea
                className={styles.textarea}
                rows={3}
                value={draft.bio}
                onChange={(e) => updateBio(e.target.value)}
                placeholder="public identity — visible to peers"
              />
              {bioDirty && (
                <div className={styles.draftRow}>
                  <span className={styles.draftTag}>draft</span>
                  <button
                    type="button"
                    className="alink"
                    onClick={discardBio}
                  >
                    Discard
                  </button>
                  <button
                    type="button"
                    className="alink"
                    onClick={saveBio}
                  >
                    Save
                  </button>
                  <span style={{ flex: 1 }} />
                  <Button
                    size="sm"
                    onClick={draftIdentity}
                    loading={drafting}
                    disabled={drafting || !profile.model}
                    title={
                      !profile.model
                        ? "Set a model first to draft"
                        : "Synthesize a one-liner from AGENT.md (one LLM call)"
                    }
                  >
                    Draft
                  </Button>
                </div>
              )}
            </div>
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
              onRefresh={refresh}
              onLoadingChange={setPeersLoading}
            />
          </Row>
          <Row label="workgroups">
            <WorkgroupsField
              profile={profile}
              profiles={profiles}
              onSelectWorkgroup={(id) =>
                onNavigate?.({ kind: "workgroup", id })
              }
              onLoadingChange={setWorkgroupsLoading}
            />
          </Row>
        </Section>

        {profile.name === "default" && (activeConnection?.kind === "local" || activeConnection?.role === "admin") && (
          <Section title="Devices" tooltip="paired apps">
            {activeConnection?.kind === "local" && <PairingNameField />}
            {activeConnection?.kind === "local" && <HostPortField profile={profile} onSaved={onSaved} />}
            <DevicesField
              connectionId={activeConnection?.id ?? null}
              role={activeConnection?.role ?? null}
              onLoadingChange={setDevicesLoading}
            />
          </Section>
        )}

        <SchedulesSection
          profile={profile}
          connectionId={activeConnection?.id ?? null}
          onLoadingChange={setSchedulesLoading}
        />

        <Section
          title="Sandbox"
          tooltip="isolate shell commands"
        >
          <SandboxField profile={profile} onSaved={onSaved} />
        </Section>

        <Section title="Voice" tooltip="text-to-speech voice">
          <VoiceField profile={profile} onSaved={onSaved} />
        </Section>

        <Section title="MCP Servers" tooltip="external tool servers">
          <McpField profile={profile} onSaved={onSaved} />
        </Section>

        <Section title="Storage" tooltip="disk + data usage">
          <StorageField
            profile={profile}
            activeConnection={activeConnection}
            onLoadingChange={setStorageLoading}
          />
        </Section>

        {profile.name !== "default"
          && (activeConnection?.kind === "local" || activeConnection?.role === "admin") && (
          <Section title="Danger Zone">
            <Row label="delete">
              <DeleteProfileAction
                profile={profile}
                onDelete={onDelete}
                autoConfirm={intent === "delete"}
                onConsumed={() => onNavigate?.({ kind: "profile", id: profile.name })}
              />
            </Row>
          </Section>
        )}
      </div>
    </main>
  );
}
