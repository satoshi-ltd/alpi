import { useLocalSearchParams, useRouter } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { RefreshControl, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { space } from '../../../src/theme/tokens';

import { pairName } from '../../../../common/accents.mjs';
import { FALLBACK_ACCENT } from '../../../../common/folds.mjs';
import { toUsageDays } from '../../../../common/usage.mjs';
import { attentionHelper, attentionLabel, flagCount } from '../../../../common/attention.mjs';
import { AttentionValue } from '../../../src/components/AttentionPill';
import { useAttention } from '../../../src/hooks/useAttention';
import { Button } from '../../../src/components/Button';
import { Fold } from '../../../src/components/Fold';
import { Meter } from '../../../src/components/Meter';
import { Eyebrow } from '../../../src/components/Eyebrow';
import { Toggle } from '../../../src/components/Toggle';
import { Pill } from '../../../src/components/Pill';
import { Row, RowGroup, RowSeparator, SectionHeader, SettingsBand } from '../../../src/components/Row';
import { ScreenHeader } from '../../../src/components/ScreenHeader';
import { SettingsSkeleton } from '../../../src/components/SettingsSkeleton';
import { SyncBar } from '../../../src/components/SyncBar';
import { TextPrompt } from '../../../src/components/TextPrompt';
import { UsageChart } from '../../../src/components/UsageChart';
import { useBack } from '../../../src/hooks/useBack';
import { usePullRefresh } from '../../../src/hooks/usePullRefresh';
import { modelLabel } from '../../../src/lib/modelLabel';
import { profileLabel } from '../../../src/lib/profileName';
import { copyText } from '../../../src/lib/clipboard';
import { useToast } from '../../../src/components/Toast';
import { Bold, Code, TypedConfirm } from '../../../src/components/TypedConfirm';
import { updateOutcome } from '../../../src/features/settings/daemonUpdate';
import { canSelfUpdate, updateHint } from '../../../../common/updateHint.mjs';
import { IdentityEditor } from '../../../src/features/settings/IdentityEditor';
import {
  useEmailAccounts,
  useProfileStorage,
  useProfileSnapshot,
  useScheduleList,
} from '../../../src/hooks/useDaemonData';
import { useProfile } from '../../../src/hooks/useSubject';
import { useEndpoint } from '../../../src/lib/EndpointContext';
import { AppearanceSheet } from '../../../src/features/sheets/AppearanceSheet';
import {
  BudgetSheet,
  CleanupSheet,
  ModelSheet,
  ReasoningEffortSheet,
  VoiceSheet,
  WorkspaceSheet,
} from '../../../src/features/sheets/ProfileFieldSheets';
import { usePane } from '../../../src/nav/PaneContext';
import { SettingsSurface } from '../../../src/nav/SettingsSurface';
import { AttentionSummary, JumpChips } from '../../../src/features/settings/SectionJump';
import { useSectionJump } from '../../../src/features/settings/useSectionJump';
import { useTheme } from '../../../src/theme/ThemeContext';
import { voiceLabel } from '../../../src/lib/voices';
import { EMPTY } from '../../../../common/emptyCopy.mjs';
import { SubtitleSkeleton } from '../../../src/components/SubtitleSkeleton';
import { UsageSkeleton } from '../../../src/components/UsageSkeleton';
import { ListSkeleton } from '../../../src/components/ListSkeleton';

const DEFAULT_ALP_PORT = 7423;
const WIDE_BODY_MAX_W = 968;
const WIDE_LABEL_W = 96;

function ChipRow({ items }) {
  return (
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'flex-end', gap: space.s2 }}>
      {items.map((it) => (
        <Pill key={it}>{it}</Pill>
      ))}
    </View>
  );
}

function formatBytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  if (n < 1024 ** 3) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  return `${(n / 1024 ** 3).toFixed(2)} GB`;
}

function tierValue(tier) {
  if (!tier?.model) return 'main model';
  return modelLabel(tier.model);
}

function sectionData(section) {
  return section && !section.error ? section : null;
}

function needsFallback(snapshot, name) {
  if (snapshot.unsupported) return true;
  if (!snapshot.data) return false;
  return !sectionData(snapshot.data?.[name]);
}

export function providerLabels(profile) {
  const cloud = (profile?.provider_keys ?? []).map((k) =>
    String(k?.env ?? k ?? '').replace(/_API_KEY$/, '').toLowerCase(),
  );
  const ollama = (profile?.provider_ollama ?? []).map((o) => `ollama/${o.name}`);
  return [...cloud, ...ollama].filter(Boolean);
}

