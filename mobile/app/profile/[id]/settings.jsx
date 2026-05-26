import { useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { radii, space , fontSizes} from '../../../src/theme/tokens';

import { Diamond } from '../../../src/components/Diamond';
import { OnOff } from '../../../src/components/OnOff';
import { Pill } from '../../../src/components/Pill';
import { Row, RowSeparator, SectionHeader } from '../../../src/components/Row';
import { ScreenHeader } from '../../../src/components/ScreenHeader';
import { useToast } from '../../../src/components/Toast';
import { Bold, Code, TypedConfirm } from '../../../src/components/TypedConfirm';
import {
  useGatewayStatus,
  useProfileStorage,
  useScheduleList,
  useSkills,
  useTools,
} from '../../../src/hooks/useDaemonData';
import { useProfile } from '../../../src/hooks/useSubject';
import { useEndpoint } from '../../../src/lib/EndpointContext';
import { AccentSheet } from '../../../src/features/sheets/AccentSheet';
import {
  BudgetSheet,
  ModelSheet,
  ReasoningEffortSheet,
  VoiceSheet,
  WorkspaceSheet,
} from '../../../src/features/sheets/ProfileFieldSheets';
import { accentForProfile } from '../../../src/theme/accents';
import { useTheme } from '../../../src/theme/ThemeContext';
import { voiceLabel } from '../../../src/lib/voices';

// Toggles `service.<name>` in user.yaml; daemon must restart for changes to take effect (mobile can't restart it remotely).
const SUBSYSTEMS = ['gateway', 'schedule', 'alp', 'workgroups'];
const SUBSYSTEMS_DEFAULT = { gateway: true, schedule: true, alp: true, workgroups: true };

function formatBytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  if (n < 1024 ** 3) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  return `${(n / 1024 ** 3).toFixed(2)} GB`;
}

