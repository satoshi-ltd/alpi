import { useRouter } from 'expo-router';
import { Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { space , fontSizes} from '../src/theme/tokens';

import { Button } from '../src/components/Button';
import { Icon } from '../src/components/Icon';
import { useTheme } from '../src/theme/ThemeContext';

export default function PairSuccess() {
  const router = useRouter();
  const { colors, fonts, fontSizes, lineHeights } = useTheme();

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg, padding: space.s9 }}>
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', gap: space.s8 }}>
        <View
          style={{
            width: 88,
            height: 88,
            borderRadius: 44,
            backgroundColor: `${colors.success}22`,
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Icon name="forward" size={44} color={colors.success} strokeWidth={2.5} />
        </View>
        <Text
          style={{
            fontFamily: fonts.sans.semibold,
            fontSize: fontSizes.display,
            color: colors.ink,
            textAlign: 'center',
            letterSpacing: -0.018 * 28,
          }}
        >
          Paired
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
          Your daemon is reachable and your alpis are available.
        </Text>
      </View>
      <Button title="Open Inbox" size="hero" onPress={() => router.replace('/')} fullWidth />
    </SafeAreaView>
  );
}
