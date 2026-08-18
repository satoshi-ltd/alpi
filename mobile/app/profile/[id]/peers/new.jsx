// Daemon: host.peers.add. ALP scopes (peer.may_call): link.ping/ask/cancel. Alias set out-of-band in peers.yaml.

import { useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
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
import { useEndpoint } from '../../../../src/lib/EndpointContext';
import { useTheme } from '../../../../src/theme/ThemeContext';

const ALP_SCOPES = [
  { id: 'link.ping', desc: 'liveness probe · zero LLM cost' },
  { id: 'link.ask', desc: 'full agent turn · spends from your daily LLM budget' },
  { id: 'link.cancel', desc: 'abort an in-flight ask the peer started' },
];

export default function AddPeer() {
  const { id } = useLocalSearchParams();
  const router = useRouter();
  const toast = useToast();
  const { call } = useEndpoint();
  const { colors, fonts, fontSizes } = useTheme();

  const [handle, setHandle] = useState('');
  const [pubkey, setPubkey] = useState('');
  const [address, setAddress] = useState('');
  const [scopes, setScopes] = useState(new Set(['link.ping', 'link.ask']));
  const [busy, setBusy] = useState(false);

  const ready = handle.trim() && pubkey.trim() && scopes.size > 0 && !busy;

  const toggle = (sid) => {
    const next = new Set(scopes);
    if (next.has(sid)) next.delete(sid);
    else next.add(sid);
    setScopes(next);
  };

  const save = async () => {
    if (!ready) return;
    setBusy(true);
    try {
      await call('host.peers.add', {
        profile: id,
        id: handle.trim(),
        pubkey: pubkey.trim(),
        address: address.trim() || undefined,
        allow: Array.from(scopes),
      });
      toast({ title: 'Peer added', message: handle });
      router.back();
    } catch (e) {
      toast({ title: 'Add failed', message: String(e) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader
        title="Add peer"
        subtitle={`@${id} · TRUST ANOTHER ALPI`}
        onBack={() => router.back()}
        right={<Button title="Add" size="md" disabled={!ready} loading={busy} onPress={save} />}
      />
      <KeyboardPane>
        <ScrollView contentContainerStyle={{ padding: space.s8, gap: space.s8 }} keyboardShouldPersistTaps="handled">
          <Field
            label="Handle"
            value={handle}
            onChangeText={(t) => setHandle(t.replace(/[^a-zA-Z0-9_-]/g, ''))}
            placeholder="doc · ledger"
            mono
            autoCapitalize="none"
            autoCorrect={false}
            helper="how this peer will appear in @mentions on this profile"
          />
          <Field
            label="Public key"
            value={pubkey}
            onChangeText={setPubkey}
            placeholder="base64 ed25519 pubkey"
            mono
            autoCapitalize="none"
            autoCorrect={false}
            multiline
            rows={3}
          />
          <Field
            label="Address (optional)"
            value={address}
            onChangeText={setAddress}
            placeholder="100.114.140.25:49200"
            mono
            autoCapitalize="none"
            autoCorrect={false}
            helper="empty for intra-machine peers · Tailscale/WireGuard/LAN IP:port"
          />

          <View style={{ gap: space.s3 }}>
            <Eyebrow>Allow scopes</Eyebrow>
            <View style={{ gap: space.s3 }}>
              {ALP_SCOPES.map((s) => {
                const on = scopes.has(s.id);
                return (
                  <Pressable
                    key={s.id}
                    onPress={() => toggle(s.id)}
                    style={{ flexDirection: 'row', alignItems: 'center', gap: space.s4, paddingVertical: space.s1 }}
                  >
                    <Pill tone={on ? 'on' : undefined} off={!on}>● {s.id}</Pill>
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
