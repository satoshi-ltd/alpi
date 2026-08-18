import { useRouter } from 'expo-router';
import { Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { space, tracking } from '../src/theme/tokens';

import { Button } from '../src/components/Button';
import { AlpiMark } from '../src/components/AlpiMark';
import { useTheme } from '../src/theme/ThemeContext';

export default function Onboarding() {
  const router = useRouter();
  const { colors, fonts, fontSizes, lineHeights } = useTheme();

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg, padding: space.s9 }}>
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', gap: space.s9 }}>
        <AlpiMark color={colors.ink} size={88} />
        <Text
          style={{
            fontFamily: fonts.sans.semibold,
            fontSize: fontSizes.display,
            color: colors.ink,
            textAlign: 'center',
            letterSpacing: fontSizes.display * tracking.tight,
          }}
        >
          Connect to Alpi
        </Text>
        <Text
          style={{
            fontFamily: fonts.sans.regular,
            fontSize: fontSizes.lg,
            color: colors.ink2,
            textAlign: 'center',
            lineHeight: fontSizes.lg * lineHeights.relaxed,
            maxWidth: 320,
          }}
        >
          Alpi runs as a daemon on your computer or Umbrel. This phone is a client — pair it once and you can talk to your profiles from anywhere.
        </Text>
      </View>
      <View style={{ gap: space.s4 }}>
        <Button title="Scan QR" onPress={() => router.push('/pair')} fullWidth size="hero" />
        <Button title="Paste alpi:// link" variant="ghost" onPress={() => router.push('/pair')} fullWidth />
      </View>
    </SafeAreaView>
  );
}
