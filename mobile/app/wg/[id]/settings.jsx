// wg.members is a count; roster from host.workgroup.members → [{pubkey, bio, voice, joined}]. pubkey → @name via hub.peers + local profiles, else truncated.

import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { Pressable, RefreshControl, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { radii, space, tracking } from '../../../src/theme/tokens';

import { toUsageDays } from '../../../../common/usage.mjs';
import { ActionSheet } from '../../../src/components/ActionSheet';
import { Button } from '../../../src/components/Button';
import { Diamond } from '../../../src/components/Diamond';
import { Eyebrow } from '../../../src/components/Eyebrow';
import { Icon } from '../../../src/components/Icon';
import { Toggle } from '../../../src/components/Toggle';
import { Pill } from '../../../src/components/Pill';
import { Row, RowSeparator, SectionHeader, SettingsBand } from '../../../src/components/Row';
import { ScreenHeader } from '../../../src/components/ScreenHeader';
import { SettingsSkeleton } from '../../../src/components/SettingsSkeleton';
import { UsageChart } from '../../../src/components/UsageChart';
import { useToast } from '../../../src/components/Toast';
import { Bold, Code, TypedConfirm } from '../../../src/components/TypedConfirm';
import { useBack } from '../../../src/hooks/useBack';
import { usePullRefresh } from '../../../src/hooks/usePullRefresh';
import { useProfileSummaries, useWorkgroupMembers, useWorkgroupUsage } from '../../../src/hooks/useDaemonData';
import { useProfile, useWorkgroup } from '../../../src/hooks/useSubject';
import { copyText } from '../../../src/lib/clipboard';
import { useEndpoint } from '../../../src/lib/EndpointContext';
import { EditBudgetSheet } from '../../../src/features/sheets/EditBudgetSheet';
import { PipelinesSection } from '../../../src/features/workgroups/PipelinesSection';
import { usePane } from '../../../src/nav/PaneContext';
import { SettingsSurface } from '../../../src/nav/SettingsSurface';
import { accentForProfile } from '../../../src/theme/accents';
import { useTheme } from '../../../src/theme/ThemeContext';
import { AdminGuard } from '../../../src/components/AdminGuard';

const WIDE_BODY_MAX_W = 968;

function shortPubkey(pk) {
  if (!pk) return '—';
  return `${pk.slice(0, 6)}…${pk.slice(-4)}`;
}

export function joinCommand(hubId, wgId) {
  return `alpi workgroup join ${hubId} ${wgId}`;
}

function RemoveButton({ label, onPress }) {
  const { colors } = useTheme();
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      hitSlop={space.s2}
      style={({ pressed }) => ({
        width: 40,
        height: 40,
        borderRadius: radii.md,
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: pressed ? colors.selected : 'transparent',
      })}
    >
      <Icon name="x" size="md" color={colors.ink2} />
    </Pressable>
  );
}

export default function WorkgroupSettingsRoute() {
  return (
    <AdminGuard>
      <WorkgroupSettings />
    </AdminGuard>
  );
}

