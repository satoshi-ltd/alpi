import { CameraView, useCameraPermissions } from 'expo-camera';
import * as Clipboard from 'expo-clipboard';
import { useRouter } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { radii, space , fontSizes, lineHeights} from '../src/theme/tokens';

import { Button } from '../src/components/Button';
import { useToast } from '../src/components/Toast';
import { useEndpoint } from '../src/lib/EndpointContext';
import { parsePairing, PairingError } from '../src/lib/pairing';
import { probe } from '../src/lib/probe';
import { useTheme } from '../src/theme/ThemeContext';

export default function Pair() {
  const { colors, fonts, fontSizes, mobile } = useTheme();
  const router = useRouter();
  const toast = useToast();
  // Use the context's addConnection — calling saveConnection() directly only writes to SecureStore; the EndpointProvider's in-memory `connections` array stays stale until next mount, so the freshly-paired daemon doesn't appear in the connection list. addConnection() chains saveConnection + refresh() so context state stays in sync.
  const { addConnection } = useEndpoint();
  const [mode, setMode] = useState('paste');
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [permission, requestPermission] = useCameraPermissions();

  const tryPair = async (input) => {
    setBusy(true);
    setError(null);
    try {
      const endpoint = parsePairing(input);
      const { status, deviceName, deviceId } = await probe(endpoint);
      if (status === 'auth-failed') {
        throw new PairingError('Token rejected by daemon. Generate a fresh pairing link on the daemon and try again.');
      }
      if (status !== 'online') {
        throw new PairingError(`Daemon unreachable at ${endpoint.ip}:${endpoint.port}. Make sure the daemon is running, both devices are on the same network, and the port is open.`);
      }
      if (!deviceId) {
        throw new PairingError('Daemon too old or host.version unavailable. Update alpi to v0.6.6 or newer and retry.');
      }
      const finalEndpoint = { ...endpoint, deviceId, ...(deviceName ? { name: deviceName } : {}) };
      await addConnection(finalEndpoint);
      toast({ title: 'Paired', message: `Connected to ${finalEndpoint.name}`, duration: 2200 });
      router.replace('/paired');
    } catch (e) {
      setError(e?.message ?? 'Pairing failed');
    } finally {
      setBusy(false);
    }
  };

  const handlePaste = async () => {
    const clip = await Clipboard.getStringAsync();
    if (clip) setText(clip);
  };

  const handleScan = async ({ data }) => {
    if (busy) return;
    setMode('paste');
    setText(data);
    await tryPair(data);
  };

  if (mode === 'scan') {
    const ready = permission?.granted;
    return (
      <View style={{ flex: 1, backgroundColor: '#000' }}>
        <SafeAreaView edges={['top']} style={{ zIndex: 2 }}>
          <View
            style={{
              flexDirection: 'row',
              alignItems: 'center',
              padding: space.s7,
              gap: space.s5,
            }}
          >
            <Pressable onPress={() => setMode('paste')} hitSlop={12}>
              <Text style={{ color: '#fff', fontSize: fontSizes.display, fontFamily: fonts.sans.regular }}>‹</Text>
            </Pressable>
            <View style={{ flex: 1 }}>
              <Text style={{ color: '#fff', fontFamily: fonts.sans.semibold, fontSize: fontSizes.md }}>
                Pair this phone
              </Text>
              <Text
                style={{
                  color: 'rgba(255,255,255,0.6)',
                  fontFamily: fonts.mono,
                  fontSize: fontSizes.xs,
                  marginTop: space.s1,
                }}
              >
                Scan the QR shown on your daemon
              </Text>
            </View>
          </View>
        </SafeAreaView>
        {ready ? (
          <CameraView
            onBarcodeScanned={busy ? undefined : handleScan}
            barcodeScannerSettings={{ barcodeTypes: ['qr'] }}
            style={{ flex: 1 }}
          />
        ) : (
          <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: space.s9, gap: space.s7 }}>
            <Text style={{ color: '#fff', textAlign: 'center', fontFamily: fonts.sans.regular, fontSize: fontSizes.lg }}>
              Camera permission needed to scan the pairing QR.
            </Text>
            <Button title="Grant access" onPress={requestPermission} />
          </View>
        )}
        <SafeAreaView edges={['bottom']}>
          <View style={{ padding: space.s7 }}>
            <Pressable
              onPress={() => setMode('paste')}
              style={({ pressed }) => ({
                padding: space.s6,
                borderRadius: radii.lg,
                backgroundColor: pressed ? 'rgba(255,255,255,0.18)' : 'rgba(255,255,255,0.12)',
                alignItems: 'center',
              })}
            >
              <Text style={{ color: '#fff', fontFamily: fonts.sans.medium, fontSize: fontSizes.md }}>
                Paste alpi:// link instead
              </Text>
            </Pressable>
          </View>
        </SafeAreaView>
      </View>
    );
  }

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', padding: space.s7, gap: space.s5 }}>
        <Pressable onPress={() => router.back()} hitSlop={12}>
          <Text style={{ color: colors.ink, fontSize: fontSizes.display }}>‹</Text>
        </Pressable>
        <View style={{ flex: 1 }}>
          <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.xl, color: colors.ink }}>
            Pair this phone
          </Text>
          <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3, marginTop: space.s1, letterSpacing: 0.6 }}>
            CONNECT TO YOUR DAEMON
          </Text>
        </View>
      </View>

      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
      <ScrollView contentContainerStyle={{ padding: space.s8, gap: space.s8 }} keyboardShouldPersistTaps="handled">
        <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.md, color: colors.ink2, lineHeight: fontSizes.md * lineHeights.normal }}>
          Open your daemon's settings, choose{' '}
          <Text style={{ fontFamily: fonts.mono, color: colors.ink }}>Settings → Devices → + Pair phone</Text>, then either
          scan the QR or paste the <Text style={{ fontFamily: fonts.mono, color: colors.ink }}>alpi://</Text> link below.
        </Text>

        <Button title="Scan QR" onPress={() => setMode('scan')} fullWidth />

        <View style={{ gap: space.s3 }}>
          <Text
            style={{
              fontFamily: fonts.mono,
              fontSize: fontSizes.xs,
              color: colors.ink3,
              letterSpacing: 0.6,
              textTransform: 'uppercase',
            }}
          >
            or paste link
          </Text>
          <View
            style={{
              backgroundColor: colors.bgPane,
              borderRadius: radii.lg,
              borderWidth: 0.5,
              borderColor: colors.line2,
              padding: space.s5,
            }}
          >
            <TextInput
              value={text}
              onChangeText={setText}
              placeholder="alpi://device?host=…&port=…&name=…&token=…"
              placeholderTextColor={colors.ink4}
              multiline
              numberOfLines={3}
              autoCapitalize="none"
              autoCorrect={false}
              style={{
                minHeight: 64,
                fontFamily: fonts.mono,
                fontSize: fontSizes.sm,
                color: colors.ink,
                textAlignVertical: 'top',
              }}
            />
          </View>
          <Pressable onPress={handlePaste} hitSlop={6} style={{ alignSelf: 'flex-end' }}>
            <Text style={{ fontFamily: fonts.sans.medium, fontSize: fontSizes.md, color: colors.ink2 }}>
              Paste from clipboard
            </Text>
          </Pressable>
        </View>

        {error ? (
          <View
            style={{
              padding: space.s5,
              borderRadius: radii.md,
              backgroundColor: `${colors.danger}1a`,
            }}
          >
            <Text style={{ fontFamily: fonts.sans.medium, fontSize: fontSizes.md, color: colors.danger }}>
              {error}
            </Text>
          </View>
        ) : null}

        <Button
          title={busy ? 'Pairing…' : 'Pair'}
          onPress={() => tryPair(text)}
          loading={busy}
          disabled={!text.trim() || busy}
          fullWidth
        />
      </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
