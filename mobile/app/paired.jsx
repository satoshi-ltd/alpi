import { useLocalSearchParams, useRouter } from 'expo-router';
import { Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { space, tracking } from '../src/theme/tokens';

import { ALPACA_FOLD } from '../../common/folds.mjs';
import { pairedRoleLine } from '../../common/onboarding.mjs';
import { Button } from '../src/components/Button';
import { Fold } from '../src/components/Fold';
import { useTheme } from '../src/theme/ThemeContext';

export default function PairSuccess() {
  const router = useRouter();
  const { host, role, shared } = useLocalSearchParams();
  const { colors, fonts, fontSizes, lineHeights } = useTheme();
  const sharedCount = shared != null && shared !== '' ? Number(shared) : null;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg, padding: space.s9 }}>
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', gap: space.s8 }}>
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
          {host ? `Paired with ${host}` : 'Paired'}
        </Text>
        {role ? (
          <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.ink3 }}>
            {pairedRoleLine(role, sharedCount)}
          </Text>
        ) : null}
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
          Your daemon is reachable and your profiles are available.
        </Text>
      </View>
      <Button
        title="Open inbox"
        size="hero"
        onPress={() => {
          if (router.canDismiss?.()) router.dismissAll();
          router.replace('/');
        }}
        fullWidth
      />
    </SafeAreaView>
  );
}
