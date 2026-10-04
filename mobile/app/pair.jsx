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
import { useBack } from '../src/hooks/useBack';
import { useEndpoint } from '../src/lib/EndpointContext';
import { exchangePairing, pairingLinkFromParams, parsePairing } from '../src/lib/pairing';
import { RATE_LIMITED_STATUS } from '../src/lib/rateLimit';
import { probe } from '../src/lib/probe';
import { call } from '../src/lib/rpc';
import { useTheme } from '../src/theme/ThemeContext';
import { useWell } from '../src/components/well';
import { StepLadder, ladderSteps } from '../src/components/StepLadder';
import { PAIRING_STEPS, failedStep, pairingFailure, pairingFailureKind, pairingLinkHost, pairingStepLabel } from '../../common/onboarding.mjs';

export default function Pair() {
  const { colors, fonts, fontSizes, mobile } = useTheme();
  const [well, focus] = useWell(colors);
  const router = useRouter();
  const goBack = useBack();
  // addConnection keeps SecureStore and the provider's live connection list in sync.
  const { addConnection } = useEndpoint();
  const params = useLocalSearchParams();
  const routedLink = pairingLinkFromParams(params);
  const [mode, setMode] = useState(params.mode === 'scan' && !routedLink ? 'scan' : 'paste');
  const [text, setText] = useState(routedLink);
  const [busy, setBusy] = useState(false);
  const [current, setCurrent] = useState(null);
  const [failure, setFailure] = useState(null);
  const [permission, requestPermission] = useCameraPermissions();

  useEffect(() => {
    if (routedLink) setText(routedLink);
  }, [routedLink]);

  const fail = (kind, host, failedAt, savedNote) => {
    const next = pairingFailure(kind, host);
    setFailure(savedNote
      ? { ...next, hint: `${next.hint} This phone kept the connection.`, action: 'Open inbox', saved: true, host, at: failedAt ?? failedStep(next.kind) }
      : { ...next, host, at: failedAt ?? failedStep(next.kind) });
    if (!next.keepLink && !savedNote) setText('');
  };

  const editLink = (value) => {
    setText(value);
    setFailure(null);
    setCurrent(null);
  };

  const onPrimary = () => {
    if (failure?.saved) {
      if (router.canDismiss?.()) router.dismissAll();
      router.replace('/');
    } else if (!text.trim()) {
      setMode('scan');
    } else {
      tryPair(text);
    }
  };

  const tryPair = async (input) => {
    setBusy(true);
    setFailure(null);
    setCurrent('read');
    const host = pairingLinkHost(input);
    let exchangedCredentialSaved = false;
    let endpoint;
    try {
      endpoint = parsePairing(input);
    } catch {
      fail('invalid', host, 'read');
      setBusy(false);
      return;
    }
    try {
      setCurrent('reach');
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
      const { status, deviceName, deviceId, role, summaries } = await probe(endpoint);
      if (status === 'auth-failed') return fail('link-used', host, 'sign-in', exchangedCredentialSaved);
      if (status === 'disabled') return fail('disabled', host, 'sign-in', exchangedCredentialSaved);
      if (status === RATE_LIMITED_STATUS) return fail('rate-limited', host, 'reach', exchangedCredentialSaved);
      if (status !== 'online') return fail('unreachable', host, 'reach', exchangedCredentialSaved);
      if (!deviceId) return fail('too-old', host, 'sign-in', exchangedCredentialSaved);
      setCurrent('sign-in');
      await call(endpoint, 'host.connections.register_device', {
        client: 'mobile',
        name: clientName,
        app_version: appVersion,
      }).catch(() => {});
      const finalEndpoint = { ...endpoint, deviceId, ...(deviceName ? { name: deviceName } : {}) };
      await addConnection(finalEndpoint);
      setCurrent('done');
      const shared = Array.isArray(summaries?.profiles) ? summaries.profiles.length : Array.isArray(summaries) ? summaries.length : null;
      router.replace({
        pathname: '/paired',
        params: { host: finalEndpoint.name ?? host ?? '', role: role ?? '', ...(shared != null ? { shared: String(shared) } : {}) },
      });
    } catch (e) {
      fail(pairingFailureKind(e), host, null, exchangedCredentialSaved);
    } finally {
      setBusy(false);
    }
  };

  const handlePaste = async () => {
    const clip = await Clipboard.getStringAsync();
    if (clip) editLink(clip);
  };

  const handleScan = async ({ data }) => {
    if (busy) return;
    setMode('paste');
    setText(data);
    await tryPair(data);
  };

  const ladderHost = pairingLinkHost(text) ?? failure?.host;
  const steps = current
    ? ladderSteps(PAIRING_STEPS, current, failure ? failure.at : null, (id) => pairingStepLabel(id, ladderHost))
    : null;

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
                borderRadius: radii.xs,
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
              ...well,
              padding: space.s5,
            }}
          >
            <TextInput
              value={text}
              onChangeText={editLink}
              placeholder="alpi://device?url=wss://…&name=…&pairing_token=…"
              placeholderTextColor={colors.ink4}
              {...focus}
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

        {steps ? (
          <View style={{ padding: space.s6, borderRadius: radii.xs, backgroundColor: colors.hover, gap: space.s5 }}>
            <StepLadder steps={steps} />
            {failure ? (
              <View accessibilityRole="alert" style={{ gap: space.s2 }}>
                <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.lg, color: colors.ink }}>{failure.title}</Text>
                <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.md, lineHeight: fontSizes.md * lineHeights.normal, color: colors.ink2 }}>{failure.hint}</Text>
              </View>
            ) : null}
          </View>
        ) : null}

        <Button
          title={busy ? 'Pairing…' : failure ? failure.action : 'Pair'}
          onPress={onPrimary}
          loading={busy}
          disabled={busy || (!text.trim() && !failure)}
          fullWidth
        />
      </ScrollView>
      </KeyboardPane>
    </SafeAreaView>
  );
}
