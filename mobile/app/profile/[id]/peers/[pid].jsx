// Peer shape: { id, pubkey, address, alias, allow: [link.ping | link.ask | link.cancel | …] }

import { useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { ScrollView, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Diamond } from '../../../../src/components/Diamond';
import { Pill } from '../../../../src/components/Pill';
import { Row, RowSeparator, SectionHeader } from '../../../../src/components/Row';
import { ScreenHeader } from '../../../../src/components/ScreenHeader';
import { useToast } from '../../../../src/components/Toast';
import { Bold, Code, TypedConfirm } from '../../../../src/components/TypedConfirm';
import { useProfile } from '../../../../src/hooks/useSubject';
import { useEndpoint } from '../../../../src/lib/EndpointContext';
import { accentForProfile } from '../../../../src/theme/accents';
import { useTheme } from '../../../../src/theme/ThemeContext';

const KNOWN_SCOPES = [
  { id: 'link.ping', desc: 'liveness probe · zero LLM cost' },
  { id: 'link.ask', desc: 'full agent turn · spends from your daily budget' },
  { id: 'link.cancel', desc: 'abort an in-flight ask' },
];

export default function PeerDetail() {
  const { id, pid } = useLocalSearchParams();
  const router = useRouter();
  const toast = useToast();
  const { call } = useEndpoint();
  const { colors } = useTheme();
  const { profile } = useProfile(id);
  const [confirmRevoke, setConfirmRevoke] = useState(false);

  const peer = (profile?.peers ?? []).find((p) => p.id === pid);
  const allow = peer?.allow ?? [];

  const revoke = async () => {
    try {
      await call('host.peers.remove', { profile: id, id: pid });
      toast({ title: 'Revoked', message: `@${pid}` });
      router.back();
    } catch (e) {
      toast({ title: 'Revoke failed', message: String(e) });
    }
  };

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader
        title={`@${pid}`}
        subtitle={`@${id} · PEER`}
        onBack={() => router.back()}
        leadingGlyph={<Diamond color={accentForProfile(pid)} size={12} />}
      />
      <ScrollView>
        <SectionHeader>Identity</SectionHeader>
        <Row label="Handle" value={`@${pid}`} chevron={false} />
        <RowSeparator />
        <Row label="Pubkey" value={peer?.pubkey ?? '—'} chevron={false} />
        {peer?.alias ? (
          <>
            <RowSeparator />
            <Row label="Alias" value={peer.alias} chevron={false} />
          </>
        ) : null}

        <SectionHeader>Transport</SectionHeader>
        <Row label="Address" value={peer?.address ?? 'intra-machine'} chevron={false} />

        <SectionHeader>Allowed scopes</SectionHeader>
        {KNOWN_SCOPES.map((s, i) => (
          <View key={s.id}>
            {i > 0 ? <RowSeparator /> : null}
            <Row
              label={s.id}
              helper={s.desc}
              value={
                allow.includes(s.id) ? <Pill tone="on">allowed</Pill> : <Pill off>blocked</Pill>
              }
              chevron={false}
            />
          </View>
        ))}

        <SectionHeader>Danger</SectionHeader>
        <Row
          label="Revoke"
          helper="removes trust, future requests will be rejected"
          danger
          chevron={false}
          onPress={() => setConfirmRevoke(true)}
        />
      </ScrollView>
      <TypedConfirm
        open={confirmRevoke}
        onClose={() => setConfirmRevoke(false)}
        title={`Revoke @${pid}`}
        body={
          <>
            Drops <Code>@{pid}</Code> from this profile's peer list. <Bold>Future ALP calls from their pubkey will be rejected until you re-add them.</Bold>
          </>
        }
        expected={String(pid ?? '')}
        confirmLabel="Revoke peer"
        onConfirm={() => {
          setConfirmRevoke(false);
          revoke();
        }}
      />
    </SafeAreaView>
  );
}
