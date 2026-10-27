import { CameraView, useCameraPermissions } from 'expo-camera';
import * as Clipboard from 'expo-clipboard';
import Constants from 'expo-constants';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useMemo, useRef, useState } from 'react';
import { AppState, Keyboard, Linking, Platform, ScrollView, Text, TextInput, View } from 'react-native';
import { ALPACA_FOLD, FOLD_SIZES } from '../../common/folds.mjs';
import { LINK_SOURCE_ROWS, PAIRING_STEPS, failedStep, pairingFailure, pairingFailureKind, pairingLinkHost, pairingStepLabel } from '../../common/onboarding.mjs';
import { KeyboardPane } from '../src/components/KeyboardPane';
import { palettes, space } from '../src/theme/tokens';
import {
  BUSY_MARK_PX,
  busyMarkStyle,
  firstRun,
  firstRunActions,
  firstRunBottom,
  firstRunColumn,
  firstRunScroll,
  firstRunType,
  foldMarkStyle,
} from '../src/lib/firstRun';

import { Busy } from '../src/components/Busy';
import { Button } from '../src/components/Button';
import { Eyebrow } from '../src/components/Eyebrow';
import { Fold } from '../src/components/Fold';
import { StepLadder, ladderSteps } from '../src/components/StepLadder';
import { useWell } from '../src/components/well';
import { useFirstRunLayout, useKeyboardOpen } from '../src/hooks/useFirstRunLayout';
import { useEndpoint } from '../src/lib/EndpointContext';
import { exchangePairing, pairingLinkFact, pairingLinkFromParams, parsePairing } from '../src/lib/pairing';
import { RATE_LIMITED_STATUS } from '../src/lib/rateLimit';
import { isSpentPairing, rememberSpentPairing } from '../src/lib/spentPairings';
import { probe } from '../src/lib/probe';
import { call } from '../src/lib/rpc';
import { ThemeContext, useTheme } from '../src/theme/ThemeContext';

const CAMERA_GROUND = '#000';

