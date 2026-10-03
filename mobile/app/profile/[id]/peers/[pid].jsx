// Peer shape: { id, pubkey, address, alias, allow: [link.ping | link.ask | link.cancel | …] }

import { useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { ScrollView, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Fold } from '../../../../src/components/Fold';
import { Pill } from '../../../../src/components/Pill';
import { Row, RowGroup, RowSeparator, SectionHeader } from '../../../../src/components/Row';
import { ScreenHeader } from '../../../../src/components/ScreenHeader';
import { useToast } from '../../../../src/components/Toast';
import { Bold, Code, TypedConfirm } from '../../../../src/components/TypedConfirm';
import { useBack } from '../../../../src/hooks/useBack';
import { useProfileSummaries } from '../../../../src/hooks/useDaemonData';
import { useProfile } from '../../../../src/hooks/useSubject';
import { useEndpoint } from '../../../../src/lib/EndpointContext';
import { accentForPubkey, foldForPubkey } from '../../../../src/lib/localFold';
import { useTheme } from '../../../../src/theme/ThemeContext';

const KNOWN_SCOPES = [
  { id: 'link.ping', desc: 'liveness probe · zero LLM cost' },
  { id: 'link.ask', desc: 'full agent turn · spends from your daily budget' },
  { id: 'link.cancel', desc: 'abort an in-flight ask' },
];

export default function PeerDetail() {
  const { id, pid } = useLocalSearchParams();
  const goBack = useBack();
  const toast = useToast();
  const { call } = useEndpoint();
  const { colors } = useTheme();
  const { profile } = useProfile(id);
  const summaries = useProfileSummaries();
  const [confirmRevoke, setConfirmRevoke] = useState(false);

  const peer = (profile?.peers ?? []).find((p) => p.id === pid);
  const allow = peer?.allow ?? [];

  const revoke = async () => {
    try {
      await call('host.peers.remove', { profile: id, id: pid });
      toast({ title: 'Revoked', message: `@${pid}` });
      goBack();
    } catch (e) {
      toast({ title: 'Revoke failed', message: String(e) });
    }
  };

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader
        title={`@${pid}`}
        subtitle={`@${id} · PEER`}
        onBack={goBack}
        leadingGlyph={<Fold fold={foldForPubkey(summaries, peer?.pubkey)} color={accentForPubkey(summaries, peer?.pubkey)} size="md" />}
      />
      <ScrollView>
        <SectionHeader>Identity</SectionHeader>
        <RowGroup>
          <Row label="Handle" value={`@${pid}`} chevron={false} />
          <RowSeparator />
          <Row label="Pubkey" value={peer?.pubkey ?? '—'} chevron={false} />
          {peer?.alias ? (
            <>
              <RowSeparator />
              <Row label="Alias" value={peer.alias} chevron={false} />
            </>
          ) : null}
        </RowGroup>

        <SectionHeader>Transport</SectionHeader>
        <RowGroup>
          <Row label="Address" value={peer?.address ?? 'intra-machine'} chevron={false} />
        </RowGroup>

        <SectionHeader>Allowed scopes</SectionHeader>
        <RowGroup>
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
        </RowGroup>

        <SectionHeader>Danger</SectionHeader>
        <RowGroup>
          <Row
            label="Revoke"
            helper="removes trust, future requests will be rejected"
            danger
            chevron={false}
            onPress={() => setConfirmRevoke(true)}
          />
        </RowGroup>
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
