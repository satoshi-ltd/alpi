import { useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import Button from "../../primitives/Button.jsx";
import ActionLink from "../../primitives/ActionLink.jsx";
import Chip from "../../primitives/Chip.jsx";
import Textarea from "../../primitives/Textarea.jsx";
import { Reveal } from "../../primitives/Skeleton.jsx";
import UsageSkeleton from "../../primitives/UsageSkeleton.jsx";
import { useSkeletonPhase } from "../../hooks/useSkeleton.js";
import { useNotify } from "../../primitives/Notification.jsx";
import { useProfileDetail } from "../../hooks/useProfileDetail.js";
import { useProfileSnapshot } from "../../hooks/useProfileSnapshot.js";
import { useUsageDaily } from "../../hooks/useUsage.js";
import { Section, Row, CopyButton } from "./primitives.jsx";
import Usage from "./Usage.jsx";
import SettingsNav from "./SettingsNav.jsx";
import {
  AppearancePicker,
  CopyIcon,
  Fold,
  SettingsHero,
} from "../../primitives/index.js";
import { TWIN } from "../../lib/brandMark.js";
import { profileLabel } from "../../lib/profile-display.js";
import { ProfileDetails, profileBudget } from "../../primitives/HeaderDetails.jsx";
import RefreshBar from "../../primitives/RefreshBar.jsx";
import { FIELD_KEYS, providerPills } from "./util.js";
import { mergeProfileDraft } from "../../lib/profile-draft.js";
import {
  BudgetField,
  SandboxField,
  WorkspaceField,
} from "./fields/boundaries.jsx";
import {
  AddProviderField,
  FallbackModelsField,
  McpField,
  ModelField,
  ReasoningEffortField,
  TierField,
  VisionModelField,
  VoiceField,
} from "./fields/agent.jsx";
import {
  PeersField,
  PipelineLimitField,
  TcpPortField,
  WorkgroupsField,
} from "./fields/alp.jsx";
import { EmailCell } from "./fields/services.jsx";
import { DaemonField } from "./fields/DaemonField.jsx";
import { ThemeField } from "./fields/ThemeField.jsx";
import { canSelfUpdate } from "../../../../common/updateHint.mjs";
import { fallbackList, hasFallbackModels } from "../../../../common/fallbackModels.mjs";
import {
  NetworkAddressField,
  PairingNameField,
  PrivateRouteField,
  PublicRouteField,
} from "./fields/network.jsx";
import LazyMount from "../../primitives/LazyMount.jsx";
import {
  DeleteProfileAction,
  StorageField,
  _clearStorageCache as _clearStorageCacheSafe,
} from "./fields/maintenance.jsx";
import styles from "./Settings.module.css";
import { copyText } from "../../lib/clipboard.js";
import { useSettingsDirty } from "../../lib/settingsDirty.js";
import { emptyLine } from "../../../../common/emptyCopy.mjs";
import { profileShape } from "../../../../common/shapes.mjs";
import { applyEdits, saveOptimistic, useProfileEdits } from "../../lib/optimisticProfiles.js";

// storage stays out: its os.walk dominates snapshot latency, so StorageField fetches it independently.
const SNAPSHOT_SECTIONS = ["detail", "usage", "workgroups", "email"];

const CHOICE_PATHS = {
  model: "model",
  accent: "accent",
  shape: "shape",
  reasoningEffort: "model_reasoning_effort",
};

function initialDraft(profile) {
  return {
    bio: profile.bio ?? "",
    workspace: profile.workspace ?? "",
    model: profile.model ?? "",
    accent: (profile.accent ?? "").toLowerCase(),
    shape: profileShape(profile),
    reasoningEffort: profile.model_reasoning_effort ?? "",
  };
}

export default function ProfileDetail({
  profile: profileSummary,
  profiles,
  activeConnection,
  connectionSyncing = false,
  intent,
  onSaved,
  onDelete,
  onNavigate,
  onOpenChat,
  onOpenConnections,
  refreshTick = 0,
}) {
  const connId = activeConnection?.id ?? null;
  const name = profileSummary?.name ?? null;
  // One round-trip feeds every section; per-section fetches stay DEFERRED until the snapshot settles, and only fire as fallback when it errors (old daemon, offline).
  const snap = useProfileSnapshot(connId, name, { sections: SNAPSHOT_SECTIONS });
  const sn = snap.snapshot;
  const snapPending = !sn && !snap.error;
  const sectionData = (s) => (s && !s.error ? s : undefined);
  const detailPre = sectionData(sn?.detail);
  const usagePre = sectionData(sn?.usage);
  const workgroupsPre = sectionData(sn?.workgroups)?.workgroups;
  const emailPre = sectionData(sn?.email)?.accounts;
  const storagePre = sectionData(sn?.storage)?.storage;

  const { detail, loading: detailLoading, refresh } = useProfileDetail(
    connId, name, { refreshOnMount: true, prefetched: detailPre, defer: snapPending },
  );
  const refreshDetail = detailPre !== undefined ? snap.refresh : refresh;
  const editsVersion = useProfileEdits();
  const profile = useMemo(
    () => applyEdits({
      ...profileSummary,
      ...(detail || {}),
      ...(profileSummary?.model_reasoning_effort !== undefined
        ? { model_reasoning_effort: profileSummary.model_reasoning_effort }
        : {}),
    }, connId),
    [profileSummary, detail, connId, editsVersion],
  );
  const usage = useUsageDaily(name, connId, usagePre, snapPending);
  const { show: showUsageSkeleton, revealed: usageRevealed } = useSkeletonPhase(usage.loading && usage.days.length === 0);

  const snapRefresh = snap.refresh;
  const lastRefreshTickRef = useRef(refreshTick);
  useEffect(() => {
    if (refreshTick === lastRefreshTickRef.current) return;
    lastRefreshTickRef.current = refreshTick;
    snapRefresh();
  }, [refreshTick, snapRefresh]);
  const baseline = useMemo(() => initialDraft(profile), [profile]);
  const [draft, setDraft] = useState(baseline);
  const [emailLoading, setEmailLoading] = useState(false);
  const [modelLoading, setModelLoading] = useState(false);
  const [ollamaErrors, setOllamaErrors] = useState([]);

  const [workgroupsLoading, setWorkgroupsLoading] = useState(false);
  const [workgroupCount, setWorkgroupCount] = useState(workgroupsPre?.length ?? 0);
  useEffect(() => {
    if (workgroupsPre !== undefined) setWorkgroupCount(workgroupsPre.length);
  }, [workgroupsPre]);

  const notify = useNotify();
  const bodyRef = useRef(null);
  const timersRef = useRef({});
  const pendingRef = useRef({});
  const prevBaselineRef = useRef(baseline);
  const profileKey = `${profile.name}|${activeConnection?.id ?? ""}`;
  const prevProfileKeyRef = useRef(profileKey);

  useEffect(() => {
    const prevBaseline = prevBaselineRef.current;
    const prevProfileKey = prevProfileKeyRef.current;
    setDraft((d) => mergeProfileDraft({ draft: d, baseline, prevBaseline, profileKey, prevProfileKey }));
    prevBaselineRef.current = baseline;
    prevProfileKeyRef.current = profileKey;
  }, [baseline, profileKey]);

  const flushRef = useRef(null);
  flushRef.current = () => {
    const timers = timersRef.current;
    for (const [field, t] of Object.entries(timers)) {
      clearTimeout(t);
      if (field in pendingRef.current) persist(field, pendingRef.current[field].value, pendingRef.current[field].connId);
    }
    timersRef.current = {};
    pendingRef.current = {};
  };
  useEffect(() => () => flushRef.current?.(), []);

  function persist(field, value, connectionId = connId) {
    invoke("set_config_field", {
      profile: profile.name,
      key: FIELD_KEYS[field],
      value,
      connectionId,
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

  function fail(field) {
    return (e) => notify({ message: `${field}: ${String(e)}`, variant: "error", duration: 4000 });
  }

  function choose(field, value) {
    setDraft((d) => ({ ...d, [field]: value }));
    clearTimeout(timersRef.current[field]);
    delete timersRef.current[field];
    delete pendingRef.current[field];
    const path = CHOICE_PATHS[field];
    const detailField = path === "model_reasoning_effort";
    saveOptimistic({
      connectionId: connId,
      name: profile.name,
      patch: { [path]: value },
      run: () => invoke("set_config_field", {
        profile: profile.name,
        key: FIELD_KEYS[field],
        value,
        connectionId: connId,
      }),
      onFailed: fail(field),
      refresh: () => Promise.all([detailField ? refreshDetail() : null, onSaved?.()]),
    }).then(({ latest }) => {
      if (!latest) return;
      onSaved?.();
      if (detailField) refreshDetail();
    }, () => {});
  }

  function update(field, value) {
    setDraft((d) => ({ ...d, [field]: value }));
    const timers = timersRef.current;
    if (timers[field]) clearTimeout(timers[field]);
    const editedOn = connId;
    pendingRef.current[field] = { value, connId: editedOn };
    timers[field] = setTimeout(() => {
      delete timers[field];
      delete pendingRef.current[field];
      persist(field, value, editedOn);
    }, 600);
  }

  function updateBio(value) {
    setDraft((d) => ({ ...d, bio: value }));
  }
  const bioDirty = draft.bio !== baseline.bio;
  useSettingsDirty(`profile:${profileKey}:bio`, bioDirty);
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
  const accent = profile.accent || "var(--accent)";
  const providers = providerPills(profile, ollamaErrors);
  const hasModels =
    (profile.models?.length ?? 0) > 0 || (profile.provider_ollama?.length ?? 0) > 0;
  const heroMeta = <ProfileDetails model={profile.model} budget={profileBudget(profile)} accent={accent} />;
  // Lazy sections (storage, peers, network) keep their loading local — the header bar covers only above-the-fold data.
  const syncing = (
    detailLoading || emailLoading
    || modelLoading || workgroupsLoading
    || usage.loading || snap.loading || connectionSyncing
  );

  return (
    <main className={styles.detail}>
      <SettingsHero
        kind="profile"
        id={profileLabel(profile.name)}
        accent={accent}
        shape={profile.shape}
        bio={profile.bio || profile.public_bio}
        meta={heroMeta}
        paused={!!profile.paused}
        onOpenChat={onOpenChat ? () => onOpenChat(profile) : undefined}
        onOpenConnections={onOpenConnections}
      />
      <div className={styles.syncBarSlot}>
        <RefreshBar
          active={syncing}
          controlled
          label="Fetching latest settings"
          color={profile.accent || null}
        />
      </div>
      <div ref={bodyRef} className={styles.body}>
        <SettingsNav scrollRef={bodyRef}>
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
          <Row label="providers">
            <span className={styles.inlineRow}>
              {providers.length > 0 ? (
                providers.map((p) => (
                  <Chip
                    key={p.label}
                    state={p.error ? "error" : "on"}
                    tooltip={p.error ?? undefined}
                  >
                    {p.label}
                  </Chip>
                ))
              ) : (
                <span className={styles.muted}>{emptyLine("providers")}</span>
              )}
              <AddProviderField profile={profile} onSaved={onSaved} />
            </span>
          </Row>
          <Row label="model">
            <span className={styles.inlineRow}>
              {hasModels ? (
                <ModelField
                  profile={profile}
                  value={draft.model}
                  onChange={(v) => choose("model", v)}
                  onLoadingChange={setModelLoading}
                  onOllamaErrors={setOllamaErrors}
                />
              ) : (
                <span className={styles.muted}>{emptyLine("models")}</span>
              )}
              {profile.model_reasoning_supported && (
                <ReasoningEffortField
                  value={draft.reasoningEffort}
                  onChange={(v) => choose("reasoningEffort", v)}
                />
              )}
            </span>
          </Row>
          {/* profile.tiers missing = daemon predates routing tiers — hide the rows instead of rendering pickers that can't read state back. */}
          {profile.tiers && hasModels && (
            <>
              <Row label="fast model">
                <TierField
                  profile={profile}
                  name="fast"
                  connectionId={connId}
                  onSaved={() => { const landed = refreshDetail(); onSaved?.(); return landed; }}
                />
              </Row>
              <Row label="deep model">
                <TierField
                  profile={profile}
                  name="deep"
                  connectionId={connId}
                  onSaved={() => { const landed = refreshDetail(); onSaved?.(); return landed; }}
                />
              </Row>
            </>
          )}
          {profile.vision_model !== undefined && (hasModels || profile.vision_model) && (
            <Row label="vision model">
              <VisionModelField
                profile={profile}
                connectionId={connId}
                onSaved={() => { const landed = refreshDetail(); onSaved?.(); return landed; }}
              />
            </Row>
          )}
          {hasFallbackModels(profile) && (hasModels || fallbackList(profile).length > 0) && (
            <Row label="fallbacks" keywords="fallback models outage provider" alignTop>
              <FallbackModelsField
                profile={profile}
                onSaved={() => { const landed = refreshDetail(); onSaved?.(); return landed; }}
              />
            </Row>
          )}
          <BudgetField profile={profile} connectionId={connId} onSaved={onSaved} />
          <Row label="workspace">
            <WorkspaceField
              value={draft.workspace}
              onChange={(v) => update("workspace", v)}
              isLocal={activeConnection?.kind === "local"}
            />
          </Row>
          <Row label="appearance" keywords="accent colour color shape mark">
            {profile.name === "default" ? (
              <span className={styles.lockedAppearance}>
                <Fold shape={TWIN} color={accent} size={28} />
                <span>Twin · brand mark</span>
              </span>
            ) : (
              <AppearancePicker
                shape={draft.shape}
                accent={draft.accent}
                onChange={(patch, { typed = false } = {}) => Object.entries(patch).forEach(([field, value]) => (typed ? update : choose)(field, value))}
              />
            )}
          </Row>
          {profile.name === "default" && (
            <Row label="theme" keywords="light dark system appearance mode">
              <ThemeField />
            </Row>
          )}
        </Section>

        {(usage.loading || showUsageSkeleton || usage.days.length > 0) && (
          <Section title="Usage" kicker="last 14 days">
            {showUsageSkeleton ? (
              <UsageSkeleton />
            ) : usage.days.length > 0 ? (
              <Reveal animate={usageRevealed}>
                <Usage
                  days={usage.days}
                  accent={profile.accent || "var(--accent)"}
                  capLine={capUsd}
                  total30={usage.total30}
                />
              </Reveal>
            ) : null}
          </Section>
        )}

        {(activeConnection?.kind === "local" || activeConnection?.role === "admin") && (
          <Section title="Service" tooltip="daemon + network">
            <Row label="daemon">
              <DaemonField connectionId={activeConnection.id} selfUpdate={canSelfUpdate(activeConnection.self_update)} />
            </Row>
            {profile.name === "default" && activeConnection?.kind === "local" && (
              <>
                <LazyMount>
                  <NetworkAddressField profile={profile} onSaved={onSaved} />
                </LazyMount>
                <PairingNameField />
                <PrivateRouteField />
                <PublicRouteField />
              </>
            )}
          </Section>
        )}

        <Section title="ALP" tooltip="peers + workgroups">
          {profile.pubkey_b64 && (
            <Row label="pubkey">
              <span className={styles.inlineRow}>
                <code className={`${styles.codeChip} ${styles.truncate}`}>
                  {profile.pubkey_b64}
                </code>
                <ActionLink
                  className={styles.copyBtn}
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
                  <CopyIcon size="sm" />{" "}
                  Copy
                </ActionLink>
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
                  <ActionLink
                    onClick={discardBio}
                  >
                    Discard
                  </ActionLink>
                  <ActionLink
                    onClick={saveBio}
                  >
                    Save
                  </ActionLink>
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
            <LazyMount>
              <PeersField
                profile={profile}
                profiles={profiles}
                onSaved={onSaved}
                onRefresh={refreshDetail}
              />
            </LazyMount>
          </Row>
          <Row label="workgroups" hidden={!workgroupsLoading && workgroupCount === 0}>
            <WorkgroupsField
              profile={profile}
              profiles={profiles}
              connectionId={activeConnection?.id ?? null}
              prefetched={workgroupsPre}
              defer={snapPending}
              onSelectWorkgroup={(id) =>
                onNavigate?.({ kind: "workgroup", id })
              }
              onLoadingChange={setWorkgroupsLoading}
              onCountChange={setWorkgroupCount}
            />
          </Row>
          {profile.max_active_workgroups !== undefined && (
            <Row label="concurrency">
              <PipelineLimitField profile={profile} onSaved={onSaved} />
            </Row>
          )}
        </Section>

        <Section
          title="Sandbox"
          tooltip="isolate shell commands"
        >
          <SandboxField profile={profile} onSaved={onSaved} />
        </Section>

        <Section title="Voice" tooltip="text-to-speech voice">
          <VoiceField profile={profile} onSaved={onSaved} />
        </Section>

        <Section title="MCP servers" tooltip="external tool servers">
          <McpField profile={profile} connectionId={activeConnection?.id ?? null} onSaved={onSaved} />
        </Section>

        <Section title="Email" tooltip="IMAP + Gmail accounts">
          <Row label="accounts">
            <EmailCell
              profile={profile}
              connectionId={activeConnection?.id ?? null}
              prefetched={emailPre}
              defer={snapPending}
              onSnapshotRefresh={snap.refresh}
              onLoadingChange={setEmailLoading}
            />
          </Row>
        </Section>

        <Section title="Storage" tooltip="disk + data usage">
          <LazyMount>
            <StorageField
              profile={profile}
              activeConnection={activeConnection}
              prefetched={storagePre}
              onCleaned={() => { _clearStorageCacheSafe(); onSaved?.(); }}
            />
          </LazyMount>
        </Section>

        {profile.name !== "default"
          && (activeConnection?.kind === "local" || activeConnection?.role === "admin") && (
          <Section title="Danger zone">
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
        </SettingsNav>
      </div>
    </main>
  );
}
