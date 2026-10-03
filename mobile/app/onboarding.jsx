import { useRouter } from 'expo-router';
import { Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { ALPACA_FOLD } from '../../common/folds.mjs';
import { LINK_SOURCES } from '../../common/onboarding.mjs';
import { radii, space, tracking } from '../src/theme/tokens';

import { Button } from '../src/components/Button';
import { Fold } from '../src/components/Fold';
import { useTheme } from '../src/theme/ThemeContext';

export default function Onboarding() {
  const router = useRouter();
  const { colors, fonts, fontSizes, lineHeights } = useTheme();

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg, padding: space.s9 }}>
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', gap: space.s9 }}>
        <Fold fold={ALPACA_FOLD} size={88} />
        <Text
          style={{
            fontFamily: fonts.sans.semibold,
            fontSize: fontSizes.display,
            color: colors.ink,
            textAlign: 'center',
            letterSpacing: fontSizes.display * tracking.tight,
          }}
        >
          Pair with your alpi
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
          alpi runs on a computer or a server. Pair this phone once and its profiles come with you.
        </Text>
      </View>
      <View style={{ gap: space.s4 }}>
        <View style={{ gap: space.s2, padding: space.s5, borderRadius: radii.xs, backgroundColor: colors.hover }}>
          <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.md, color: colors.ink }}>Where do I get a link?</Text>
          {LINK_SOURCES.map((line) => (
            <Text key={line} style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, lineHeight: fontSizes.sm * lineHeights.relaxed, color: colors.ink2 }}>
              {line}
            </Text>
          ))}
        </View>
        <Button title="Scan QR" onPress={() => router.push({ pathname: '/pair', params: { mode: 'scan' } })} fullWidth size="hero" />
        <Button title="Paste link" variant="ghost" onPress={() => router.push('/pair')} fullWidth />
      </View>
    </SafeAreaView>
  );
}
