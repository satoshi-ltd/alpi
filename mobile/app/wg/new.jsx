// Daemon: host.workgroup.create({profile, name, members, briefing}). `members` =
// peer ids resolved via the hub's peers.yaml. Hubs need counts.peers > 0.

import { useRouter } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { radii, space , fontSizes} from '../../src/theme/tokens';

import { ActionSheet } from '../../src/components/ActionSheet';
import { Button } from '../../src/components/Button';
import { Diamond } from '../../src/components/Diamond';
import { Field } from '../../src/components/Field';
import { Icon } from '../../src/components/Icon';
import { ScreenHeader } from '../../src/components/ScreenHeader';
import { useToast } from '../../src/components/Toast';
import { useProfileSummaries } from '../../src/hooks/useDaemonData';
import { useProfile } from '../../src/hooks/useSubject';
import { useEndpoint } from '../../src/lib/EndpointContext';
import { accentForProfile } from '../../src/theme/accents';
import { useTheme } from '../../src/theme/ThemeContext';
import { AdminGuard } from '../../src/components/AdminGuard';

export default function NewWorkgroupRoute() {
  return (
    <AdminGuard>
      <NewWorkgroup />
    </AdminGuard>
  );
}

function NewWorkgroup() {
  const router = useRouter();
  const toast = useToast();
  const { call } = useEndpoint();
  const summaries = useProfileSummaries();
  const { colors, fonts, fontSizes } = useTheme();
  const [hub, setHub] = useState(null);
  const [name, setName] = useState('');
  const [members, setMembers] = useState(new Set());
  const [briefing, setBriefing] = useState('');
  const [busy, setBusy] = useState(false);
  const [hubPickerOpen, setHubPickerOpen] = useState(false);

  const eligibleHubs = useMemo(
    () => (summaries.data?.profiles ?? []).filter((p) => (p.counts?.peers ?? p.peers?.length ?? 0) > 0),
    [summaries.data],
  );

  useEffect(() => {
    if (!hub && eligibleHubs.length > 0) setHub(eligibleHubs[0].name);
  }, [eligibleHubs, hub]);

  useEffect(() => { setMembers(new Set()); }, [hub]);

  const { profile: hubDetail } = useProfile(hub);
  const hubSummary = useMemo(
    () => eligibleHubs.find((p) => p.name === hub) ?? null,
    [eligibleHubs, hub],
  );
  const peers = hubDetail?.peers ?? [];

  const ready = !!hub && name.trim().length > 0 && members.size > 0;

  const toggleMember = (mid) => {
    const next = new Set(members);
    if (next.has(mid)) next.delete(mid);
    else next.add(mid);
    setMembers(next);
  };

  const create = async () => {
    if (!ready || busy) return;
    setBusy(true);
    try {
      const result = await call('host.workgroup.create', {
        profile: hub,
        name: name.trim(),
        members: Array.from(members),
        briefing: briefing.trim() || undefined,
      });
      const wgId = result?.wg_id ?? result?.id;
      toast({ title: 'Workgroup created', message: `#${name.trim()}` });
      if (wgId) router.replace(`/wg/${wgId}`);
      else router.replace('/');
    } catch (e) {
      toast({ title: 'Create failed', message: String(e) });
    } finally {
      setBusy(false);
    }
  };

  const Eyebrow = ({ children }) => (
    <Text
      style={{
        fontFamily: fonts.mono,
        fontSize: fontSizes.xs,
        color: colors.ink3,
        letterSpacing: 0.6,
        textTransform: 'uppercase',
      }}
    >
      {children}
    </Text>
  );

  if (!summaries.loading && eligibleHubs.length === 0) {
    return (
      <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
        <ScreenHeader title="New workgroup" onBack={() => router.back()} />
        <View style={{ padding: space.s9, gap: space.s5 }}>
          <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.md, color: colors.ink2 }}>
            No profile has any ALP peers yet. A workgroup needs at least one peer to invite.
          </Text>
          <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink3 }}>
            Open a profile and add a peer from Settings · ALP, then come back here.
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader
        title="New workgroup"
        onBack={() => router.back()}
        right={<Button title="Create" size="md" onPress={create} disabled={!ready || busy} loading={busy} />}
      />
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={{ padding: space.s8, gap: space.s9 }} keyboardShouldPersistTaps="handled">
          <View style={{ gap: space.s3 }}>
            <Eyebrow>Hub</Eyebrow>
            <Pressable
              onPress={() => setHubPickerOpen(true)}
              style={({ pressed }) => ({
                flexDirection: 'row',
                alignItems: 'center',
                gap: space.s4,
                backgroundColor: pressed ? colors.selected : colors.bgInput,
                borderWidth: 0.5,
                borderColor: colors.line2,
                borderRadius: radii.lg,
                paddingHorizontal: space.s6,
                minHeight: 44,
              })}
            >
              {hubSummary ? (
                <>
                  <Diamond color={hubSummary.accent ?? accentForProfile(hubSummary.name)} size={10} />
                  <Text style={{ flex: 1, fontFamily: fonts.mono, fontSize: fontSizes.md, color: colors.ink }}>
                    @{hubSummary.name}
                  </Text>
                  {hubSummary.model ? (
                    <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>
                      {hubSummary.model}
                    </Text>
                  ) : null}
                </>
              ) : (
                <Text style={{ flex: 1, fontFamily: fonts.mono, fontSize: fontSizes.md, color: colors.ink3 }}>
                  Pick profile…
                </Text>
              )}
              <Icon name="chevron-down" size={16} color={colors.ink3} />
            </Pressable>
          </View>

          <Field
            label="Name"
            placeholder="team-alpha · roadmap · customers"
            value={name}
            onChangeText={(t) => setName(t.replace(/[^a-zA-Z0-9_-]/g, ''))}
            mono
            autoCapitalize="none"
            autoCorrect={false}
          />

          <View style={{ gap: space.s4 }}>
            <Eyebrow>Members — peers of @{hub ?? '…'}</Eyebrow>
            {peers.length === 0 ? (
              <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink4 }}>
                @{hub} has no peers yet — add some from Profile · ALP first
              </Text>
            ) : (
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: space.s3 }}>
                {peers.map((peer) => {
                  const on = members.has(peer.id);
                  const local = (summaries.data?.profiles ?? []).find((x) => x.pubkey_b64 === peer.pubkey);
                  const peerAccent = local?.accent ?? accentForProfile(peer.id);
                  return (
                    <Pressable
                      key={peer.id}
                      onPress={() => toggleMember(peer.id)}
                      style={{
                        flexDirection: 'row',
                        alignItems: 'center',
                        gap: space.s2,
                        paddingHorizontal: space.s5,
                        height: 32,
                        borderRadius: radii.pill,
                        backgroundColor: on ? `${peerAccent}33` : colors.hover,
                        borderWidth: on ? 1 : 0,
                        borderColor: on ? peerAccent : 'transparent',
                      }}
                    >
                      <Diamond color={peerAccent} size={8} />
                      <Text
                        style={{
                          fontFamily: fonts.mono,
                          fontSize: fontSizes.sm,
                          color: on ? colors.ink : colors.ink2,
                        }}
                      >
                        @{peer.alias || peer.id}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>
            )}
          </View>

          <Field
            label="Briefing (optional)"
            value={briefing}
            onChangeText={setBriefing}
            multiline
            rows={4}
            placeholder="what is this workgroup about? who does what?"
          />
        </ScrollView>
      </KeyboardAvoidingView>

      <ActionSheet
        open={hubPickerOpen}
        onClose={() => setHubPickerOpen(false)}
        title="Pick hub profile"
        subtitle="WORKGROUP HUB"
        actions={eligibleHubs.map((p) => ({
          id: p.name,
          icon: <Diamond color={p.accent ?? accentForProfile(p.name)} size={12} />,
          label: `@${p.name}`,
          detail: p.model || undefined,
          onPress: () => setHub(p.name),
        }))}
      />
    </SafeAreaView>
  );
}
