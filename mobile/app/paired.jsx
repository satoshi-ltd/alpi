import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { AppState, Linking, ScrollView, Text, View } from 'react-native';
import { ALPACA_FOLD, FOLD_SIZES } from '../../common/folds.mjs';
import { pairedRoleLine } from '../../common/onboarding.mjs';
import { mobile, space } from '../src/theme/tokens';
import { firstRun, firstRunActions, firstRunBottom, firstRunColumn, firstRunScroll, firstRunType, foldMarkStyle } from '../src/lib/firstRun';

import { Button } from '../src/components/Button';
import { Eyebrow } from '../src/components/Eyebrow';
import { Fold } from '../src/components/Fold';
import { OnOff } from '../src/components/OnOff';
import { Row, RowSeparator } from '../src/components/Row';
import { Toggle } from '../src/components/Toggle';
import { getPermissionStatus, requestPermission } from '../src/features/aln/notify';
import { PRIMER_FLAG, loadFlag, saveFlag } from '../src/features/aln/state';
import { useFirstRunLayout } from '../src/hooks/useFirstRunLayout';
import { authenticate, biometricCapabilities, getBiometricPref, setBiometricPref } from '../src/lib/biometric';
import { useTheme } from '../src/theme/ThemeContext';

export default function PairSuccess() {
  const router = useRouter();
  const { host, role, shared } = useLocalSearchParams();
  const theme = useTheme();
  const { colors } = theme;
  const { edge, insets } = useFirstRunLayout();
  const type = firstRunType(theme);
  const sharedCount = shared != null && shared !== '' ? Number(shared) : null;
  const [caps, setCaps] = useState(null);
  const [bioOn, setBioOn] = useState(false);
  const [alerts, setAlerts] = useState(null);

  useEffect(() => {
    biometricCapabilities().then(setCaps);
    getBiometricPref().then(setBioOn);
    getPermissionStatus().then(setAlerts);
  }, []);

  useEffect(() => {
    const sub = AppState.addEventListener('change', async (next) => {
      if (next !== 'active') return;
      const status = await getPermissionStatus();
      setAlerts(status);
      if (status === 'granted' && (await loadFlag(PRIMER_FLAG, null)) !== 'accepted') await saveFlag(PRIMER_FLAG, 'accepted');
    });
    return () => sub?.remove?.();
  }, []);

  const toggleBiometric = async (next) => {
    if (next) {
      if (!(await authenticate(`Enable ${caps.label} unlock`))) return false;
      await setBiometricPref(true);
    } else {
      await setBiometricPref(false);
    }
    setBioOn(next);
    return true;
  };

  const enableAlerts = async () => {
    let next;
    try {
      next = await requestPermission();
    } catch {
      return;
    }
    setAlerts(next);
    if (next === 'granted') await saveFlag(PRIMER_FLAG, 'accepted');
    else if (next === 'denied') await saveFlag(PRIMER_FLAG, 'declined');
  };

  const alertsControl = alerts === null ? null
    : alerts === 'granted' ? <OnOff on />
      : alerts === 'denied' ? <Button title="Open settings" variant="secondary" size="md" onPress={() => Linking.openSettings()} />
        : <Button title="Enable" variant="secondary" size="md" onPress={enableAlerts} />;

  const showFaceId = caps?.hasHardware && caps?.enrolled;
  const faceIdLabel = `${caps?.label} unlock`;

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScrollView style={{ flex: 1 }} contentContainerStyle={firstRunScroll(insets, edge)}>
        <View style={firstRunColumn}>
          <View style={foldMarkStyle}>
            <Fold fold={ALPACA_FOLD} size={FOLD_SIZES.hero} />
          </View>
          <Text accessibilityRole="header" style={type.title}>{host ? `Paired with ${host}` : 'Paired'}</Text>
          {role ? <Text style={type.fact}>{pairedRoleLine(role, sharedCount)}</Text> : null}
          <Text style={type.sentence}>Your daemon is reachable and your profiles are available.</Text>
          <View style={{ marginTop: firstRun.gap, gap: space.s3 }}>
            <Eyebrow>Optional</Eyebrow>
            <View accessibilityRole="list" style={{ marginHorizontal: -space.s7 }}>
              {showFaceId ? (
                <Row
                  label={faceIdLabel}
                  helper="required on cold start"
                  helperLines={4}
                  chevron={false}
                  value={(
                    <View style={{ minHeight: mobile.tap, minWidth: mobile.tap, justifyContent: 'center', alignItems: 'flex-end' }}>
                      <Toggle on={bioOn} label={faceIdLabel} onChange={toggleBiometric} />
                    </View>
                  )}
                />
              ) : null}
              {showFaceId ? <RowSeparator /> : null}
              <Row
                label="Notifications"
                helper="built on this phone from your daemon · no push service"
                helperLines={4}
                chevron={false}
                value={alertsControl}
              />
            </View>
          </View>
        </View>
      </ScrollView>
      <View style={firstRunBottom(insets, edge)}>
        <View style={firstRunActions}>
          <Button
            title="Open inbox"
            size="hero"
            fullWidth
            onPress={() => {
              if (router.canDismiss?.()) router.dismissAll();
              router.replace('/');
            }}
          />
        </View>
      </View>
    </View>
  );
}
