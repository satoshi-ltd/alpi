// Daemon: host.workgroup.add_member. Candidates = hub.peers (from host.profile.detail) minus current members. Single-tap adds.

import { useLocalSearchParams } from 'expo-router';
import { useMemo, useState } from 'react';
import { FlatList, Pressable, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { space } from '../../../src/theme/tokens';

import { Fold } from '../../../src/components/Fold';
import { InboxSkeleton } from '../../../src/features/inbox/InboxSkeleton';
import { ScreenHeader } from '../../../src/components/ScreenHeader';
import { useToast } from '../../../src/components/Toast';
import { useBack } from '../../../src/hooks/useBack';
import { useProfileSummaries, useWorkgroupMembers } from '../../../src/hooks/useDaemonData';
import { useProfile, useWorkgroup } from '../../../src/hooks/useSubject';
import { accentForPubkey, foldForPubkey } from '../../../src/lib/localFold';
import { useEndpoint } from '../../../src/lib/EndpointContext';
import { useTheme } from '../../../src/theme/ThemeContext';
import { AdminGuard } from '../../../src/components/AdminGuard';
import { Spinner } from '../../../src/components/Spinner';

export default function AddMemberRoute() {
  return (
    <AdminGuard>
      <AddMember />
    </AdminGuard>
  );
}

function AddMember() {
  const { id } = useLocalSearchParams();
  const goBack = useBack();
  const toast = useToast();
  const { call } = useEndpoint();
  const { colors, fonts, fontSizes } = useTheme();
  const { workgroup: wg } = useWorkgroup(id);
  const memberQuery = useWorkgroupMembers(wg?.profile, wg?.id);
  const summaries = useProfileSummaries();
  const { profile: hub } = useProfile(wg?.hub_id ?? wg?.profile ?? null);
  const [busy, setBusy] = useState(null);

  const candidates = useMemo(() => {
    if (!hub) return [];
    const taken = new Set(
      (memberQuery.data?.members ?? []).map((m) => (typeof m === 'string' ? m : m.pubkey)),
    );
    return (hub.peers ?? []).filter((p) => !taken.has(p.pubkey));
  }, [hub, memberQuery.data]);

  const add = async (peer) => {
    if (!wg || busy) return;
    setBusy(peer.id);
    try {
      await call('host.workgroup.add_member', {
        profile: wg.profile, wg_id: wg.id, member: peer.id,
      });
      toast({ title: 'Added', message: `@${peer.alias || peer.id}` });
      goBack();
    } catch (e) {
      toast({ title: 'Failed', message: String(e) });
      setBusy(null);
    }
  };

  const peersLoading = wg && !hub;

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader
        title="Add member"
        subtitle={`#${id} · PICK FROM @${wg?.hub_id ?? '…'} PEERS`}
        onBack={goBack}
      />
      {peersLoading ? (
        <InboxSkeleton rows={4} label="Loading the hub’s peers" />
      ) : (
        <FlatList
          data={candidates}
          keyExtractor={(p) => p.id}
          renderItem={({ item }) => {
            const isBusy = busy === item.id;
            return (
              <Pressable
                onPress={() => add(item)}
                disabled={!!busy}
                android_ripple={{ color: colors.selected }}
                style={({ pressed }) => ({
                  flexDirection: 'row',
                  alignItems: 'center',
                  gap: space.s5,
                  paddingHorizontal: space.s8,
                  paddingVertical: space.s6,
                  backgroundColor: pressed ? colors.selected : 'transparent',
                  opacity: busy && !isBusy ? 0.4 : 1,
                })}
              >
                <Fold fold={foldForPubkey(summaries, item.pubkey)} color={accentForPubkey(summaries, item.pubkey)} size="md" />
                <View style={{ flex: 1 }}>
                  <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.md, color: colors.ink }}>
                    @{item.alias || item.id}
                  </Text>
                  <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink4 }}>
                    {(item.pubkey || '').slice(0, 16)}…
                  </Text>
                </View>
                {isBusy ? <Spinner color={colors.ink3} /> : null}
              </Pressable>
            );
          }}
          ItemSeparatorComponent={() => <View style={{ height: 0.5, backgroundColor: colors.line, marginLeft: 52 }} />}
          ListEmptyComponent={() => (
            <View style={{ padding: space.s10, alignItems: 'center' }}>
              <Text style={{ color: colors.ink3, textAlign: 'center', fontFamily: fonts.sans.regular, fontSize: fontSizes.md }}>
                {(hub?.peers ?? []).length === 0
                  ? `@${wg?.hub_id ?? '…'} has no peers yet. Add some in the profile's ALP settings first.`
                  : 'No more peers to add'}
              </Text>
            </View>
          )}
        />
      )}
    </SafeAreaView>
  );
}
