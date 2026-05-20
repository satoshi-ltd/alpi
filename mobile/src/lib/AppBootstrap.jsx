import { useRouter, useSegments } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, Text, View } from 'react-native';
import { radii, space , fontSizes} from '../theme/tokens';

import { AlpiMark } from '../components/AlpiMark';
import { authenticate, biometricCapabilities, getBiometricPref } from './biometric';
import { useEndpoint } from './EndpointContext';
import { useTheme } from '../theme/ThemeContext';

export function AppBootstrap({ children }) {
  const router = useRouter();
  const segments = useSegments();
  const firstSegment = segments[0];
  const { colors, fonts, fontSizes } = useTheme();
  // connections + ready come from EndpointProvider — already kept in sync by addConnection/forget/unpair, so post-pairing redirects react to the live count instead of a stale loadConnections() snapshot.
  const { ready: endpointReady, connections } = useEndpoint();
  const hasConn = (connections?.length ?? 0) > 0;
  const [bioChecked, setBioChecked] = useState(false);
  const [locked, setLocked] = useState(false);
  const [bioLabel, setBioLabel] = useState('Biometric');

  // Cold-start biometric prompt only — must not depend on route or connection state.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const bioOn = await getBiometricPref();
      if (bioOn) {
        const caps = await biometricCapabilities();
        if (caps.hasHardware && caps.enrolled) {
          setBioLabel(caps.label);
          setLocked(true);
          const ok = await authenticate(`Unlock alpi with ${caps.label}`);
          if (!cancelled && ok) setLocked(false);
        }
      }
      if (!cancelled) setBioChecked(true);
    })();
    return () => { cancelled = true; };
  }, []);

  const ready = bioChecked && endpointReady;

  useEffect(() => {
    if (!ready) return;
    const allowWhileUnpaired = firstSegment === 'pair' || firstSegment === 'onboarding';
    if (!hasConn && !allowWhileUnpaired) router.replace('/onboarding');
  }, [ready, hasConn, firstSegment, router]);

  if (!ready) {
    return (
      <View
        style={{
          flex: 1,
          backgroundColor: colors.bg,
          alignItems: 'center',
          justifyContent: 'center',
          gap: space.s9,
        }}
      >
        <AlpiMark color={colors.ink} size={64} />
        <ActivityIndicator color={colors.ink2} />
        <Text
          style={{
            fontFamily: fonts.mono,
            fontSize: fontSizes.xs,
            color: colors.ink3,
            letterSpacing: 0.6,
          }}
        >
          CONNECTING…
        </Text>
      </View>
    );
  }

  if (locked) {
    return (
      <View
        style={{
          flex: 1,
          backgroundColor: colors.bg,
          alignItems: 'center',
          justifyContent: 'center',
          gap: space.s9,
        }}
      >
        <AlpiMark color={colors.ink} size={72} />
        <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.hLg, color: colors.ink }}>Locked</Text>
        <Text
          style={{
            fontFamily: fonts.sans.regular,
            fontSize: fontSizes.md,
            color: colors.ink2,
            textAlign: 'center',
            paddingHorizontal: space.s11,
          }}
        >
          {`Authenticate with ${bioLabel} to open alpi.`}
        </Text>
        <Pressable
          onPress={async () => {
            const ok = await authenticate(`Unlock alpi with ${bioLabel}`);
            if (ok) setLocked(false);
          }}
          style={{
            paddingHorizontal: space.s9,
            paddingVertical: space.s6,
            backgroundColor: colors.ink,
            borderRadius: radii.md,
          }}
        >
          <Text style={{ fontFamily: fonts.sans.medium, fontSize: fontSizes.md, color: colors.bgPane }}>
            Unlock
          </Text>
        </Pressable>
      </View>
    );
  }

  return children;
}
