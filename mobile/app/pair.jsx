import { CameraView, useCameraPermissions } from 'expo-camera';
import * as Clipboard from 'expo-clipboard';
import Constants from 'expo-constants';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { Platform, Pressable, ScrollView, Text, TextInput, View } from 'react-native';
import { KeyboardPane } from '../src/components/KeyboardPane';
import { SafeAreaView } from 'react-native-safe-area-context';
import { radii, space, lineHeights } from '../src/theme/tokens';

import { Button } from '../src/components/Button';
import { Eyebrow } from '../src/components/Eyebrow';
import { Icon } from '../src/components/Icon';
import { useToast } from '../src/components/Toast';
import { useBack } from '../src/hooks/useBack';
import { useEndpoint } from '../src/lib/EndpointContext';
import { exchangePairing, pairingLinkFromParams, parsePairing, PairingError } from '../src/lib/pairing';
import { probe } from '../src/lib/probe';
import { call } from '../src/lib/rpc';
import { useTheme } from '../src/theme/ThemeContext';

export default function Pair() {
  const { colors, fonts, fontSizes, mobile } = useTheme();
  const router = useRouter();
  const goBack = useBack();
  const toast = useToast();
  // addConnection keeps SecureStore and the provider's live connection list in sync.
  const { addConnection } = useEndpoint();
  const params = useLocalSearchParams();
  const routedLink = pairingLinkFromParams(params);
  const [mode, setMode] = useState('paste');
  const [text, setText] = useState(routedLink);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [permission, requestPermission] = useCameraPermissions();

  useEffect(() => {
    if (routedLink) setText(routedLink);
  }, [routedLink]);

  const tryPair = async (input) => {
    setBusy(true);
    setError(null);
    let exchangedCredentialSaved = false;
    try {
      let endpoint = parsePairing(input);
      const usesOneTimeGrant = Boolean(endpoint.pairingToken);
      const clientName = Platform.constants?.Model || Platform.OS;
      const appVersion = Constants.expoConfig?.version || '';
      endpoint = await exchangePairing(endpoint, {
        name: clientName,
        appVersion,
      }, call, addConnection);
      if (usesOneTimeGrant) {
        exchangedCredentialSaved = true;
      }
      const { status, deviceName, deviceId } = await probe(endpoint);
      if (status === 'auth-failed') {
        throw new PairingError('Token rejected by daemon. Generate a fresh pairing link on the daemon and try again.');
      }
      if (status === 'disabled') {
        throw new PairingError('Connection disabled by host. Ask an admin to enable it in Settings → Connections.');
      }
      if (status !== 'online') {
        throw new PairingError(`Daemon unreachable at ${endpoint.url}. Make sure the daemon is running, the route is reachable, and the port is open.`);
      }
      if (!deviceId) {
        throw new PairingError('Daemon too old or host.version unavailable. Update alpi to v0.6.6 or newer and retry.');
      }
      await call(endpoint, 'host.connections.register_device', {
        client: 'mobile',
        name: clientName,
        app_version: appVersion,
      }).catch(() => {});
      const finalEndpoint = { ...endpoint, deviceId, ...(deviceName ? { name: deviceName } : {}) };
      await addConnection(finalEndpoint);
      toast({ title: 'Paired', message: `Connected to ${finalEndpoint.name}`, duration: 2200 });
      router.replace('/paired');
    } catch (e) {
      const message = e?.message ?? 'Pairing failed';
      setError(exchangedCredentialSaved
        ? `Pairing credential saved. ${message}`
        : message);
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
              <Icon name="back" size="lg" color="#fff" />
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
                borderRadius: radii.xl,
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
        <Pressable onPress={goBack} hitSlop={12}>
          <Icon name="back" size="lg" color={colors.ink} />
        </Pressable>
        <View style={{ flex: 1 }}>
          <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.xl, color: colors.ink }}>
            Pair this phone
          </Text>
          <Eyebrow style={{ marginTop: space.s1 }}>Connect to your daemon</Eyebrow>
        </View>
      </View>

      <KeyboardPane>
      <ScrollView contentContainerStyle={{ padding: space.s8, gap: space.s8 }} keyboardShouldPersistTaps="handled">
        <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.md, color: colors.ink2, lineHeight: fontSizes.md * lineHeights.normal }}>
          Open your daemon's settings, choose{' '}
          <Text style={{ fontFamily: fonts.mono, color: colors.ink }}>Settings → Connections → New connection / Add device</Text>, then either
          scan the QR or paste the <Text style={{ fontFamily: fonts.mono, color: colors.ink }}>alpi://</Text> link below.
        </Text>

        <Button title="Scan QR" onPress={() => setMode('scan')} fullWidth />

        <View style={{ gap: space.s3 }}>
          <Eyebrow>or paste link</Eyebrow>
          <View
            style={{
              backgroundColor: colors.bgPane,
              borderRadius: radii.xl,
              borderWidth: 0.5,
              borderColor: colors.line2,
              padding: space.s5,
            }}
          >
            <TextInput
              value={text}
              onChangeText={setText}
              placeholder="alpi://device?url=wss://…&name=…&pairing_token=…"
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
              borderRadius: radii.lg,
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
      </KeyboardPane>
    </SafeAreaView>
  );
}
