import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { radii, space } from '../../../src/theme/tokens';

import { Diamond } from '../../../src/components/Diamond';
import { OnOff } from '../../../src/components/OnOff';
import { Pill } from '../../../src/components/Pill';
import { Row, RowSeparator, SectionHeader } from '../../../src/components/Row';
import { ScreenHeader } from '../../../src/components/ScreenHeader';
import { SyncBar } from '../../../src/components/SyncBar';
import { useBack } from '../../../src/hooks/useBack';
import { modelLabel } from '../../../src/lib/modelLabel';
import { profileLabel } from '../../../src/lib/profileName';
import { useToast } from '../../../src/components/Toast';
import { Bold, Code, TypedConfirm } from '../../../src/components/TypedConfirm';
import {
  useEmailAccounts,
  useProfileStorage,
  useProfileSnapshot,
  useScheduleList,
} from '../../../src/hooks/useDaemonData';
import { useProfile } from '../../../src/hooks/useSubject';
import { useEndpoint } from '../../../src/lib/EndpointContext';
import { AccentSheet } from '../../../src/features/sheets/AccentSheet';
import {
  BudgetSheet,
  CleanupSheet,
  ModelSheet,
  ReasoningEffortSheet,
  VoiceSheet,
  WorkspaceSheet,
} from '../../../src/features/sheets/ProfileFieldSheets';
import { accentForProfile } from '../../../src/theme/accents';
import { useTheme } from '../../../src/theme/ThemeContext';
import { voiceLabel } from '../../../src/lib/voices';

function formatBytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  if (n < 1024 ** 3) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  return `${(n / 1024 ** 3).toFixed(2)} GB`;
}

function formatUsd(n) {
  return `$${Number(n || 0).toFixed(2)}`;
}

