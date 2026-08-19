import Constants from 'expo-constants';
import { useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { alpha, mobile, radii, space } from '../../theme/tokens';

import { Eyebrow } from '../../components/Eyebrow';
import { OnOff } from '../../components/OnOff';
import { Row, RowSeparator, SectionHeader } from '../../components/Row';
import { useToast } from '../../components/Toast';
import { Bold, Code, TypedConfirm } from '../../components/TypedConfirm';
import {
  authenticate,
  biometricCapabilities,
  getBiometricPref,
  setBiometricPref,
} from '../../lib/biometric';
import { useEndpoint } from '../../lib/EndpointContext';
import { signOut } from '../../lib/signOut';
import { getPermissionStatus, requestPermission } from '../aln/notify';
import { useTheme } from '../../theme/ThemeContext';
import {
  DEFAULT_TEXT_SCALE,
  MAX_TEXT_SCALE,
  MIN_TEXT_SCALE,
  stepTextScale,
  textScaleLabel,
} from '../../theme/textScale';

const APP_VERSION = Constants.expoConfig?.version ?? '0.0.0';

function StatusValue({ active, label = 'on', mutedLabel = 'off', disabled = false }) {
  return <OnOff on={!disabled && !!active} onLabel={label} offLabel={mutedLabel} />;
}

function StepButton({ glyph, label, disabled, onPress }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityLabel={label}
      style={({ pressed }) => ({
        width: mobile.tap,
        height: mobile.tap,
        alignItems: 'center',
        justifyContent: 'center',
        borderRadius: radii.md,
        backgroundColor: pressed && !disabled ? colors.selected : colors.bgInput,
        opacity: disabled ? alpha.disabled : 1,
      })}
    >
      <Text style={{ fontFamily: fonts.sans.medium, fontSize: fontSizes.xl, color: colors.ink2 }}>
        {glyph}
      </Text>
    </Pressable>
  );
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

  const [bioOn, setBioOn] = useState(false);
  const [bioCaps, setBioCaps] = useState({ hasHardware: false, enrolled: false, label: 'Biometric' });
  const [confirmSignOut, setConfirmSignOut] = useState(false);
  const [notifPerm, setNotifPerm] = useState('undetermined');

  useEffect(() => {
    if (!active) return;
    biometricCapabilities().then(setBioCaps);
    getBiometricPref().then(setBioOn);
    getPermissionStatus().then(setNotifPerm);
  }, [active]);

  const onPermissionPress = async () => {
    if (notifPerm === 'granted') {
      toast?.({
        title: 'Already granted',
        message: 'Revoke in iOS / Android system settings.',
        duration: 2400,
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

  const cycleAppearance = () => {
    const next = pref === 'system' ? 'light' : pref === 'light' ? 'dark' : 'system';
    setMode(next);
  };

  const appearanceLabel =
    pref === 'system' ? 'System' : pref === 'light' ? 'Light' : 'Dark';

  const handleSignOut = async () => {
    setConfirmSignOut(false);
    onDismiss?.();
    await signOut();
    try { await unpair?.(); } catch {}
    toast({ title: 'Signed out', message: 'All local data cleared', duration: 1800 });
    router.replace('/onboarding');
  };

  const toggleBiometric = async () => {
    if (!bioCaps.hasHardware) {
      toast({ title: 'Not available', message: 'This device has no biometric hardware.', duration: 2400 });
      return;
    }
    if (!bioCaps.enrolled) {
      toast({ title: 'Not enrolled', message: `Set up ${bioCaps.label} in your OS settings first.`, duration: 2400 });
      return;
    }
    if (!bioOn) {
      const ok = await authenticate(`Enable ${bioCaps.label} unlock`);
      if (!ok) return;
      await setBiometricPref(true);
      setBioOn(true);
      toast({ title: `${bioCaps.label} on`, duration: 1800 });
    } else {
      await setBiometricPref(false);
      setBioOn(false);
    }
  };

  return (
    <>
      <ScrollView contentContainerStyle={{ paddingBottom: space.s9 }}>
        <SectionHeader>This phone</SectionHeader>
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
          value={<StatusValue active={bioOn} label="on" disabled={!bioCaps.hasHardware} />}
          onPress={toggleBiometric}
          chevron={false}
        />

        <SectionHeader>Notifications</SectionHeader>
        <Row
          label="System permission"
          helper="ambient background updates · zero relay · ~15–60 min cadence"
          value={<StatusValue active={notifPerm === 'granted'} />}
          onPress={onPermissionPress}
          chevron={notifPerm !== 'granted'}
        />
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

        <SectionHeader>Appearance</SectionHeader>
        <Row label="Theme" value={appearanceLabel} onPress={cycleAppearance} />
        <RowSeparator />
        <Row
          label="Text size"
          helper="multiplies your OS text size · long-press to reset"
          value={textScaleLabel(textScale)}
          onLongPress={() => setTextScale?.(DEFAULT_TEXT_SCALE)}
          chevron={false}
          trailing={
            <View style={{ flexDirection: 'row', gap: space.s3 }}>
              <StepButton
                glyph="−"
                label="Smaller text"
                disabled={textScale <= MIN_TEXT_SCALE}
                onPress={() => setTextScale?.(stepTextScale(textScale, -1))}
              />
              <StepButton
                glyph="+"
                label="Larger text"
                disabled={textScale >= MAX_TEXT_SCALE}
                onPress={() => setTextScale?.(stepTextScale(textScale, 1))}
              />
            </View>
          }
        />

        <SectionHeader>Danger zone</SectionHeader>
        <Row
          label="Sign out"
          helper="forgets every daemon + clears pins, prefs, biometric. The app reverts to first-install."
          danger
          chevron={false}
          onPress={() => setConfirmSignOut(true)}
        />

        <View
          style={{
            paddingHorizontal: space.s8,
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
      </ScrollView>

      <TypedConfirm
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
