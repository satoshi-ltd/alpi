// wg.members is a count; roster from host.workgroup.members → [{pubkey, bio, voice, joined}]. pubkey → @name via hub.peers + local profiles, else truncated.

import { useLocalSearchParams, useRouter } from 'expo-router';
import { useMemo, useState } from 'react';
import { ActivityIndicator, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { radii, space , fontSizes} from '../../../src/theme/tokens';

import { ActionSheet } from '../../../src/components/ActionSheet';
import { Diamond } from '../../../src/components/Diamond';
import { Icon } from '../../../src/components/Icon';
import { Pill } from '../../../src/components/Pill';
import { Row, RowSeparator, SectionHeader } from '../../../src/components/Row';
import { ScreenHeader } from '../../../src/components/ScreenHeader';
import { useToast } from '../../../src/components/Toast';
import { Bold, Code, TypedConfirm } from '../../../src/components/TypedConfirm';
import { useProfileSummaries, useWorkgroupMembers } from '../../../src/hooks/useDaemonData';
import { useProfile, useWorkgroup } from '../../../src/hooks/useSubject';
import { useEndpoint } from '../../../src/lib/EndpointContext';
import { EditBudgetSheet } from '../../../src/features/sheets/EditBudgetSheet';
import { accentForProfile } from '../../../src/theme/accents';
import { useTheme } from '../../../src/theme/ThemeContext';
import { AdminGuard } from '../../../src/components/AdminGuard';

function shortPubkey(pk) {
  if (!pk) return '—';
  return `${pk.slice(0, 6)}…${pk.slice(-4)}`;
}

export default function WorkgroupSettingsRoute() {
  return (
    <AdminGuard>
      <WorkgroupSettings />
    </AdminGuard>
  );
}

function WorkgroupSettings() {
  const { id } = useLocalSearchParams();
  const router = useRouter();
  const toast = useToast();
  const { call } = useEndpoint();
  const { colors, fonts, fontSizes } = useTheme();
  const { workgroup: wg, loading, refresh } = useWorkgroup(id);
  const memberQuery = useWorkgroupMembers(wg?.profile, wg?.id);
  const summaries = useProfileSummaries();
  const { profile: hub } = useProfile(wg?.hub_id ?? null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [confirmLeave, setConfirmLeave] = useState(false);
  const [memberTarget, setMemberTarget] = useState(null);
  const [confirmKick, setConfirmKick] = useState(null);
  const [budgetOpen, setBudgetOpen] = useState(false);

  if (loading && !wg) {
    return (
      <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
        <ScreenHeader title={`#${id}`} subtitle="WORKGROUP · LOADING" onBack={() => router.back()} />
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <ActivityIndicator color={colors.ink3} />
        </View>
      </SafeAreaView>
    );
  }

  if (!wg) {
    return (
      <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
        <ScreenHeader title={`#${id}`} subtitle="WORKGROUP · NOT FOUND" onBack={() => router.back()} />
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

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader
        title={wg.name ?? wg.id}
        subtitle={`WORKGROUP · ${isHub ? 'HUB' : 'MEMBER'}`}
        onBack={() => router.back()}
        leadingGlyph={<Text style={{ color: colors.ink4, fontFamily: fonts.mono, fontSize: fontSizes.lg }}>#</Text>}
      />
      <ScrollView contentContainerStyle={{ paddingBottom: space.s10 }}>
        <SectionHeader>Overview</SectionHeader>
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
        <Row label="ID" value={`wg_${wg.id}`} chevron={false} />
        <RowSeparator />
        <Row
          label="Accent"
          value={
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s2 }}>
              <View style={{ width: 14, height: 14, borderRadius: radii.sm, backgroundColor: accent }} />
              <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.ink3 }}>
                {accent}
              </Text>
            </View>
          }
          chevron={false}
        />

        {cap > 0 || isHub ? (
          <>
            <SectionHeader>Budget · weekly cap</SectionHeader>
            <View style={{ paddingHorizontal: space.s8, paddingVertical: space.s7, gap: space.s4, backgroundColor: colors.bgPane }}>
              <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: space.s4, flexWrap: 'wrap' }}>
                <Text
                  style={{
                    fontFamily: fonts.sans.semibold,
                    fontSize: fontSizes.display,
                    color: colors.ink,
                    letterSpacing: -0.018 * 26,
                  }}
                >
                  ${used.toFixed(2)}
                </Text>
                <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.md, color: colors.ink3 }}>
                  of <Text style={{ color: colors.ink2 }}>{cap > 0 ? `$${cap.toFixed(2)}` : 'no cap'}</Text>
                  {cap > 0 ? ` · ${Math.round(pct)}%` : ''}
                </Text>
              </View>
              {cap > 0 ? (
                <View style={{ height: 6, borderRadius: radii.pill, backgroundColor: colors.line, overflow: 'hidden' }}>
                  <View style={{ width: `${Math.min(100, pct)}%`, height: '100%', backgroundColor: accent }} />
                </View>
              ) : null}
            </View>
            {isHub ? (
              <Row
                label="Edit cap"
                value={cap > 0 ? `$${cap.toFixed(2)}/wk` : 'set cap'}
                onPress={() => setBudgetOpen(true)}
              />
            ) : null}
          </>
        ) : null}

        <SectionHeader>Briefing · what this workgroup decides</SectionHeader>
        <Row
          label={wg.briefing && wg.briefing.length > 0 ? wg.briefing : 'No briefing set'}
          labelLines={3}
          helper={isHub ? 'tap to edit' : undefined}
          onPress={isHub ? () => router.push(`/wg/${id}/briefing`) : undefined}
          chevron={isHub}
        />

        <SectionHeader>Members · {memberRows.length || wg.members || 0}</SectionHeader>
        {memberRows.map((m, i) => {
          const pk = m.pubkey;
          const resolved = resolveMember(pk);
          const isHubMember = hub?.pubkey_b64 ? pk === hub.pubkey_b64 : resolved.label === `@${wg.hub_id}`;
          return (
            <View key={pk ?? i}>
              {i > 0 ? <RowSeparator /> : null}
              <Row
                leading={<Diamond color={isHubMember ? accent : resolved.accent} size="md" />}
                label={resolved.label}
                helper={m.bio || resolved.bio || (m.joined ? 'joined' : 'invited')}
                value={
                  <View style={{ flexDirection: 'row', gap: space.s2, alignItems: 'center' }}>
                    {isHubMember ? (
                      <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3, letterSpacing: 0.6, textTransform: 'uppercase' }}>
                        hub
                      </Text>
                    ) : null}
                    {!isHubMember ? (m.joined ? <Pill tone="on">joined</Pill> : <Pill off>invited</Pill>) : null}
                  </View>
                }
                onLongPress={isHub && !isHubMember ? () => setMemberTarget({ ...m, label: resolved.label }) : undefined}
                chevron={false}
              />
            </View>
          );
        })}
        {isHub ? (
          <>
            <RowSeparator />
            <Row label="+ Add member" onPress={() => router.push(`/wg/${id}/member`)} chevron={false} />
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
                  icon: <Icon name="x" size={20} color={colors.danger} />,
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