function formatTokens(n) {
  const v = Number(n || 0);
  if (v >= 1000000) return `${(v / 1000000).toFixed(1)}M`;
  if (v >= 1000) return `${(v / 1000).toFixed(1)}K`;
  return String(Math.round(v));
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

function usageTotals(days) {
  return (days || []).reduce(
    (acc, d) => ({
      cost: acc.cost + Number(d.cost || 0),
      tokIn: acc.tokIn + Number(d.tokIn || 0),
      tokOut: acc.tokOut + Number(d.tokOut || 0),
    }),
    { cost: 0, tokIn: 0, tokOut: 0 },
  );
}

export default function ProfileSettings() {
  const { id, intent } = useLocalSearchParams();
  const router = useRouter();
  const goBack = useBack();
  const toast = useToast();
  const { call } = useEndpoint();
  const { colors, fonts, fontSizes } = useTheme();
  const snap = useProfileSnapshot(id);
  const detailPre = sectionData(snap.data?.detail);
  const { profile: baseProfile, loading, refresh, refreshDetail } = useProfile(id, { skipDetail: !snap.unsupported });
  const profile = detailPre ? { ...(baseProfile || {}), ...detailPre } : baseProfile;
  const emailAccounts = useEmailAccounts(id, { skipWhen: !needsFallback(snap, 'email') });
  const schedule = useScheduleList(id, { skipWhen: !needsFallback(snap, 'schedules') });
  const storage = useProfileStorage(id, { skipWhen: !needsFallback(snap, 'storage') });
  const [sheet, setSheet] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [restartBusy, setRestartBusy] = useState(false);
  const [confirmRestart, setConfirmRestart] = useState(false);

  useEffect(() => { if (intent === 'delete') setConfirmDelete(true); }, [intent]);

  const refreshSettings = async () => {
    await refresh();
    const next = await snap.refresh();
    if (!next && snap.unsupported) await refreshDetail();
  };

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

  if (loading && !profile) {
    return (
      <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
        <ScreenHeader title={`@${profileLabel(id)}`} subtitle="PROFILE · LOADING" onBack={goBack} />
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <ActivityIndicator color={colors.ink3} />
        </View>
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

  const accent = profile.accent ?? accentForProfile(profile.name);
  const emailSection = sectionData(snap.data?.email);
  const scheduleSection = sectionData(snap.data?.schedules);
  const storageSection = sectionData(snap.data?.storage);
  const usageSection = sectionData(snap.data?.usage);
  const workgroupsSection = sectionData(snap.data?.workgroups);
  const emailList = emailSection?.accounts ?? emailAccounts.data?.accounts ?? [];
  const providerCount =
    (profile.provider_keys?.length ?? 0) + (profile.provider_ollama?.length ?? 0);
  const mcpCount = profile.mcps?.length ?? 0;
  const skillCount = profile.counts?.skills ?? 0;
  const scheduleCount = scheduleSection?.jobs?.length ?? schedule.data?.jobs?.length ?? 0;
  const peerCount = profile.counts?.peers ?? profile.peers?.length ?? 0;
  const workgroupCount = workgroupsSection?.workgroups?.length ?? profile.counts?.workgroups ?? 0;
  const storageRows = storageSection?.storage ?? storage.data?.storage ?? [];
  const usageDays = usageSection?.days ?? [];
  const usageTotal = usageTotals(usageDays);
  const todayUsage = usageDays.find((d) => d.today) ?? usageDays[usageDays.length - 1] ?? null;
  const settingsSyncing = snap.loading || emailAccounts.loading || schedule.loading || storage.loading;

  // Field keys are dotted paths into user.yaml (e.g. `tui.accent`); voice uses a dedicated RPC.
  const saveField = (key, value) =>
    call('host.config.set_field', { profile: id, key, value }).then(() => refreshSettings());

  const setVoice = (voiceId) =>
    call('host.voice.set_voice', { profile: id, voice_id: voiceId }).then(() => refreshSettings());
  const toggleAutoRead = () =>
    call('host.voice.set_auto_read', { profile: id, enabled: !profile.voice_auto_read }).then(() => refreshSettings());

  // host.sandbox.network requires sandbox on (daemon returns -32008 otherwise).
  const toggleSandbox = async () => {
    try {
      await call('host.sandbox.set', { profile: id, state: profile.sandbox ? 'off' : 'on' });
      refreshSettings();
    } catch (e) {
      toast({ title: 'Sandbox failed', message: String(e) });
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
    }
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

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader
        title={profileLabel(profile.name)}
        subtitle="PROFILE · SETTINGS"
        onBack={goBack}
        leadingGlyph={<Diamond color={accent} size="md" />}
      />
      <SyncBar syncing={settingsSyncing} />
      <ScrollView contentContainerStyle={{ paddingBottom: space.s10 }}>
        <SectionHeader>Overview</SectionHeader>
        <Row
          label={profile.paused ? 'Resume profile' : 'Pause profile'}
          helper="paused profiles can't be chatted and sort last in new-chat"
          value={<Pill tone={profile.paused ? 'warn' : 'on'}>{profile.paused ? 'paused' : 'active'}</Pill>}
          onPress={() => saveField('paused', profile.paused ? 'false' : 'true')}
          chevron={false}
        />
        <RowSeparator />
        <Row
          label="Providers"
          helper="API keys + local Ollama"
          value={String(providerCount)}
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
          value={(() => {
            const cap = profile.budget_daily_usd;
            const used = profile.budget_used_usd ?? 0;
            if (cap == null) return 'not set';
            return `$${Number(used).toFixed(2)}/$${Number(cap).toFixed(2)}`;
          })()}
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
          label="Accent"
          value={
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s2 }}>
              <View style={{ width: 14, height: 14, borderRadius: radii.md, backgroundColor: accent }} />
              <Text style={{ fontFamily: fonts.monoMedium, fontSize: fontSizes.sm, color: colors.ink3 }}>
                {accent}
              </Text>
            </View>
          }
          onPress={() => setSheet('accent')}
        />
        <RowSeparator />
        <Row label="Home" value={`~/.alpi/profiles/${profile.name}`} chevron={false} />

        <SectionHeader>Usage · last 14 days</SectionHeader>
        {usageDays.length === 0 && snap.loading ? (
          <Row label="Loading usage…" chevron={false} />
        ) : usageDays.length === 0 ? (
          <Row label="No usage yet" helper="tokens and spend appear after the first turn" chevron={false} />
        ) : (
          <>
            <Row
              label="Today"
              value={formatUsd(todayUsage?.cost)}
              helper={`${formatTokens((todayUsage?.tokIn || 0) + (todayUsage?.tokOut || 0))} tokens`}
              chevron={false}
            />
            <RowSeparator />
            <Row
              label="14-day total"
              value={formatUsd(usageTotal.cost)}
              helper={`${formatTokens(usageTotal.tokIn)} in · ${formatTokens(usageTotal.tokOut)} out`}
              chevron={false}
            />
          </>
        )}

        <SectionHeader>Identity · how peers see this agent</SectionHeader>
        <Row
          label={profile.bio ? profile.bio : 'Set identity prompt'}
          helper={profile.bio ? undefined : 'one-line public bio'}
          labelLines={2}
          onPress={() => router.push(`/profile/${id}/identity`)}
        />

        <SectionHeader>Service</SectionHeader>
        <Row
          label={restartBusy ? 'Restarting…' : 'Daemon'}
          helper="exits the daemon · supervisor relaunches · reconnects automatically"
          value={restartBusy ? null : 'Restart'}
          onPress={restartBusy ? undefined : () => setConfirmRestart(true)}
          chevron={false}
        />
        <RowSeparator />
        <Row
          label="Email"
          helper={emailList.length === 0 ? 'IMAP / Gmail accounts' : `${emailList.length} account${emailList.length === 1 ? '' : 's'}`}
          value={
            <View style={{ flexDirection: 'row', gap: space.s1, flexWrap: 'wrap', justifyContent: 'flex-end', maxWidth: 200 }}>
              {emailList.filter((a) => a.configured).length === 0 ? (
                <Pill off>none</Pill>
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

        <SectionHeader>ALP · link protocol</SectionHeader>
        <Row
          label="Peers"
          value={String(peerCount)}
          onPress={() => router.push(`/profile/${id}/peers`)}
        />
        <RowSeparator />
        <Row
          label="Workgroups"
          value={String(workgroupCount)}
          chevron={false}
        />

        <SectionHeader>Schedule</SectionHeader>
        <Row
          label="Cron jobs"
          helper="disable · fire · delete · add new"
          value={String(scheduleCount)}
          onPress={() => router.push(`/profile/${id}/schedule`)}
        />

        <SectionHeader>Sandbox</SectionHeader>
        <Row
          label="Terminal"
          helper="wraps shell tools in sandbox-exec / bubblewrap"
          value={<OnOff on={!!profile.sandbox} />}
          onPress={toggleSandbox}
          chevron={false}
        />
        <RowSeparator />
        <Row
          label="Network"
          helper={profile.sandbox ? 'outbound http access' : 'enable terminal sandbox first'}
          value={<OnOff on={!!profile.sandbox && !!profile.sandbox_allow_network} disabled={!profile.sandbox} />}
          onPress={profile.sandbox ? toggleSandboxNetwork : undefined}
          chevron={false}
        />

        <SectionHeader>Voice</SectionHeader>
        <Row
          label="Voice"
          value={voiceLabel(profile.voice_id) ?? 'not set'}
          onPress={() => setSheet('voice')}
        />
        <RowSeparator />
        <Row
          label="Auto-read replies"
          helper="reads each agent reply aloud as it arrives — never your messages"
          value={<OnOff on={!!profile.voice_auto_read} />}
          onPress={toggleAutoRead}
        />

        <SectionHeader>MCP Servers</SectionHeader>
        <Row
          label="Manage"
          helper="add, remove, inspect tools"
          value={String(mcpCount)}
          onPress={() => router.push(`/profile/${id}/mcp`)}
        />

        <SectionHeader>Brain · skills, memories, tools</SectionHeader>
        <Row
          label="Skills"
          helper="instructions loaded on demand"
          value={String(skillCount)}
          onPress={() => router.push(`/profile/${id}/brain/skills`)}
        />
        <RowSeparator />
        <Row
          label="Memories"
          helper="USER · MEMORY · AGENT"
          value="3 files"
          onPress={() => router.push(`/profile/${id}/brain/memory`)}
        />
        <RowSeparator />
        <Row
          label="Tools"
          helper="native callable functions"
          value="view"
          onPress={() => router.push(`/profile/${id}/brain/tools`)}
        />

        <SectionHeader>Storage · disk footprint</SectionHeader>
        {storageRows.filter((it) => it.size_bytes > 0 || it.file_count > 0).length === 0 ? (
          <Row
            label={snap.loading || storage.loading ? 'Loading storage…' : 'Nothing yet'}
            helper={snap.loading || storage.loading ? undefined : 'storage shows up once this profile starts using disk'}
            chevron={false}
          />
        ) : (
          storageRows
            .filter((it) => it.size_bytes > 0 || it.file_count > 0)
            .map((it, i, arr) => (
              <View key={it.key}>
                {i > 0 ? <RowSeparator /> : null}
                <Row
                  label={it.label}
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

        <SectionHeader>Danger zone</SectionHeader>
        <Row
          label="Delete profile"
          helper="removes identity, memory, skills, schedule from disk. Cannot be undone."
          danger
          chevron={false}
          onPress={() => setConfirmDelete(true)}
        />
      </ScrollView>

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
        onSave={(value) => saveField('budget.daily_usd', value)}
      />
      <WorkspaceSheet
        open={sheet === 'workspace'}
        onClose={() => setSheet(null)}
        profileName={profile.name}
        initialValue={profile.workspace}
        onSave={(value) => saveField('workspace', value)}
      />
      <AccentSheet
        open={sheet === 'accent'}
        onClose={() => setSheet(null)}
        profileName={profile.name}
        initialValue={accent}
        onSave={(value) => saveField('tui.accent', (value ?? '').toLowerCase())}
      />
      <VoiceSheet
        open={sheet === 'voice'}
        onClose={() => setSheet(null)}
        profileName={profile.name}
        accent={accent}
        initialValue={profile.voice_id}
        onSave={setVoice}
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
        body={
          <>
            Every connected client briefly loses its socket. Agent loops mid-turn stop and
            resume on the next request. <Bold>Type restart to confirm.</Bold>
          </>
        }
        expected="restart"
        confirmLabel="Restart"
        onConfirm={handleRestart}
      />
    </SafeAreaView>
  );
}