export default function Pair() {
  const theme = useTheme();
  const { colors, fonts, fontSizes } = theme;
  const [well, focus] = useWell(colors);
  const router = useRouter();
  const { edge, insets } = useFirstRunLayout();
  const keyboardOpen = useKeyboardOpen();
  const type = firstRunType(theme);
  const fieldRef = useRef(null);
  // addConnection keeps SecureStore and the provider's live connection list in sync.
  const { addConnection, connections } = useEndpoint();
  const hasConnection = (connections?.length ?? 0) > 0;
  const inFlight = useRef(false);
  const mounted = useRef(true);
  const params = useLocalSearchParams();
  const routedLink = pairingLinkFromParams(params);
  const [mode, setMode] = useState(params.mode === 'scan' && !routedLink ? 'scan' : 'paste');
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [current, setCurrent] = useState(null);
  const [failure, setFailure] = useState(null);
  const [permission, requestPermission, getPermission] = useCameraPermissions();
  const darkTheme = useMemo(() => ({ ...theme, mode: 'dark', colors: palettes.dark }), [theme]);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => {
    if (!routedLink) return undefined;
    let cancelled = false;
    isSpentPairing(params.pairing_token ?? params.token).then((spent) => {
      if (cancelled) return;
      if (spent) {
        const host = pairingLinkHost(routedLink);
        setFailure({ ...pairingFailure('link-used', host), host, at: 'sign-in' });
        setCurrent('sign-in');
        return;
      }
      setText(routedLink);
    });
    return () => { cancelled = true; };
  }, [routedLink]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (failure && !failure.keepLink && !failure.saved && !text) fieldRef.current?.focus?.();
  }, [failure]);

  useEffect(() => {
    if (mode !== 'scan' || permission?.granted || !getPermission) return undefined;
    const sub = AppState.addEventListener('change', (next) => {
      if (next === 'active') getPermission();
    });
    return () => sub?.remove?.();
  }, [mode, permission?.granted, getPermission]);

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
    } else if (failure && !failure.keepLink) {
      editLink('');
      fieldRef.current?.focus?.();
    } else if (text.trim()) {
      tryPair(text);
    }
  };

  const tryPair = async (input) => {
    if (inFlight.current) return;
    inFlight.current = true;
    Keyboard.dismiss();
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
      inFlight.current = false;
      return;
    }
    try {
      setCurrent('reach');
      const grant = endpoint.pairingToken;
      const usesOneTimeGrant = Boolean(grant);
      const clientName = Platform.constants?.Model || Platform.OS;
      const appVersion = Constants.expoConfig?.version || '';
      endpoint = await exchangePairing(endpoint, {
        name: clientName,
        appVersion,
      }, call, addConnection);
      if (usesOneTimeGrant) {
        exchangedCredentialSaved = true;
        rememberSpentPairing(grant);
      }
      const { status, deviceName, deviceId, role, summaries } = await probe(endpoint);
      if (status === 'auth-failed') {
        rememberSpentPairing(grant);
        return fail('link-used', host, 'sign-in', exchangedCredentialSaved);
      }
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
      if (!mounted.current) return;
      const shared = Array.isArray(summaries?.profiles) ? summaries.profiles.length : Array.isArray(summaries) ? summaries.length : null;
      router.replace({
        pathname: '/paired',
        params: { host: finalEndpoint.name ?? host ?? '', role: role ?? '', ...(shared != null ? { shared: String(shared) } : {}) },
      });
    } catch (e) {
      fail(pairingFailureKind(e), host, null, exchangedCredentialSaved);
    } finally {
      setBusy(false);
      inFlight.current = false;
    }
  };

  const handlePaste = async () => {
    const clip = await Clipboard.getStringAsync();
    if (clip) editLink(clip);
  };

  const handleScan = async ({ data }) => {
    if (busy || inFlight.current) return;
    setMode('paste');
    setText(data);
    await tryPair(data);
  };

  const ladderHost = pairingLinkHost(text) ?? failure?.host;
  const steps = current
    ? ladderSteps(PAIRING_STEPS, current, failure ? failure.at : null, (id) => pairingStepLabel(id, ladderHost))
    : null;
  const fact = pairingLinkFact(text);

  if (mode === 'scan' && permission?.granted) {
    const dark = darkTheme.colors;
    return (
      <View style={{ flex: 1, backgroundColor: CAMERA_GROUND }}>
        <View style={{ paddingTop: insets.top + space.s7, paddingHorizontal: edge, paddingBottom: space.s7, gap: space.s1 }}>
          <Text accessibilityRole="header" style={{ color: dark.ink, fontFamily: fonts.sans.semibold, fontSize: fontSizes.md }}>
            Pair this phone
          </Text>
          <Text style={{ color: dark.ink3, fontFamily: fonts.mono, fontSize: fontSizes.xs }}>
            Scan the QR shown on your daemon
          </Text>
        </View>
        <CameraView
          onBarcodeScanned={busy ? undefined : handleScan}
          barcodeScannerSettings={{ barcodeTypes: ['qr'] }}
          style={{ flex: 1 }}
        />
        <View style={firstRunBottom(insets, edge)}>
          <View style={firstRunColumn}>
            <ThemeContext.Provider value={darkTheme}>
              <Button title="Paste link" variant="secondary" size="lg" fullWidth onPress={() => setMode('paste')} />
            </ThemeContext.Provider>
          </View>
        </View>
      </View>
    );
  }

  if (mode === 'scan' && !permission) return <View style={{ flex: 1, backgroundColor: colors.bg }} />;

  if (mode === 'scan') {
    const blocked = permission?.canAskAgain === false;
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg }}>
        <ScrollView style={{ flex: 1 }} contentContainerStyle={firstRunScroll(insets, edge)}>
          <View style={firstRunColumn}>
            <View style={foldMarkStyle}>
              <Fold fold={ALPACA_FOLD} size={FOLD_SIZES.hero} />
            </View>
            <Text accessibilityRole="header" style={type.title}>Pair this phone</Text>
            <Text style={type.fact}>camera · not allowed</Text>
            <Text style={type.sentence}>Camera permission needed to scan the pairing QR.</Text>
          </View>
        </ScrollView>
        <View style={firstRunBottom(insets, edge)}>
          <View style={firstRunActions}>
            <Button
              title={blocked ? 'Open settings' : 'Grant access'}
              size="hero"
              fullWidth
              onPress={blocked ? () => Linking.openSettings() : requestPermission}
            />
            <Button title="Paste link" variant="ghost" fullWidth onPress={() => setMode('paste')} />
          </View>
        </View>
      </View>
    );
  }

  const primaryTitle = failure ? failure.action : 'Pair';

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <KeyboardPane>
        <ScrollView style={{ flex: 1 }} contentContainerStyle={firstRunScroll(insets, edge)} keyboardShouldPersistTaps="handled">
          <View style={firstRunColumn}>
            {keyboardOpen ? null : busy ? (
              <Busy visible size={BUSY_MARK_PX} style={busyMarkStyle} />
            ) : (
              <View style={foldMarkStyle}>
                <Fold fold={ALPACA_FOLD} size={FOLD_SIZES.hero} />
              </View>
            )}
            <Text accessibilityRole="header" style={[type.title, keyboardOpen ? { marginTop: 0 } : null]}>Pair this phone</Text>
            {fact ? <Text style={type.fact}>{fact}</Text> : null}
            <View style={{ marginTop: firstRun.gap, gap: space.s3 }}>
              <Eyebrow>alpi:// link</Eyebrow>
              <View style={{ ...well, padding: space.s5 }}>
                <TextInput
                  ref={fieldRef}
                  value={text}
                  onChangeText={editLink}
                  editable={!busy}
                  accessibilityLabel="alpi:// link"
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
            </View>
            {steps ? (
              <View style={{ marginTop: firstRun.stack, gap: firstRun.stack }}>
                <StepLadder steps={steps} />
                {failure ? (
                  <View accessibilityRole="alert" style={{ gap: space.s2 }}>
                    <Text style={type.failureTitle}>{failure.title}</Text>
                    <Text style={type.failureHint}>{failure.hint}</Text>
                  </View>
                ) : null}
              </View>
            ) : (
              <>
                <View style={{ marginTop: firstRun.tight, marginLeft: -space.s6, alignSelf: 'flex-start' }}>
                  <Button title="Paste from clipboard" variant="ghost" size="md" onPress={handlePaste} />
                </View>
                {keyboardOpen ? null : (
                  <View style={{ marginTop: firstRun.stack, gap: space.s3 }}>
                    {LINK_SOURCE_ROWS.map(({ label, path }) => (
                      <View key={label}>
                        <Text style={type.sourceLabel}>{label}</Text>
                        <Text style={type.sourcePath}>{path}</Text>
                      </View>
                    ))}
                  </View>
                )}
              </>
            )}
          </View>
        </ScrollView>
        {busy ? null : (
          <View style={firstRunBottom(insets, edge, keyboardOpen)}>
            <View style={firstRunActions}>
              <Button title={primaryTitle} size="hero" fullWidth disabled={!text.trim() && !failure} onPress={onPrimary} />
              {failure?.saved ? null : <Button title="Scan QR" variant="ghost" fullWidth onPress={() => setMode('scan')} />}
              {failure?.saved || !hasConnection ? null : <Button title="Open inbox" variant="ghost" fullWidth onPress={() => router.replace('/')} />}
            </View>
          </View>
        )}
      </KeyboardPane>
    </View>
  );
}
