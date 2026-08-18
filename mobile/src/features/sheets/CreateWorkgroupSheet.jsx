import { usePathname, useRouter } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { mobile, radii, space } from '../../theme/tokens';

import { ActionSheet } from '../../components/ActionSheet';
import { Diamond } from '../../components/Diamond';
import { Field, FieldLabel } from '../../components/Field';
import { Icon } from '../../components/Icon';
import { Sheet } from '../../components/Sheet';
import { useToast } from '../../components/Toast';
import { useProfileSummaries, useWorkgroups } from '../../hooks/useDaemonData';
import { useProfile } from '../../hooks/useSubject';
import { useEndpoint } from '../../lib/EndpointContext';
import { openVerb } from '../../lib/panes';
import { usePane } from '../../nav/PaneContext';
import { accentForProfile } from '../../theme/accents';
import { useTheme } from '../../theme/ThemeContext';

const CHIP_H = 32;
const CHIP_SLOP = (mobile.tap - CHIP_H) / 2;

export function CreateWorkgroupSheet({ open, onClose }) {
  const { colors, fonts, fontSizes } = useTheme();
  const router = useRouter();
  const pathname = usePathname();
  const { twoPane } = usePane();
  const toast = useToast();
  const { call } = useEndpoint();
  const summaries = useProfileSummaries();
  const wgs = useWorkgroups();

  const [hub, setHub] = useState(null);
  const [name, setName] = useState('');
  const [members, setMembers] = useState(() => new Set());
  const [briefing, setBriefing] = useState('');
  const [busy, setBusy] = useState(false);
  const [hubPickerOpen, setHubPickerOpen] = useState(false);

  const eligibleHubs = useMemo(
    () => (summaries.data?.profiles ?? []).filter((p) => (p.counts?.peers ?? p.peers?.length ?? 0) > 0),
    [summaries.data],
  );

  useEffect(() => {
    setHub(null);
    setName('');
    setBriefing('');
    setBusy(false);
    setHubPickerOpen(false);
  }, [open]);

  useEffect(() => {
    if (!open || hub || eligibleHubs.length === 0) return;
    setHub(eligibleHubs[0].name);
  }, [open, hub, eligibleHubs]);

  useEffect(() => { setMembers(new Set()); }, [hub]);

  const { profile: hubDetail } = useProfile(hub);
  const hubSummary = useMemo(
    () => eligibleHubs.find((p) => p.name === hub) ?? null,
    [eligibleHubs, hub],
  );
  const peers = hubDetail?.peers ?? [];

  const noHubs = !summaries.loading && eligibleHubs.length === 0;
  const ready = !!hub && name.trim().length > 0 && members.size > 0 && !busy;

  const toggleMember = (mid) => {
    const next = new Set(members);
    if (next.has(mid)) next.delete(mid);
    else next.add(mid);
    setMembers(next);
  };

  const create = async () => {
    if (!ready) return;
    setBusy(true);
    try {
      const result = await call('host.workgroup.create', {
        profile: hub,
        name: name.trim(),
        members: Array.from(members),
        briefing: briefing.trim() || undefined,
      });
      const wgId = result?.wg_id ?? result?.id;
      // Refresh before navigating: /wg/<id> renders "not found" against a list that predates the create.
      await wgs.refresh?.();
      toast({ title: 'Workgroup created', message: `#${name.trim()}` });
      onClose?.();
      router[openVerb({ twoPane, pathname })](wgId ? `/wg/${wgId}` : '/');
    } catch (e) {
      toast({ title: 'Create failed', message: String(e) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="New workgroup"
      subtitle={noHubs ? undefined : 'HUB · NAME · MEMBERS'}
      primaryAction={
        noHubs ? undefined : { label: 'Create', onPress: create, disabled: !ready, loading: busy }
      }
    >
      {noHubs ? (
        <View style={{ padding: space.s8, gap: space.s5 }}>
          <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.md, color: colors.ink2 }}>
            No profile has any ALP peers yet. A workgroup needs at least one peer to invite.
          </Text>
          <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink3 }}>
            Open a profile and add a peer from Settings · ALP, then come back here.
          </Text>
        </View>
      ) : (
        <ScrollView
          contentContainerStyle={{ padding: space.s8, gap: space.s9 }}
          keyboardShouldPersistTaps="handled"
        >
          <View style={{ gap: space.s3 }}>
            <FieldLabel>Hub</FieldLabel>
            <Pressable
              accessibilityLabel="Pick hub profile"
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
                minHeight: mobile.tap,
              })}
            >
              {hubSummary ? (
                <>
                  <Diamond color={hubSummary.accent ?? accentForProfile(hubSummary.name)} />
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
            <FieldLabel>Members — peers of @{hub ?? '…'}</FieldLabel>
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
                      accessibilityLabel={`@${peer.alias || peer.id}`}
                      onPress={() => toggleMember(peer.id)}
                      hitSlop={CHIP_SLOP}
                      style={{
                        flexDirection: 'row',
                        alignItems: 'center',
                        gap: space.s2,
                        paddingHorizontal: space.s5,
                        height: CHIP_H,
                        borderRadius: radii.pill,
                        backgroundColor: on ? `${peerAccent}33` : colors.hover,
                        borderWidth: on ? 1 : 0,
                        borderColor: on ? peerAccent : 'transparent',
                      }}
                    >
                      <Diamond color={peerAccent} />
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
      )}

      <ActionSheet
        open={hubPickerOpen}
        onClose={() => setHubPickerOpen(false)}
        title="Pick hub profile"
        subtitle="WORKGROUP HUB"
        actions={eligibleHubs.map((p) => ({
          id: p.name,
          icon: <Diamond color={p.accent ?? accentForProfile(p.name)} size="md" />,
          label: `@${p.name}`,
          detail: p.model || undefined,
          onPress: () => setHub(p.name),
        }))}
      />
    </Sheet>
  );
}