function WorkgroupSettings() {
  const { id, intent } = useLocalSearchParams();
  const router = useRouter();
  const goBack = useBack();
  const toast = useToast();
  const { call } = useEndpoint();
  const { colors, fonts, fontSizes } = useTheme();
  const { twoPane } = usePane();
  const { workgroup: wg, loading, refresh } = useWorkgroup(id);
  const memberQuery = useWorkgroupMembers(wg?.profile, wg?.id);
  const usage = useWorkgroupUsage(wg?.profile, wg?.id);
  const pull = usePullRefresh(async () => {
    await Promise.all([refresh(), memberQuery.refresh?.(), usage.refresh?.()]);
  });
  const summaries = useProfileSummaries();
  const { profile: hub } = useProfile(wg?.hub_id ?? null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [confirmLeave, setConfirmLeave] = useState(false);
  const [memberTarget, setMemberTarget] = useState(null);
  const [confirmKick, setConfirmKick] = useState(null);
  const [budgetOpen, setBudgetOpen] = useState(false);

  const peerByPubkey = useMemo(() => {
    const m = new Map();
    for (const p of (summaries.data?.profiles ?? [])) {
      if (p.pubkey_b64) m.set(p.pubkey_b64, { name: p.name, accent: p.accent, bio: p.bio });
    }
    for (const peer of (hub?.peers ?? [])) {
      if (peer.pubkey && !m.has(peer.pubkey)) {
        m.set(peer.pubkey, { name: peer.alias || peer.id, accent: undefined, bio: undefined });
      }
    }
    return m;
  }, [summaries.data, hub]);

  useEffect(() => { if (intent === 'delete' && wg?.is_hub) setConfirmDelete(true); }, [intent, wg?.is_hub]);

  if (loading && !wg) {
    return (
      <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
        <ScreenHeader title={`#${id}`} subtitle="WORKGROUP · LOADING" onBack={goBack} />
        <SettingsSkeleton wide={twoPane} />
      </SafeAreaView>
    );
  }

  if (!wg) {
    return (
      <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
        <ScreenHeader title={`#${id}`} subtitle="WORKGROUP · NOT FOUND" onBack={goBack} />
      </SafeAreaView>
    );
  }

  const accent = hub?.accent ?? accentForProfile(wg.hub_id) ?? colors.ink3;
  const cap = Number(wg.budget_usd ?? 0);
  const used = Number(wg.spent_usd ?? 0);
  const pct = cap > 0 ? (used / cap) * 100 : 0;
  const paused = !!wg.paused;
  const isHub = !!wg.is_hub;

  const memberRows = memberQuery.data?.members ?? [];
  const joined = memberRows.filter((m) => m.joined);
  const invited = memberRows.filter((m) => !m.joined);
  const usageDays = toUsageDays(usage.data?.days);

  const resolveMember = (pk) => {
    const hit = peerByPubkey.get(pk);
    if (hit?.name) return { label: `@${hit.name}`, accent: hit.accent ?? accentForProfile(hit.name), bio: hit.bio };
    return { label: shortPubkey(pk), accent: colors.ink3, bio: undefined };
  };

  // pause/resume = hub-only meta.yaml mutation; leave = subscriber ALP message to hub.
  const performAction = async (action) => {
    try {
      await call('host.workgroup.action', { profile: wg.profile, wg_id: wg.id, action });
      toast({ title: action === 'pause' ? 'Paused' : action === 'resume' ? 'Resumed' : 'Left', duration: 1500 });
      refresh();
      if (action === 'leave') router.replace('/');
    } catch (e) {
      toast({ title: `${action} failed`, message: String(e) });
    }
  };

  const toggleAutoRead = async () => {
    try {
      await call('host.workgroup.update', { profile: wg.profile, wg_id: wg.id, auto_read: !wg.auto_read });
      refresh();
    } catch (e) {
      toast({ title: 'auto-read failed', message: String(e) });
      throw e;
    }
  };

  const kickMember = async (pubkey, label) => {
    try {
      await call('host.workgroup.kick', { profile: wg.profile, wg_id: wg.id, member: pubkey });
      toast({ title: 'Kicked', message: label || shortPubkey(pubkey) });
      memberQuery.refresh?.();
      refresh();
    } catch (e) {
      toast({ title: 'Kick failed', message: String(e) });
    }
  };

  const removeWorkgroup = async () => {
    try {
      await call('host.workgroup.remove', { profile: wg.profile, wg_id: wg.id });
      toast({ title: 'Deleted', message: `#${wg.id}` });
      router.replace('/');
    } catch (e) {
      toast({ title: 'Delete failed', message: String(e) });
    }
  };

  const copyJoin = async () => {
    const ok = await copyText(joinCommand(wg.hub_id, wg.id));
    toast({ title: ok ? 'Join command copied' : 'Copy failed', duration: 1400 });
  };

  const contentStyle = twoPane
    ? { paddingHorizontal: space.s9, paddingTop: space.s9, paddingBottom: space.s11, maxWidth: WIDE_BODY_MAX_W, width: '100%', alignSelf: 'center' }
    : { paddingBottom: space.s10 };

  const renderMember = (m, i, { removable }) => {
    const pk = m.pubkey;
    const resolved = resolveMember(pk);
    const isHubMember = hub?.pubkey_b64 ? pk === hub.pubkey_b64 : resolved.label === `@${wg.hub_id}`;
    const canRemove = removable && isHub && !isHubMember;
    return (
      <View key={pk ?? i}>
        {i > 0 ? <RowSeparator /> : null}
        <Row
          leading={<Diamond color={isHubMember ? accent : resolved.accent} size="md" />}
          label={resolved.label}
          item
          helper={m.bio || resolved.bio || (m.joined ? 'joined' : 'invited')}
          value={
            <View style={{ flexDirection: 'row', gap: space.s2, alignItems: 'center' }}>
              {isHubMember ? <Eyebrow>hub</Eyebrow> : null}
              {!isHubMember ? (m.joined ? <Pill tone="on">joined</Pill> : <Pill off>invited</Pill>) : null}
            </View>
          }
          trailing={
            canRemove ? (
              <RemoveButton
                label={`Remove ${resolved.label}`}
                onPress={() => setConfirmKick({ ...m, label: resolved.label })}
              />
            ) : null
          }
          onLongPress={canRemove ? () => setMemberTarget({ ...m, label: resolved.label }) : undefined}
          chevron={false}
        />
      </View>
    );
  };

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader
        title={wg.name ?? wg.id}
        subtitle={twoPane ? 'SETTINGS' : `WORKGROUP · ${isHub ? 'HUB' : 'MEMBER'}`}
        onBack={goBack}
        accent={accent}
        leadingGlyph={<Text style={{ color: colors.ink4, fontFamily: fonts.mono, fontSize: fontSizes.lg }}>#</Text>}
        meta={
          <>
            <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.ink2 }}>{`hub @${wg.hub_id}`}</Text>
            <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.ink2 }}>{`${joined.length} members`}</Text>
            <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: paused ? colors.warningText : colors.successText }}>
              {paused ? 'paused' : 'active'}
            </Text>
            <Text numberOfLines={1} style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.ink3, flexShrink: 1 }}>{wg.id}</Text>
          </>
        }
      />
      <SettingsSurface>
      <ScrollView
        contentContainerStyle={contentStyle}
        keyboardShouldPersistTaps="handled"
        refreshControl={<RefreshControl refreshing={pull.refreshing} onRefresh={pull.onRefresh} tintColor={colors.ink3} />}
      >
        <SectionHeader first>Overview</SectionHeader>
        <Row
          label="Hub"
          value={
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s2 }}>
              <Diamond color={accentForProfile(wg.hub_id)} />
              <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.ink2 }}>
                @{wg.hub_id}
              </Text>
            </View>
          }
          chevron={false}
        />
        <RowSeparator />
        <Row
          label="Status"
          value={<Pill tone={paused ? 'warn' : 'on'}>{paused ? 'paused' : 'active'}</Pill>}
          chevron={false}
        />
        <RowSeparator />
        {isHub ? (
          <>
            <Row
              label="Auto-read messages"
              helper="reads agents' automatic messages aloud — never your directives"
              value={<Toggle on={!!wg.auto_read} label="Auto-read messages" color={accent} onChange={toggleAutoRead} />}
              chevron={false}
            />
            <RowSeparator />
          </>
        ) : null}
        <Row label="ID" value={`wg_${wg.id}`} chevron={false} />
        <RowSeparator />
        <Row
          label="Accent"
          value={
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s2 }}>
              <View style={{ width: 14, height: 14, borderRadius: radii.md, backgroundColor: accent }} />
              <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.ink3 }}>
                {accent}
              </Text>
            </View>
          }
          chevron={false}
        />

        {cap > 0 || isHub ? (
          <>
            <SectionHeader kicker="workgroup spend cap">Budget</SectionHeader>
            <SettingsBand>
              <View style={{ gap: space.s4 }}>
                <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: space.s4, flexWrap: 'wrap' }}>
                  <Text
                    style={{
                      fontFamily: fonts.sans.semibold,
                      fontSize: fontSizes.display,
                      color: colors.ink,
                      letterSpacing: fontSizes.display * tracking.tight,
                    }}
                  >
                    ${used.toFixed(2)}
                  </Text>
                  <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.md, color: colors.ink3 }}>
                    of <Text style={{ color: colors.ink2 }}>{cap > 0 ? `$${cap.toFixed(2)}/wk` : 'no cap'}</Text>
                    {cap > 0 ? ` · ${Math.round(pct)}%` : ''}
                  </Text>
                  {isHub ? (
                    <>
                      <View style={{ flex: 1 }} />
                      <Button title={cap > 0 ? 'Edit' : 'Set cap'} variant="ghost" size="sm" onPress={() => setBudgetOpen(true)} />
                    </>
                  ) : null}
                </View>
                {cap > 0 ? (
                  <View style={{ height: 6, borderRadius: radii.pill, backgroundColor: colors.line, overflow: 'hidden' }}>
                    <View style={{ width: `${Math.min(100, pct)}%`, height: '100%', backgroundColor: accent }} />
                  </View>
                ) : null}
              </View>
            </SettingsBand>
          </>
        ) : null}

        <SectionHeader kicker="last 14 days">Usage</SectionHeader>
        {usageDays.length === 0 && usage.loading ? (
          <Row label="Loading usage…" chevron={false} />
        ) : usageDays.length === 0 ? (
          <Row label="No usage yet" helper="spend appears once the hub posts or settles a task" chevron={false} />
        ) : (
          <SettingsBand>
            <UsageChart days={usageDays} accent={accent} />
          </SettingsBand>
        )}

        <SectionHeader kicker="what this workgroup decides">Briefing</SectionHeader>
        <Row
          label={wg.briefing && wg.briefing.length > 0 ? wg.briefing : 'No briefing set'}
          labelLines={3}
          helper={isHub ? 'tap to edit' : undefined}
          onPress={isHub ? () => router.push(`/wg/${id}/briefing`) : undefined}
          chevron={isHub}
        />
        <PipelinesSection workgroup={wg} />

        <SectionHeader kicker={`${joined.length || wg.members || 0} profiles`}>Members</SectionHeader>
        {joined.map((m, i) => renderMember(m, i, { removable: true }))}
        {isHub ? (
          <>
            {joined.length ? <RowSeparator /> : null}
            <Row label="+ Add member" onPress={() => router.push(`/wg/${id}/member`)} chevron={false} />
          </>
        ) : null}

        {invited.length > 0 ? (
          <>
            <SectionHeader kicker={`${invited.length} pending`}>Invitations</SectionHeader>
            {isHub ? (
              <>
                <Row
                  label="Join command"
                  helper={joinCommand(wg.hub_id, wg.id)}
                  value="Copy"
                  onPress={copyJoin}
                  chevron={false}
                />
                <RowSeparator />
              </>
            ) : null}
            {invited.map((m, i) => renderMember(m, i, { removable: true }))}
          </>
        ) : null}

        <SectionHeader>Danger zone</SectionHeader>
        <Row
          label={paused ? 'Resume workgroup' : 'Pause workgroup'}
          helper={isHub ? (paused ? 'lets the hub fire tasks again' : 'stops the hub from firing tasks') : 'only the hub can pause / resume'}
          onPress={isHub ? () => performAction(paused ? 'resume' : 'pause') : undefined}
          chevron={false}
        />
        {isHub ? (
          <>
            <RowSeparator />
            <Row
              label="Delete workgroup"
              helper="removes channel and all history. Cannot be undone."
              danger
              chevron={false}
              onPress={() => setConfirmDelete(true)}
            />
          </>
        ) : (
          <>
            <RowSeparator />
            <Row
              label="Leave workgroup"
              helper="unsubscribes this profile. The hub keeps the channel."
              danger
              chevron={false}
              onPress={() => setConfirmLeave(true)}
            />
          </>
        )}
      </ScrollView>
      </SettingsSurface>

      <TypedConfirm
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        title={`Delete workgroup #${wg.id}`}
        body={
          <>
            Permanently removes <Code>#{wg.id}</Code> — task history, member assignments and all
            posted messages. Members keep their profiles; only this channel is wiped.{' '}
            <Bold>This action cannot be undone.</Bold>
          </>
        }
        expected={wg.id}
        confirmLabel="Delete workgroup"
        onConfirm={() => {
          setConfirmDelete(false);
          removeWorkgroup();
        }}
      />

      <TypedConfirm
        open={confirmLeave}
        onClose={() => setConfirmLeave(false)}
        title={`Leave #${wg.id}`}
        body={
          <>
            Sends an ALP <Code>leave</Code> to <Code>@{wg.hub_id}</Code> and removes the local
            subscription. You'll lose access to <Code>#{wg.id}</Code> until re-invited.
          </>
        }
        expected={wg.id}
        confirmLabel="Leave workgroup"
        onConfirm={() => {
          setConfirmLeave(false);
          performAction('leave');
        }}
      />

      <ActionSheet
        open={!!memberTarget}
        onClose={() => setMemberTarget(null)}
        title={memberTarget?.label ?? shortPubkey(memberTarget?.pubkey)}
        subtitle={memberTarget?.joined ? 'joined' : 'invited'}
        actions={
          memberTarget
            ? [
                {
                  id: 'kick',
                  label: 'Kick from workgroup',
                  danger: true,
                  icon: <Icon name="x" size="lg" color={colors.danger} />,
                  onPress: () => {
                    const m = memberTarget;
                    setMemberTarget(null);
                    setConfirmKick(m);
                  },
                },
              ]
            : []
        }
      />
      <TypedConfirm
        open={!!confirmKick}
        onClose={() => setConfirmKick(null)}
        title="Kick member"
        body={
          <>
            Removes <Code>{confirmKick?.label ?? shortPubkey(confirmKick?.pubkey)}</Code> from <Code>#{wg?.name || wg?.id}</Code>. <Bold>They lose access to the transcript immediately; rotation of the workgroup key happens on the next post.</Bold>
          </>
        }
        expected={(confirmKick?.label ?? shortPubkey(confirmKick?.pubkey)) || ''}
        confirmLabel="Kick member"
        onConfirm={() => {
          const pk = confirmKick?.pubkey;
          const label = confirmKick?.label;
          setConfirmKick(null);
          if (pk) kickMember(pk, label);
        }}
      />

      <EditBudgetSheet
        open={budgetOpen}
        onClose={() => setBudgetOpen(false)}
        workgroup={wg}
        onSaved={refresh}
      />
    </SafeAreaView>
  );
}
