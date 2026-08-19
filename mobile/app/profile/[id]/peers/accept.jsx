// Daemon: host.peers.pending_accept({profile, id, pubkey, address?, allow}).
// `id` is the LOCAL handle the current profile assigns the peer.

import { useLocalSearchParams } from 'expo-router';
import { useMemo, useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { KeyboardPane } from '../../../../src/components/KeyboardPane';
import { SafeAreaView } from 'react-native-safe-area-context';
import { space } from '../../../../src/theme/tokens';

import { Button } from '../../../../src/components/Button';
import { Field } from '../../../../src/components/Field';
import { Eyebrow } from '../../../../src/components/Eyebrow';
import { Pill } from '../../../../src/components/Pill';
import { ScreenHeader } from '../../../../src/components/ScreenHeader';
import { useToast } from '../../../../src/components/Toast';
import { useBack } from '../../../../src/hooks/useBack';
import { useEndpoint } from '../../../../src/lib/EndpointContext';
import { useTheme } from '../../../../src/theme/ThemeContext';

const SCOPES = [
  { id: 'link.ping', label: 'link.ping', desc: 'liveness probe · zero LLM cost' },
  { id: 'link.ask', label: 'link.ask', desc: 'full agent turn · spends from your daily LLM budget' },
  { id: 'link.cancel', label: 'link.cancel', desc: 'abort an in-flight ask' },
];

export default function AcceptPendingPeer() {
  const { id, pubkey, address, suggested } = useLocalSearchParams();
  const goBack = useBack();
  const toast = useToast();
  const { call } = useEndpoint();
  const { colors, fonts, fontSizes } = useTheme();

  const [handle, setHandle] = useState(String(suggested ?? '').replace(/[^a-z0-9_-]/g, ''));
  const [scopes, setScopes] = useState(new Set(['link.ping', 'link.ask']));
  const [busy, setBusy] = useState(false);

  const pubkeyStr = String(pubkey ?? '');
  const addressStr = String(address ?? '');
  const validHandle = useMemo(() => /^[a-z0-9_-]{2,}$/.test(handle), [handle]);
  const ready = validHandle && !busy && scopes.size > 0;

  const toggleScope = (s) => {
    const next = new Set(scopes);
    if (next.has(s)) next.delete(s);
    else next.add(s);
    setScopes(next);
  };

  const accept = async () => {
    if (!ready) return;
    setBusy(true);
    try {
      await call('host.peers.pending_accept', {
        profile: id,
        id: handle,
        pubkey: pubkeyStr,
        address: addressStr || undefined,
        allow: Array.from(scopes),
      });
      toast({ title: 'Peer added', message: `@${handle}`, duration: 1800 });
      goBack();
    } catch (e) {
      toast({ title: 'Accept failed', message: String(e) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader
        title="Accept peer"
        subtitle={`@${id} · NAME · SCOPES`}
        onBack={goBack}
        right={<Button title="Accept" size="md" disabled={!ready} loading={busy} onPress={accept} />}
      />
      <KeyboardPane>
        <ScrollView contentContainerStyle={{ padding: space.s8, gap: space.s8 }} keyboardShouldPersistTaps="handled">
          <View style={{ gap: space.s2 }}>
            <Eyebrow>Pubkey</Eyebrow>
            <Text
              style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.ink2 }}
              numberOfLines={2}
            >
              {pubkeyStr}
            </Text>
            {addressStr ? (
              <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink4 }}>
                {addressStr}
              </Text>
            ) : null}
          </View>

          <Field
            label="Handle (this profile)"
            value={handle}
            onChangeText={(t) => setHandle(t.replace(/[^a-zA-Z0-9_-]/g, '').toLowerCase())}
            placeholder="ledger · workshop"
            mono
            autoCapitalize="none"
            autoCorrect={false}
            helper={
              handle && !validHandle
                ? 'min 2 chars · a–z, 0–9, _, -'
                : `how this profile refers to the peer — visible only to you`
            }
          />

          <View style={{ gap: space.s3 }}>
            <Eyebrow>Allow scopes</Eyebrow>
            <View style={{ gap: space.s3 }}>
              {SCOPES.map((s) => {
                const on = scopes.has(s.id);
                return (
                  <Pressable
                    key={s.id}
                    onPress={() => toggleScope(s.id)}
                    style={{ flexDirection: 'row', alignItems: 'center', gap: space.s4, paddingVertical: space.s1 }}
                  >
                    <Pill tone={on ? 'on' : undefined} off={!on}>● {s.label}</Pill>
                    <Text
                      style={{ flex: 1, fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink3 }}
                    >
                      {s.desc}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
          </View>
        </ScrollView>
      </KeyboardPane>
    </SafeAreaView>
  );
}