export default function ProfileSettings() {
  const { id } = useLocalSearchParams();
  const router = useRouter();
  const toast = useToast();
  const { call } = useEndpoint();
  const { colors, fonts, fontSizes } = useTheme();
  const { profile, loading, refresh } = useProfile(id);
  const gateways = useGatewayStatus(id);
  const schedule = useScheduleList(id);
  const skills = useSkills(id);
  const tools = useTools(id);
  const storage = useProfileStorage(id);
  const [sheet, setSheet] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [busySubsystem, setBusySubsystem] = useState(null);

  if (loading && !profile) {
    return (
      <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
        <ScreenHeader title={`@${id}`} subtitle="PROFILE · LOADING" onBack={() => router.back()} />
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <ActivityIndicator color={colors.ink3} />
        </View>
      </SafeAreaView>
    );
  }

  if (!profile) {
    return (
      <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
        <ScreenHeader title={`@${id}`} subtitle="PROFILE · NOT FOUND" onBack={() => router.back()} />
      </SafeAreaView>
    );
  }

  const accent = profile.accent ?? accentForProfile(profile.name);
  const gatewayList = gateways.data?.gateways ?? [];
  const providerCount =
    (profile.provider_keys?.length ?? 0) + (profile.provider_ollama?.length ?? 0);
  const mcpCount = profile.mcps?.length ?? 0;
  const skillCount = skills.data?.skills?.length ?? profile.counts?.skills ?? 0;
  const toolCount = tools.data?.tools?.length ?? 0;
  const scheduleCount = schedule.data?.jobs?.length ?? 0;
  const peerCount = profile.counts?.peers ?? profile.peers?.length ?? 0;

  // Field keys are dotted paths into user.yaml (e.g. `tui.accent`); voice uses a dedicated RPC.
  const saveField = (key, value) =>
    call('host.config.set_field', { profile: id, key, value }).then(() => refresh());

  const setVoice = (voiceId) =>
    call('host.voice.set_voice', { profile: id, voice_id: voiceId }).then(() => refresh());

  const subs = profile?.subsystems ?? SUBSYSTEMS_DEFAULT;
  const toggleSubsystem = async (name) => {
    if (busySubsystem) return;
    setBusySubsystem(name);
    const next = !subs[name];
    try {
      await call('host.config.set_field', {
        profile: id,
        key: `service.${name}`,
        value: String(next),
      });
      await refresh();
      toast({
        title: `${name} ${next ? 'enabled' : 'disabled'}`,
        message: 'restart daemon for it to apply',
        duration: 2400,
      });
    } catch (e) {
      toast({ title: `${name} failed`, message: String(e) });
    } finally {
      setBusySubsystem(null);
    }
  };

  // host.sandbox.network requires sandbox on (daemon returns -32008 otherwise).
  const toggleSandbox = async () => {
    try {
      await call('host.sandbox.set', { profile: id, state: profile.sandbox ? 'off' : 'on' });
      refresh();
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
      refresh();
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
        title={profile.name}
        subtitle="PROFILE · SETTINGS"
        onBack={() => router.back()}
        leadingGlyph={<Diamond color={accent} size={12} />}
      />
      <ScrollView contentContainerStyle={{ paddingBottom: space.s10 }}>
        <SectionHeader>Overview</SectionHeader>
        <Row
          label="Providers"
          helper="API keys + local Ollama"
          value={String(providerCount)}
          onPress={() => router.push(`/profile/${id}/providers`)}
        />
        <RowSeparator />
        <Row
          label="Model"
          value={profile.model ? profile.model.split('/').slice(1).join('/') : '—'}
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
              <View style={{ width: 14, height: 14, borderRadius: radii.sm, backgroundColor: accent }} />
              <Text style={{ fontFamily: fonts.monoMedium, fontSize: fontSizes.sm, color: colors.ink3 }}>
                {accent}
              </Text>
            </View>
          }
          onPress={() => setSheet('accent')}
        />
        <RowSeparator />
        <Row label="Home" value={`~/.alpi/profiles/${profile.name}`} chevron={false} />

        <SectionHeader>Identity · how peers see this agent</SectionHeader>
        <Row
          label={profile.bio ? profile.bio : 'Set identity prompt'}
          helper={profile.bio ? undefined : 'one-line public bio'}
          labelLines={2}
          onPress={() => router.push(`/profile/${id}/identity`)}
        />

        <SectionHeader>Services</SectionHeader>
        <Row
          label="Subsystems"
          helper="tap to enable / disable · daemon restart applies"
          value={
            <View style={{ flexDirection: 'row', gap: space.s1, flexWrap: 'wrap', justifyContent: 'flex-end', maxWidth: 220 }}>
              {SUBSYSTEMS.map((s) => {
                const on = subs[s] !== false;
                return (
                  <Pressable
                    key={s}
                    onPress={() => toggleSubsystem(s)}
                    disabled={busySubsystem === s}
                    hitSlop={4}
                  >
                    <Pill tone={on ? 'on' : undefined} off={!on}>{s}</Pill>
                  </Pressable>
                );
              })}
            </View>
          }
          chevron={false}
        />
        <RowSeparator />
        <Row
          label="Gateways"
          helper="telegram · imap · gmail · matrix"
          value={
            <View style={{ flexDirection: 'row', gap: space.s1, flexWrap: 'wrap', justifyContent: 'flex-end', maxWidth: 200 }}>
              {gatewayList.filter((g) => g.configured).length === 0 ? (
                <Pill off>none</Pill>
              ) : (
                gatewayList
                  .filter((g) => g.configured)
                  .map((g) => (
                    <Pill key={g.name ?? g.id} tone="on">
                      {g.name ?? g.id}
                    </Pill>
                  ))
              )}
            </View>
          }
          onPress={() => router.push(`/profile/${id}/gateways`)}
        />

        <SectionHeader>ALP · link protocol</SectionHeader>
        <Row
          label="Peers"
          value={String(peerCount)}
          onPress={() => router.push(`/profile/${id}/peers`)}
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
          value={String(toolCount)}
          onPress={() => router.push(`/profile/${id}/brain/tools`)}
        />

        <SectionHeader>Storage · disk footprint</SectionHeader>
        {(storage.data?.storage ?? []).filter((it) => it.size_bytes > 0 || it.file_count > 0).length === 0 ? (
          <Row label="Nothing yet" helper="storage shows up once this profile starts using disk" chevron={false} />
        ) : (
          (storage.data?.storage ?? [])
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
    </SafeAreaView>
  );
}
