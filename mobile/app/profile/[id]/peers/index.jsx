import { useFocusEffect, useLocalSearchParams, useRouter } from 'expo-router';
import { useCallback } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { radii, space , fontSizes} from '../../../../src/theme/tokens';

import { Button } from '../../../../src/components/Button';
import { Diamond } from '../../../../src/components/Diamond';
import { Pill } from '../../../../src/components/Pill';
import { Row, RowSeparator, SectionHeader } from '../../../../src/components/Row';
import { ScreenHeader } from '../../../../src/components/ScreenHeader';
import { useToast } from '../../../../src/components/Toast';
import { usePeersPending } from '../../../../src/hooks/useDaemonData';
import { useProfile } from '../../../../src/hooks/useSubject';
import { useEndpoint } from '../../../../src/lib/EndpointContext';
import { accentForProfile } from '../../../../src/theme/accents';
import { useTheme } from '../../../../src/theme/ThemeContext';

function shortPubkey(pk) {
  if (!pk) return '—';
  return `${pk.slice(0, 6)}…${pk.slice(-4)}`;
}

export default function PeersList() {
  const { id } = useLocalSearchParams();
  const router = useRouter();
  const toast = useToast();
  const { call } = useEndpoint();
  const { colors, fonts, fontSizes } = useTheme();
  const { profile, loading, refreshDetail } = useProfile(id);
  const pendingQ = usePeersPending(id);

  useFocusEffect(useCallback(() => {
    refreshDetail?.();
    pendingQ.refresh?.();
  }, [refreshDetail, pendingQ.refresh]));

  // Peer shape: {id, pubkey, address, alias, allow}. No liveness — host.peers.ping is separate, skipped for cost.
  const peers = profile?.peers ?? [];
  const pending = pendingQ.data?.pending ?? [];

  const discard = async (pubkey) => {
    try {
      await call('host.peers.pending_discard', { profile: id, pubkey });
      toast({ title: 'Discarded', message: shortPubkey(pubkey), duration: 1500 });
      pendingQ.refresh?.();
      refreshDetail?.();
    } catch (e) {
      toast({ title: 'Discard failed', message: String(e) });
    }
  };

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader
        title="Peers"
        subtitle={`@${id} · ${peers.length} TRUSTED${pending.length ? ` · ${pending.length} PENDING` : ''}`}
        onBack={() => router.back()}
        right={<Button title="+ Add" size="md" variant="ghost" onPress={() => router.push(`/profile/${id}/peers/new`)} />}
      />
      <ScrollView contentContainerStyle={{ paddingBottom: space.s9 }}>
        {/* Pending pairing requests — show first when present so the user sees them before the trusted list. Tap → accept screen with handle + scopes form. Discard kills the request immediately. */}
        {pending.length > 0 ? (
          <>
            <SectionHeader>Pending requests · {pending.length}</SectionHeader>
            {pending.map((p, i) => (
              <View key={p.pubkey}>
                {i > 0 ? <RowSeparator /> : null}
                <View
                  style={{
                    flexDirection: 'row',
                    alignItems: 'center',
                    gap: space.s4,
                    paddingHorizontal: space.s8,
                    paddingVertical: space.s6,
                  }}
                >
                  <Diamond color={accentForProfile(p.pubkey.slice(0, 8))} size="md" />
                  <View style={{ flex: 1, gap: space.s1 }}>
                    <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.md, color: colors.ink }} numberOfLines={1}>
                      {p.local_profile ? `@${p.local_profile}` : shortPubkey(p.pubkey)}
                    </Text>
                    <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink4 }} numberOfLines={1}>
                      {p.address ?? p.pubkey}
                    </Text>
                  </View>
                  <Pressable
                    onPress={() => discard(p.pubkey)}
                    hitSlop={6}
                    style={({ pressed }) => ({
                      paddingHorizontal: space.s5,
                      paddingVertical: space.s2,
                      borderRadius: radii.pill,
                      borderWidth: 0.5,
                      borderColor: colors.line2,
                      backgroundColor: pressed ? colors.selected : 'transparent',
                    })}
                  >
                    <Text style={{ fontFamily: fonts.monoMedium, fontSize: fontSizes.xs, color: colors.ink3 }}>
                      Discard
                    </Text>
                  </Pressable>
                  <Pressable
                    onPress={() =>
                      router.push({
                        pathname: `/profile/${id}/peers/accept`,
                        params: { pubkey: p.pubkey, address: p.address ?? '', suggested: p.local_profile ?? '' },
                      })
                    }
                    hitSlop={6}
                    style={({ pressed }) => ({
                      paddingHorizontal: space.s5,
                      paddingVertical: space.s2,
                      borderRadius: radii.pill,
                      backgroundColor: pressed ? colors.ink2 : colors.ink,
                    })}
                  >
                    <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.xs, color: colors.bgPane }}>
                      Accept
                    </Text>
                  </Pressable>
                </View>
              </View>
            ))}
          </>
        ) : null}

        <SectionHeader>Trusted</SectionHeader>
        {loading && peers.length === 0 ? (
          <View style={{ padding: space.s10, alignItems: 'center' }}>
            <ActivityIndicator color={colors.ink3} />
          </View>
        ) : peers.length === 0 ? (
          <Row label="No peers yet" helper="tap + Add to trust another alpi" chevron={false} />
        ) : (
          peers.map((p, i) => (
            <View key={p.id ?? i}>
              {i > 0 ? <RowSeparator /> : null}
              <Row
                leading={<Diamond color={accentForProfile(p.id)} size="md" />}
                label={`@${p.id}`}
                helper={p.alias || p.address || 'intra-machine'}
                value={
                  // Scope count as proxy for reach — no liveness in daemon summary.
                  <Pill tone={(p.allow ?? []).includes('link.ask') ? 'on' : undefined} off={!(p.allow ?? []).includes('link.ask')}>
                    {(p.allow ?? []).length} scope{(p.allow ?? []).length === 1 ? '' : 's'}
                  </Pill>
                }
                onPress={() => router.push(`/profile/${id}/peers/${p.id}`)}
              />
            </View>
          ))
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