export function pipelineLimitLabel(limit) {
  const n = Number(limit);
  if (!Number.isFinite(n) || n <= 0) return 'unlimited';
  return `${n} pipeline${n === 1 ? '' : 's'}`;
}

export function shortPubkey(pk) {
  if (!pk) return '—';
  return pk.length <= 14 ? pk : `${pk.slice(0, 8)}…${pk.slice(-4)}`;
}

export default function ProfileSettings() {
  const { id, intent } = useLocalSearchParams();
  const router = useRouter();
  const goBack = useBack();
  const toast = useToast();
  const { call, endpoint, installState, updateState } = useEndpoint();
  const install = installState?.get(endpoint?.id);
  const selfUpdate = canSelfUpdate(install?.selfUpdate);
  const updateAvailable = updateState?.get(endpoint?.id);
  const manualStep = !selfUpdate && updateAvailable ? updateHint(install?.installer, updateAvailable) : null;
  const { colors, fonts, fontSizes } = useTheme();
  const { twoPane } = usePane();
  const snap = useProfileSnapshot(id);
  const detailPre = sectionData(snap.data?.detail);
  const { profile: baseProfile, loading, refresh, refreshDetail } = useProfile(id, { skipDetail: !snap.unsupported });
  const profile = detailPre ? { ...(baseProfile || {}), ...detailPre } : baseProfile;
  const emailAccounts = useEmailAccounts(id, { skipWhen: !needsFallback(snap, 'email') });
  const schedule = useScheduleList(id, { skipWhen: !needsFallback(snap, 'schedules') });
  const { att } = useAttention(id);
  const { scrollRef, anchor, jump, section, onScroll } = useSectionJump();
  const storage = useProfileStorage(id, { skipWhen: !needsFallback(snap, 'storage') });
  const [sheet, setSheet] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [restartBusy, setRestartBusy] = useState(false);
  const [confirmRestart, setConfirmRestart] = useState(false);
  const [confirmUpdate, setConfirmUpdate] = useState(false);
  const [updateBusy, setUpdateBusy] = useState(false);

  useEffect(() => {
    if (intent === 'delete') setConfirmDelete(true);
    if (intent === 'model') setSheet('model');
  }, [intent]);

  const loadSettings = useCallback(async () => {
    let failure = null;
    try {
      await refresh();
    } catch (e) {
      failure = e;
    }
    const next = await snap.refresh().catch(() => null);
    if (!next && snap.unsupported) await refreshDetail();
    if (failure) throw failure;
  }, [refresh, snap.refresh, snap.unsupported, refreshDetail]);
  const refreshSettings = useCallback(() => loadSettings().catch(() => {}), [loadSettings]);
  const pull = usePullRefresh(loadSettings);

  const handleRestart = async () => {
    setConfirmRestart(false);
    setRestartBusy(true);
    try {
      await call('host.daemon.restart', {});
      toast({ title: 'Daemon restarting…', duration: 2400 });
    } catch (e) {
      toast({ title: 'Restart failed', message: String(e), duration: 4000 });
    } finally {
      setRestartBusy(false);
    }
  };

  const handleUpdate = async () => {
    setConfirmUpdate(false);
    setUpdateBusy(true);
    try {
      const result = await call('host.daemon.update', {});
      toast({ ...updateOutcome(result), duration: 4000 });
    } catch (e) {
      toast({ title: 'Update failed', message: String(e), duration: 4000 });
    } finally {
      setUpdateBusy(false);
    }
  };

  if (loading && !profile) {
    return (
      <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
        <ScreenHeader title={`@${profileLabel(id)}`} subtitle={<SubtitleSkeleton />} onBack={goBack} />
        <SettingsSkeleton wide={twoPane} />
      </SafeAreaView>
    );
  }

  if (!profile) {
    return (
      <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
        <ScreenHeader title={`@${profileLabel(id)}`} subtitle="PROFILE · NOT FOUND" onBack={goBack} />
      </SafeAreaView>
    );
  }

  const flagged = (panel, text) => {
    const n = flagCount(att, panel);
    return n ? <AttentionValue count={n} label={attentionLabel(att, panel)}>{text}</AttentionValue> : text;
  };
  const accent = profile.accent ?? FALLBACK_ACCENT;
  const locked = profile.name === 'default';
  const emailSection = sectionData(snap.data?.email);
  const scheduleSection = sectionData(snap.data?.schedules);
  const storageSection = sectionData(snap.data?.storage);
  const usageSection = sectionData(snap.data?.usage);
  const workgroupsSection = sectionData(snap.data?.workgroups);
  const emailList = emailSection?.accounts ?? emailAccounts.data?.accounts ?? [];
  const providers = providerLabels(profile);
  const mcpCount = profile.mcps?.length ?? 0;
  const skillCount = profile.counts?.skills ?? 0;
  const scheduleCount = scheduleSection?.jobs?.length ?? schedule.data?.jobs?.length ?? 0;
  const peerCount = profile.counts?.peers ?? profile.peers?.length ?? 0;
  const workgroups = workgroupsSection?.workgroups ?? [];
  const workgroupCount = workgroups.length || (profile.counts?.workgroups ?? 0);
  const storageRows = storageSection?.storage ?? storage.data?.storage ?? [];
  const usageDays = toUsageDays(usageSection?.days);
  const capUsd = profile.budget_daily_usd;
  const usedUsd = Number(profile.budget_used_usd ?? 0);
  const settingsSyncing = snap.loading || emailAccounts.loading || schedule.loading || storage.loading;

  // Field keys are dotted paths into user.yaml (e.g. `tui.accent`); voice uses a dedicated RPC.
  const saveField = (key, value) =>
    call('host.config.set_field', { profile: id, key, value }).then(() => refreshSettings());
  const failing = (title) => (e) => {
    toast({ title, message: String(e), duration: 3200 });
    throw e;
  };
  const saveOrUnsetField = (key, value) =>
    (String(value ?? '').trim()
      ? call('host.config.set_field', { profile: id, key, value: String(value).trim() })
      : call('host.config.unset_field', { profile: id, key })
    ).then(() => refreshSettings());

  const setVoice = (voiceId) =>
    call('host.voice.set_voice', { profile: id, voice_id: voiceId }).then(() => refreshSettings());
  const toggleAutoRead = () =>
    call('host.voice.set_auto_read', { profile: id, enabled: !profile.voice_auto_read }).then(() => refreshSettings()).catch(failing('Auto-read failed'));

  // host.sandbox.network requires sandbox on (daemon returns -32008 otherwise).
  const toggleSandbox = async () => {
    try {
      await call('host.sandbox.set', { profile: id, state: profile.sandbox ? 'off' : 'on' });
      refreshSettings();
    } catch (e) {
      toast({ title: 'Sandbox failed', message: String(e) });
      throw e;
    }
  };

  const toggleSandboxNetwork = async () => {
    if (!profile.sandbox) return;
    try {
      await call('host.sandbox.network', {
        profile: id,
        state: profile.sandbox_allow_network ? 'off' : 'on',
      });
      refreshSettings();
    } catch (e) {
      toast({ title: 'Network failed', message: String(e) });
      throw e;
    }
  };

  const copyPubkey = async () => {
    if (!profile.pubkey_b64) return;
    const ok = await copyText(profile.pubkey_b64);
    toast({ title: ok ? 'Public key copied' : 'Copy failed', duration: 1400 });
  };

  const deleteProfile = async () => {
    try {
      // host.profile.delete takes `{name}`, not `{profile}`.
      await call('host.profile.delete', { name: id });
      toast({ title: 'Profile deleted', message: `@${id}` });
      router.replace('/');
    } catch (e) {
      toast({ title: 'Delete failed', message: String(e) });
    }
  };

  const contentStyle = twoPane
    ? { paddingHorizontal: space.s9, paddingTop: space.s9, paddingBottom: space.s11, maxWidth: WIDE_BODY_MAX_W, width: '100%', alignSelf: 'center' }
    : { paddingBottom: space.s10 };

  const budgetValue = capUsd == null ? 'not set' : (
    <Meter
      label="Daily budget"
      value={`$${usedUsd.toFixed(2)}`}
      tail={`/$${Number(capUsd).toFixed(2)}`}
      pct={Number(capUsd) > 0 ? usedUsd / Number(capUsd) : 0}
      color={accent}
    />
  );

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader
        title={profileLabel(profile.name)}
        subtitle={twoPane ? 'SETTINGS' : 'PROFILE · SETTINGS'}
        onBack={goBack}
        accent={accent}
        leadingGlyph={<Fold fold={profile.fold} color={accent} size="md" />}
        meta={
          <>
            {profile.model ? (
              <Text numberOfLines={1} style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.ink2, flexShrink: 1 }}>
                {modelLabel(profile.model)}
              </Text>
            ) : null}
            {Number(capUsd) > 0 ? (
              <Meter
                label="Daily budget"
                value={`$${usedUsd.toFixed(2)}`}
                tail={`/$${Number(capUsd).toFixed(2)}`}
                pct={usedUsd / Number(capUsd)}
                color={accent}
              />
            ) : null}
          </>
        }
      />
      <SyncBar syncing={settingsSyncing} />
      <JumpChips current={section} onJump={jump} />
      <SettingsSurface>
      <ScrollView
        ref={scrollRef}
        scrollEventThrottle={64}
        onScroll={onScroll}
        contentContainerStyle={contentStyle}
        keyboardShouldPersistTaps="handled"
        refreshControl={<RefreshControl refreshing={pull.refreshing} onRefresh={pull.onRefresh} tintColor={colors.ink3} />}
      >
        <AttentionSummary att={att} onJump={jump} />
        <SectionHeader first {...anchor('overview')}>Overview</SectionHeader>
        <RowGroup>
          <Row
            label="Paused"
            helper="paused profiles can't be chatted and sort last in new-chat"
            value={
              <Toggle
                on={!!profile.paused}
                label="Paused"
                color={accent}
                onChange={(next) => saveField('paused', next ? 'true' : 'false').catch(failing('Save failed'))}
              />
            }
            chevron={false}
          />
          <RowSeparator />
          <Row
            label="Providers"
            helper={providers.length ? (twoPane ? 'API keys + local Ollama' : providers.join(' · ')) : EMPTY.providers.hint}
            value={twoPane && providers.length ? <ChipRow items={providers} /> : providers.length ? String(providers.length) : EMPTY.providers.title}
            onPress={() => router.push(`/profile/${id}/providers`)}
          />
          <RowSeparator />
          <Row
            label="Model"
            value={profile.model ? modelLabel(profile.model) : '—'}
            onPress={() => setSheet('model')}
          />
          {profile.model_reasoning_supported && (
            <>
              <RowSeparator />
              <Row
                label="Reasoning"
                helper="how hard the model thinks before answering"
                value={(profile.model_reasoning_effort || 'default')}
                onPress={() => setSheet('reasoning')}
              />
            </>
          )}
          {profile.tiers ? (
            <>
              <RowSeparator />
              <Row
                label="Fast model"
                helper="cheap model for side-tasks & delegation"
                value={tierValue(profile.tiers.fast)}
                onPress={() => setSheet('tierFast')}
              />
              {profile.tiers.fast?.reasoning_supported && (
                <>
                  <RowSeparator />
                  <Row
                    label="Fast reasoning"
                    value={(profile.tiers.fast.effort || 'default')}
                    onPress={() => setSheet('tierFastReasoning')}
                  />
                </>
              )}
              <RowSeparator />
              <Row
                label="Deep model"
                helper="stronger model for escalation & deep research"
                value={tierValue(profile.tiers.deep)}
                onPress={() => setSheet('tierDeep')}
              />
              {profile.tiers.deep?.reasoning_supported && (
                <>
                  <RowSeparator />
                  <Row
                    label="Deep reasoning"
                    value={(profile.tiers.deep.effort || 'default')}
                    onPress={() => setSheet('tierDeepReasoning')}
                  />
                </>
              )}
            </>
          ) : null}
          {profile.vision_model !== undefined ? (
            <>
              <RowSeparator />
              <Row
                label="Vision model"
                helper="image inspection via read_image"
                value={profile.vision_model ? modelLabel(profile.vision_model) : 'main model'}
                onPress={() => setSheet('vision')}
              />
            </>
          ) : null}
          <RowSeparator />
          <Row
            label="Budget"
            helper="daily spend cap"
            value={budgetValue}
            onPress={() => setSheet('budget')}
          />
          <RowSeparator />
          <Row
            label="Workspace"
            value={profile.workspace ?? 'not set'}
            onPress={() => setSheet('workspace')}
          />
          <RowSeparator />
          <Row
            label="Appearance"
            value={
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s2, flexShrink: 1 }}>
                <Fold fold={profile.fold} color={accent} size="md" />
                <Text
                  numberOfLines={1}
                  style={{ fontFamily: fonts.sans.medium, fontSize: fontSizes.sm, color: colors.ink2, flexShrink: 1 }}
                >
                  {locked ? 'Alpaca' : pairName(profile.fold, accent)}
                </Text>
                <Text style={{ fontFamily: fonts.monoMedium, fontSize: fontSizes.sm, color: colors.ink3 }}>
                  {locked ? 'brand accent' : accent}
                </Text>
              </View>
            }
            chevron={!locked}
            onPress={locked ? undefined : () => setSheet('appearance')}
          />
          <RowSeparator />
          <Row label="Home" value={`~/.alpi/profiles/${profile.name}`} chevron={false} />
        </RowGroup>

        <SectionHeader kicker="last 14 days" {...anchor('usage')}>Usage</SectionHeader>
        <RowGroup>
          {usageDays.length === 0 && snap.loading ? (
            <SettingsBand><UsageSkeleton /></SettingsBand>
          ) : usageDays.length === 0 ? (
            <Row label={EMPTY.usage.title} helper={EMPTY.usage.hint} chevron={false} />
          ) : (
            <SettingsBand>
              <UsageChart
                days={usageDays}
                accent={accent}
                capLine={capUsd != null ? Number(capUsd) : null}
                total30={usageSection?.total30 ?? null}
              />
            </SettingsBand>
          )}
        </RowGroup>

        <SectionHeader kicker="how peers see this agent" {...anchor('identity')}>Identity</SectionHeader>
        <RowGroup>
          {twoPane ? (
            <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: space.s9, paddingVertical: space.s3 }}>
              <View style={{ width: WIDE_LABEL_W, flexShrink: 1, paddingTop: space.s3 }}>
                <Eyebrow color={colors.ink3}>Identity</Eyebrow>
              </View>
              <View style={{ flex: 1, maxWidth: 520 }}>
                <IdentityEditor profileId={id} profile={profile} call={call} onSaved={refreshSettings} />
              </View>
            </View>
          ) : (
            <Row
              label={profile.bio ? profile.bio : 'Set identity prompt'}
              helper={profile.bio ? undefined : 'one-line public bio · draft it from AGENT.md'}
              labelLines={2}
              onPress={() => router.push(`/profile/${id}/identity`)}
            />
          )}
        </RowGroup>

        <SectionHeader kicker="daemon" {...anchor('service')}>Service</SectionHeader>
        <RowGroup>
          {twoPane ? (
            <Row
              label="Daemon"
              helper={manualStep ? `${manualStep} Restart exits and the supervisor relaunches.` : 'update installs the newest alpi · restart exits and the supervisor relaunches'}
              helperLines={0}
              value={
                <View style={{ flexDirection: 'row', gap: space.s3 }}>
                  {selfUpdate ? (
                    <Button
                      title="Update alpi"
                      variant="secondary"
                      size="sm"
                      loading={updateBusy}
                      disabled={restartBusy}
                      onPress={() => setConfirmUpdate(true)}
                    />
                  ) : null}
                  <Button
                    title="Restart daemon"
                    variant="secondary"
                    size="sm"
                    loading={restartBusy}
                    disabled={updateBusy}
                    onPress={() => setConfirmRestart(true)}
                  />
                </View>
              }
              chevron={false}
            />
          ) : (
            <>
              {selfUpdate ? (
                <Row
                  label="Update alpi"
                  helper="installs the newest alpi and restarts"
                  value={
                    <Button
                      title="Update"
                      variant="secondary"
                      size="sm"
                      loading={updateBusy}
                      onPress={() => setConfirmUpdate(true)}
                    />
                  }
                  onPress={updateBusy ? undefined : () => setConfirmUpdate(true)}
                  chevron={false}
                />
              ) : manualStep ? (
                <Row label="Update alpi" helper={manualStep} helperLines={0} chevron={false} />
              ) : null}
              {selfUpdate || manualStep ? <RowSeparator /> : null}
              <Row
                label="Restart daemon"
                helper="exits the daemon · supervisor relaunches · reconnects automatically"
                value={
                  <Button
                    title="Restart"
                    variant="secondary"
                    size="sm"
                    loading={restartBusy}
                    onPress={() => setConfirmRestart(true)}
                  />
                }
                onPress={restartBusy ? undefined : () => setConfirmRestart(true)}
                chevron={false}
              />
            </>
          )}
          <RowSeparator />
          <Row
            label="Email"
            helper={emailList.length === 0 ? 'IMAP / Gmail accounts' : `${emailList.length} account${emailList.length === 1 ? '' : 's'}`}
            value={
              <View style={{ flexDirection: 'row', gap: space.s1, flexWrap: 'wrap', justifyContent: 'flex-end', maxWidth: 200 }}>
                {emailList.filter((a) => a.configured).length === 0 ? (
                  <Pill off>{EMPTY.accounts.title}</Pill>
                ) : (
                  emailList
                    .filter((a) => a.configured)
                    .map((a) => (
                      <Pill key={a.id ?? a.address} tone="on">
                        {a.address ?? a.id}
                      </Pill>
                    ))
                )}
              </View>
            }
            onPress={() => router.push(`/profile/${id}/email`)}
          />
        </RowGroup>

        <SectionHeader kicker="peers + workgroups" {...anchor('alp')}>ALP</SectionHeader>
        <RowGroup>
          <Row
            label="Public key"
            helper={profile.pubkey_b64 ? 'tap to copy' : 'No identity yet'}
            value={shortPubkey(profile.pubkey_b64)}
            onPress={profile.pubkey_b64 ? copyPubkey : undefined}
            chevron={false}
          />
          <RowSeparator />
          <Row
            label="Port"
            helper="ALP listener · set from alpi setup on the daemon's machine"
            value={String(profile.tcp_port || DEFAULT_ALP_PORT)}
            chevron={false}
          />
          <RowSeparator />
          <Row
            label="Concurrency"
            helper={`${profile.queued_pipelines ? `${profile.queued_pipelines} queued · ` : ''}active workgroup pipelines at once`}
            value={pipelineLimitLabel(profile.max_active_workgroups)}
            onPress={() => setSheet('concurrency')}
          />
          <RowSeparator />
          <Row
            label="Peers"
            helper={peerCount ? undefined : EMPTY.peers.hint}
            value={peerCount ? String(peerCount) : EMPTY.peers.title}
            onPress={() => router.push(`/profile/${id}/peers`)}
          />
          {workgroups.length === 0 ? (
            <>
              <RowSeparator />
              <Row label="Workgroups" helper={workgroupCount ? undefined : EMPTY.workgroups.hint} value={String(workgroupCount)} chevron={false} />
            </>
          ) : (
            workgroups.map((wg) => (
              <View key={wg.id}>
                <RowSeparator />
                <Row
                  label={`#${wg.name || wg.id}`}
                  item
                  helper={wg.is_hub ? 'hub · this profile runs it' : `hub @${wg.hub_id ?? '?'}`}
                  value={wg.paused ? <Pill tone="warn">paused</Pill> : undefined}
                  onPress={() => router.push(`/wg/${wg.id}`)}
                />
              </View>
            ))
          )}
        </RowGroup>

        <SectionHeader {...anchor('schedule')}>Schedule</SectionHeader>
        <RowGroup>
          <Row
            label="Cron jobs"
            helper={attentionHelper(att, 'schedule') ?? 'disable · fire · delete · add new'}
            helperDanger={flagCount(att, 'schedule') > 0}
            value={flagged('schedule', String(scheduleCount))}
            spokenValue={flagCount(att, 'schedule') ? `${attentionLabel(att, 'schedule')}, ${String(scheduleCount)}` : undefined}
            onPress={() => router.push(`/profile/${id}/schedule`)}
          />
        </RowGroup>

        <SectionHeader {...anchor('sandbox')}>Sandbox</SectionHeader>
        <RowGroup>
          <Row
            label="Terminal"
            helper="wraps shell tools in sandbox-exec / bubblewrap"
            value={<Toggle on={!!profile.sandbox} label="Terminal sandbox" color={accent} onChange={toggleSandbox} />}
            chevron={false}
          />
          <RowSeparator />
          <Row
            label="Network"
            helper={profile.sandbox ? 'outbound http access' : 'enable terminal sandbox first'}
            value={
              <Toggle
                on={!!profile.sandbox && !!profile.sandbox_allow_network}
                disabled={!profile.sandbox}
                label="Sandbox network"
                color={accent}
                onChange={toggleSandboxNetwork}
              />
            }
            chevron={false}
          />
        </RowGroup>

        <SectionHeader {...anchor('voice')}>Voice</SectionHeader>
        <RowGroup>
          <Row
            label="Voice"
            value={voiceLabel(profile.voice_id) ?? 'not set'}
            onPress={() => setSheet('voice')}
          />
          <RowSeparator />
          <Row
            label="Auto-read replies"
            helper="reads each agent reply aloud as it arrives — never your messages"
            value={<Toggle on={!!profile.voice_auto_read} label="Auto-read replies" color={accent} onChange={toggleAutoRead} />}
            chevron={false}
          />
        </RowGroup>

        <SectionHeader {...anchor('mcp')}>MCP Servers</SectionHeader>
        <RowGroup>
          <Row
            label="Manage"
            helper="add, remove, inspect tools"
            value={twoPane && mcpCount ? <ChipRow items={(profile.mcps ?? []).map((m) => m.name)} /> : String(mcpCount)}
            onPress={() => router.push(`/profile/${id}/mcp`)}
          />
        </RowGroup>

        <SectionHeader kicker="skills, memories, tools" {...anchor('brain')}>Brain</SectionHeader>
        <RowGroup>
          <Row
            label="Skills"
            helper={attentionHelper(att, 'skills') ?? 'instructions loaded on demand'}
            helperDanger={flagCount(att, 'skills') > 0}
            value={flagged('skills', String(skillCount))}
            spokenValue={flagCount(att, 'skills') ? `${attentionLabel(att, 'skills')}, ${String(skillCount)}` : undefined}
            onPress={() => router.push(`/profile/${id}/brain/skills`)}
          />
          <RowSeparator />
          <Row
            label="Memories"
            helper={attentionHelper(att, 'memory') ?? 'USER · MEMORY · AGENT'}
            helperDanger={flagCount(att, 'memory') > 0}
            value={flagged('memory', '3 files')}
            spokenValue={flagCount(att, 'memory') ? `${attentionLabel(att, 'memory')}, 3 files` : undefined}
            onPress={() => router.push(`/profile/${id}/brain/memory`)}
          />
          <RowSeparator />
          <Row
            label="Tools"
            helper="native callable functions"
            value="view"
            onPress={() => router.push(`/profile/${id}/brain/tools`)}
          />
        </RowGroup>

        <SectionHeader kicker="disk footprint" {...anchor('storage')}>Storage</SectionHeader>
        <RowGroup>
          {storageRows.filter((it) => it.size_bytes > 0 || it.file_count > 0).length === 0 && (snap.loading || storage.loading) ? (
            <ListSkeleton flat rows={3} value label="Loading storage" />
          ) : storageRows.filter((it) => it.size_bytes > 0 || it.file_count > 0).length === 0 ? (
            <Row label={EMPTY.storage.title} helper={EMPTY.storage.hint} chevron={false} />
          ) : (
            storageRows
              .filter((it) => it.size_bytes > 0 || it.file_count > 0)
              .map((it, i) => (
                <View key={it.key}>
                  {i > 0 ? <RowSeparator /> : null}
                  <Row
                    label={it.label}
                    item
                    helper={`${it.file_count} file${it.file_count === 1 ? '' : 's'}`}
                    value={formatBytes(it.size_bytes)}
                    chevron={false}
                  />
                </View>
              ))
          )}
          <RowSeparator />
          <Row
            label="Reclaim space"
            helper="caches, logs, old transcripts, index bloat"
            onPress={() => setSheet('cleanup')}
          />
        </RowGroup>

        <SectionHeader>Danger zone</SectionHeader>
        <RowGroup>
          <Row
            label="Delete profile"
            helper="removes identity, memory, skills, schedule from disk. Cannot be undone."
            danger
            chevron={false}
            onPress={() => setConfirmDelete(true)}
          />
        </RowGroup>
      </ScrollView>
      </SettingsSurface>

      <ModelSheet
        open={sheet === 'model'}
        onClose={() => setSheet(null)}
        profileName={profile.name}
        accent={accent}
        initialValue={profile.model}
        profileModels={profile.models ?? []}
        providerKeys={profile.provider_keys ?? []}
        openrouterModels={(profile.providers?.openrouter?.models) ?? []}
        ollamaNames={(profile.provider_ollama ?? []).map((o) => o.name)}
        onSave={(value) => saveField('model', value)}
      />
      <ReasoningEffortSheet
        open={sheet === 'reasoning'}
        onClose={() => setSheet(null)}
        initialValue={profile.model_reasoning_effort ?? ''}
        onSave={(value) => saveField('model_reasoning.effort', value)}
      />
      <ModelSheet
        open={sheet === 'tierFast'}
        onClose={() => setSheet(null)}
        profileName={profile.name}
        accent={accent}
        title="Fast model"
        subtitle={`@${profile.name} · cheap side-task model`}
        allowClear
        initialValue={profile.tiers?.fast?.model ?? ''}
        profileModels={profile.models ?? []}
        providerKeys={profile.provider_keys ?? []}
        openrouterModels={(profile.providers?.openrouter?.models) ?? []}
        ollamaNames={(profile.provider_ollama ?? []).map((o) => o.name)}
        onSave={(value) => saveField('tiers.fast.model', value)}
      />
      <ReasoningEffortSheet
        open={sheet === 'tierFastReasoning'}
        onClose={() => setSheet(null)}
        initialValue={profile.tiers?.fast?.effort ?? ''}
        onSave={(value) => saveField('tiers.fast.effort', value)}
      />
      <ModelSheet
        open={sheet === 'tierDeep'}
        onClose={() => setSheet(null)}
        profileName={profile.name}
        accent={accent}
        title="Deep model"
        subtitle={`@${profile.name} · escalation model`}
        allowClear
        initialValue={profile.tiers?.deep?.model ?? ''}
        profileModels={profile.models ?? []}
        providerKeys={profile.provider_keys ?? []}
        openrouterModels={(profile.providers?.openrouter?.models) ?? []}
        ollamaNames={(profile.provider_ollama ?? []).map((o) => o.name)}
        onSave={(value) => saveField('tiers.deep.model', value)}
      />
      <ReasoningEffortSheet
        open={sheet === 'tierDeepReasoning'}
        onClose={() => setSheet(null)}
        initialValue={profile.tiers?.deep?.effort ?? ''}
        onSave={(value) => saveField('tiers.deep.effort', value)}
      />
      <ModelSheet
        open={sheet === 'vision'}
        onClose={() => setSheet(null)}
        profileName={profile.name}
        accent={accent}
        title="Vision model"
        subtitle={`@${profile.name} · read_image and browser screenshots`}
        allowClear
        clearHelper="read_image falls back to the profile model"
        initialValue={profile.vision_model ?? ''}
        profileModels={profile.models ?? []}
        providerKeys={profile.provider_keys ?? []}
        openrouterModels={(profile.providers?.openrouter?.models) ?? []}
        ollamaNames={(profile.provider_ollama ?? []).map((o) => o.name)}
        onSave={(value) => saveField('tools.read_image.model', value)}
      />
      <CleanupSheet
        open={sheet === 'cleanup'}
        onClose={() => setSheet(null)}
        profileName={profile.name}
        call={call}
        onCleaned={() => refreshSettings()}
      />
      <BudgetSheet
        open={sheet === 'budget'}
        onClose={() => setSheet(null)}
        profileName={profile.name}
        initialValue={profile.budget_daily_usd}
        onSave={(value) => saveOrUnsetField('budget.daily_usd', value)}
      />
      <WorkspaceSheet
        open={sheet === 'workspace'}
        onClose={() => setSheet(null)}
        profileName={profile.name}
        initialValue={profile.workspace}
        onSave={(value) => saveField('workspace', value)}
      />
      <AppearanceSheet
        open={sheet === 'appearance'}
        onClose={() => setSheet(null)}
        profileName={profile.name}
        initialValue={accent}
        initialFold={profile.fold}
        onSave={async ({ fold, accent: next }) => {
          if (fold) await saveField('tui.fold', fold);
          if (next) await saveField('tui.accent', next.toLowerCase());
        }}
      />
      <VoiceSheet
        open={sheet === 'voice'}
        onClose={() => setSheet(null)}
        profileName={profile.name}
        accent={accent}
        initialValue={profile.voice_id}
        onSave={setVoice}
      />
      <TextPrompt
        open={sheet === 'concurrency'}
        onClose={() => setSheet(null)}
        title="Pipeline concurrency"
        label="active workgroups at once · blank = unlimited"
        initialValue={profile.max_active_workgroups ? String(profile.max_active_workgroups) : ''}
        placeholder="unlimited"
        maxLength={3}
        allowEmpty
        keyboardType="number-pad"
        confirmLabel="Save"
        onSubmit={(value) => {
          const n = Number(String(value ?? '').trim());
          if (String(value ?? '').trim() && (!Number.isInteger(n) || n < 1)) {
            toast({ title: 'Enter a whole number of pipelines', duration: 2000 });
            return;
          }
          saveOrUnsetField('alp.max_active_workgroups', value)
            .then(() => toast({ title: 'Concurrency saved', duration: 1400 }))
            .catch((e) => toast({ title: 'Save failed', message: String(e), duration: 2400 }));
        }}
      />

      <TypedConfirm
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        title={`Delete profile @${profile.name}`}
        body={
          <>
            Permanently removes <Code>~/.alpi/profiles/{profile.name}/</Code> — identity, memory,
            skills, schedule and chat history. <Bold>This action cannot be undone.</Bold>
          </>
        }
        expected={profile.name}
        confirmLabel="Delete profile"
        onConfirm={() => {
          setConfirmDelete(false);
          deleteProfile();
        }}
      />

      <TypedConfirm
        open={confirmRestart}
        onClose={() => setConfirmRestart(false)}
        title="Restart the daemon"
        body="Every connected client briefly loses its socket. Agent loops mid-turn stop and resume on the next request."
        tone="neutral"
        typed={false}
        confirmLabel="Restart"
        onConfirm={handleRestart}
      />

      <TypedConfirm
        open={confirmUpdate}
        onClose={() => setConfirmUpdate(false)}
        title="Update the daemon"
        body="Installs the newest alpi release and restarts the daemon. Every connected client reconnects on its own."
        tone="neutral"
        typed={false}
        confirmLabel="Update"
        onConfirm={handleUpdate}
      />
    </SafeAreaView>
  );
}
