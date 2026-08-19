import { useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { radii, space } from '../src/theme/tokens';

import { Pill } from '../src/components/Pill';
import { Row, RowSeparator, SectionHeader } from '../src/components/Row';
import { ScreenHeader } from '../src/components/ScreenHeader';
import { useToast } from '../src/components/Toast';
import { authenticate, biometricCapabilities, getBiometricPref, setBiometricPref } from '../src/lib/biometric';
import { useTheme } from '../src/theme/ThemeContext';

export default function BiometricSettings() {
  const router = useRouter();
  const toast = useToast();
  const { colors, fonts, fontSizes } = useTheme();
  const [caps, setCaps] = useState({ hasHardware: false, enrolled: false, label: 'Biometric' });
  const [on, setOn] = useState(false);

  useEffect(() => {
    biometricCapabilities().then(setCaps);
    getBiometricPref().then(setOn);
  }, []);

  const toggle = async () => {
    if (!caps.hasHardware) {
      toast({ title: 'Not available', message: 'This device has no biometric hardware.', duration: 2200 });
      return;
    }
    if (!caps.enrolled) {
      toast({ title: 'Not enrolled', message: `Set up ${caps.label} in your OS settings.`, duration: 2400 });
      return;
    }
    if (!on) {
      const ok = await authenticate(`Enable ${caps.label} unlock`);
      if (!ok) return;
      await setBiometricPref(true);
      setOn(true);
      toast({ title: `${caps.label} on`, message: 'You will be prompted on cold start.', duration: 2200 });
    } else {
      await setBiometricPref(false);
      setOn(false);
    }
  };

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader title="Biometric unlock" subtitle="THIS PHONE · LOCK ON COLD START" onBack={() => router.back()} />
      <ScrollView>
        <SectionHeader>Capability</SectionHeader>
        <Row
          label="Hardware"
          value={<Pill tone={caps.hasHardware ? 'on' : undefined} off={!caps.hasHardware}>{caps.hasHardware ? 'detected' : 'none'}</Pill>}
          chevron={false}
        />
        <RowSeparator />
        <Row
          label={caps.label}
          value={<Pill tone={caps.enrolled ? 'on' : undefined} off={!caps.enrolled}>{caps.enrolled ? 'enrolled' : 'not enrolled'}</Pill>}
          chevron={false}
        />

        <SectionHeader>Unlock</SectionHeader>
        <Pressable
          onPress={toggle}
          android_ripple={{ color: colors.selected }}
          style={({ pressed }) => ({
            paddingHorizontal: space.s8,
            paddingVertical: space.s6,
            flexDirection: 'row',
            alignItems: 'center',
            backgroundColor: pressed ? colors.selected : 'transparent',
          })}
        >
          <View style={{ flex: 1, gap: space.s1 }}>
            <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.lg, color: colors.ink }}>
              Require {caps.label} on cold start
            </Text>
            <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink4 }}>
              {on ? 'on' : 'off'}
            </Text>
          </View>
          <View
            style={{
              width: 44,
              height: 26,
              borderRadius: radii.pill,
              backgroundColor: on ? colors.ink : colors.line,
              padding: space.s1,
              alignItems: on ? 'flex-end' : 'flex-start',
              justifyContent: 'center',
            }}
          >
            <View style={{ width: 20, height: 20, borderRadius: radii.lg, backgroundColor: colors.bgPane }} />
          </View>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}
