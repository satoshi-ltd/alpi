import Constants from 'expo-constants';
import { useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { ScrollView, Text, View } from 'react-native';
import { space } from '../../theme/tokens';

import { ALPACA_FOLD } from '../../../../common/folds.mjs';
import { Crease } from '../../components/Crease';
import { Eyebrow } from '../../components/Eyebrow';
import { Fold } from '../../components/Fold';
import { OnOff } from '../../components/OnOff';
import { Pill } from '../../components/Pill';
import { Row, RowGroup, RowSeparator, SectionHeader } from '../../components/Row';
import { Segmented } from '../../components/Segmented';
import { Toggle } from '../../components/Toggle';
import { useToast } from '../../components/Toast';
import { Bold, Code, ConfirmDialog } from '../../components/ConfirmDialog';
import {
  authenticate,
  biometricCapabilities,
  getBiometricPref,
  setBiometricPref,
} from '../../lib/biometric';
import { useEndpoint } from '../../lib/EndpointContext';
import { signOut } from '../../lib/signOut';
import { describeHealth, readHealth } from '../aln/health';
import { getPermissionStatus, requestPermission } from '../aln/notify';
import { useIsAdmin } from '../../hooks/useActiveRole';
import { useTheme } from '../../theme/ThemeContext';
import { clampTextScale, DEFAULT_TEXT_SCALE, TEXT_SCALES } from '../../theme/textScale';

const APP_VERSION = Constants.expoConfig?.version ?? '0.0.0';

const THEME_OPTIONS = [
  { value: 'system', label: 'System' },
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
];

const TEXT_SIZE_OPTIONS = TEXT_SCALES.map((step) => ({ value: step.value, label: step.label }));

function DeliveryValue({ ok }) {
  return ok ? <OnOff on /> : <Pill tone="err">blocked</Pill>;
}

export function SettingsBody({ active = true, onDismiss }) {
  const {
    pref,
    setMode,
    colors,
    fonts,
    fontSizes,
    textScale = DEFAULT_TEXT_SCALE,
    setTextScale,
  } = useTheme();
  const router = useRouter();
  const toast = useToast();
  const { unpair } = useEndpoint();
  const isAdmin = useIsAdmin();

  const [bioOn, setBioOn] = useState(false);
  const [bioCaps, setBioCaps] = useState({ hasHardware: false, enrolled: false, label: 'Biometric' });
  const [confirmSignOut, setConfirmSignOut] = useState(false);
  const [notifPerm, setNotifPerm] = useState('undetermined');
  const [notifHealth, setNotifHealth] = useState(null);

  useEffect(() => {
    if (!active) return;
    biometricCapabilities().then(setBioCaps);
    getBiometricPref().then(setBioOn);
    getPermissionStatus().then(setNotifPerm);
    readHealth().then((h) => setNotifHealth(describeHealth(h))).catch(() => setNotifHealth(null));
  }, [active, notifPerm]);

  const onPermissionPress = async () => {
    if (notifPerm === 'granted') {
      toast?.({
        title: 'Already granted',
        message: 'Revoke in iOS / Android system settings.',
      });
      return;
    }
    const next = await requestPermission();
    setNotifPerm(next);
  };

  const navigate = (path) => {
    onDismiss?.();
    router.push(path);
  };

  const handleSignOut = async () => {
    setConfirmSignOut(false);
    onDismiss?.();
    await signOut();
    try { await unpair?.(); } catch {}
    toast({ title: 'Signed out', message: 'All local data cleared' });
    router.replace('/onboarding');
  };

  const toggleBiometric = async (next) => {
    if (!bioCaps.hasHardware) {
      toast({ title: 'Not available', message: 'This device has no biometric hardware.' });
      return false;
    }
    if (!bioCaps.enrolled) {
      toast({ title: 'Not enrolled', message: `Set up ${bioCaps.label} in your OS settings first.` });
      return false;
    }
    if (next) {
      const ok = await authenticate(`Enable ${bioCaps.label} unlock`);
      if (!ok) return false;
      await setBiometricPref(true);
      setBioOn(true);
      toast({ title: `${bioCaps.label} on` });
      return true;
    }
    await setBiometricPref(false);
    setBioOn(false);
    return true;
  };

  return (
    <>
      <ScrollView contentContainerStyle={{ paddingBottom: space.s9 }}>
        <SectionHeader>This phone</SectionHeader>
        <RowGroup>
          <Row label="Re-pair this phone" helper="opens QR scanner" onPress={() => navigate('/pair')} />
          <RowSeparator />
          <Row
            label={`${bioCaps.label} unlock`}
            helper={
              bioCaps.hasHardware
                ? bioCaps.enrolled
                  ? 'required on cold start'
                  : 'not enrolled in OS settings'
                : 'not available on this device'
            }
            value={<Toggle on={bioOn} label={`${bioCaps.label} unlock`} disabled={!bioCaps.hasHardware} onChange={toggleBiometric} />}
            chevron={false}
          />
        </RowGroup>

        {isAdmin ? (
          <>
            <SectionHeader>Daemon</SectionHeader>
            <RowGroup>
              <Row
                label="Connections"
                helper="paired apps, devices, pairing links, usage"
                onPress={() => navigate('/connections')}
              />
            </RowGroup>
          </>
        ) : null}

        <SectionHeader>Notifications</SectionHeader>
        <RowGroup>
          <Row
            label="System permission"
            helper="instant while alpi is open · in the background the OS decides when to check"
            value={<OnOff on={notifPerm === 'granted'} />}
            onPress={onPermissionPress}
            chevron={notifPerm !== 'granted'}
          />
          {notifHealth && (
            <>
              <RowSeparator />
              <Row
                label="Delivery status"
                helper={notifHealth.detail}
                value={<DeliveryValue ok={notifHealth.ok} />}
                chevron={false}
              />
            </>
          )}
          {__DEV__ && (
            <>
              <RowSeparator />
              <Row
                label="Test notifications"
                helper="dev-only · sample notifications + routing check"
                onPress={() => navigate('/debug/aln')}
              />
            </>
          )}
        </RowGroup>

        <SectionHeader>Appearance</SectionHeader>
        <RowGroup>
          <Row label="Theme" below={<Segmented label="Theme" options={THEME_OPTIONS} value={pref} onChange={setMode} />} />
          <RowSeparator />
          <Row
            label="Text size"
            helper="multiplies your OS text size"
            below={
              <Segmented
                label="Text size"
                options={TEXT_SIZE_OPTIONS}
                value={clampTextScale(textScale)}
                onChange={(next) => setTextScale?.(next)}
              />
            }
          />
        </RowGroup>

        <SectionHeader>Danger zone</SectionHeader>
        <RowGroup>
          <Row
            label="Sign out"
            helper="forgets every daemon + clears pins, prefs, biometric. The app reverts to first-install."
            danger
            chevron={false}
            onPress={() => setConfirmSignOut(true)}
          />
        </RowGroup>

        <View
          style={{
            paddingHorizontal: space.s7,
            paddingTop: space.s9,
            paddingBottom: space.s3,
            flexDirection: 'row',
            justifyContent: 'space-between',
            alignItems: 'baseline',
          }}
        >
          <Eyebrow>About</Eyebrow>
          <Text style={{ fontFamily: fonts.monoMedium, fontSize: fontSizes.xs, color: colors.ink4 }}>
            Alpi mobile · v{APP_VERSION}
          </Text>
        </View>
        <View style={{ paddingHorizontal: space.s7, paddingBottom: space.s9, flexDirection: 'row', alignItems: 'center', gap: space.s4 }}>
          <Fold fold={ALPACA_FOLD} size={36} />
          <Crease text="alpi" accent={colors.accent} size={32} />
        </View>
      </ScrollView>

      <ConfirmDialog
        open={confirmSignOut}
        onClose={() => setConfirmSignOut(false)}
        title="Sign out of this phone?"
        body={
          <>
            Forgets every paired daemon and wipes <Code>pins</Code>,{' '}
            <Code>biometric</Code> and the local theme and text size from this device. Your daemons and alpis stay untouched on their hosts —
            you&apos;ll just need to re-pair. <Bold>This action cannot be undone.</Bold>
          </>
        }
        expected="sign out"
        confirmLabel="Sign out"
        onConfirm={handleSignOut}
      />
    </>
  );
}
