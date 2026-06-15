import { Text, View } from 'react-native';

import { useTheme } from '../theme/ThemeContext';
import { space } from '../theme/tokens';
import { ThinkingDots } from '../features/chat/ThinkingDots';
import { SkeletonBar } from './SkeletonBar';

const WIDTHS = ['92%', '100%', '74%'];

export function MessageSkeleton({ style }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <View style={[{ gap: space.s4 }, style]}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s2 }}>
        <ThinkingDots color={colors.ink3} padded={false} />
        <Text style={{ color: colors.ink4, fontFamily: fonts.mono, fontSize: fontSizes.xs }}>
          thinking…
        </Text>
      </View>
      <View style={{ gap: space.s2 }}>
        {WIDTHS.map((w, i) => (
          <SkeletonBar key={i} width={w} height={13} delay={i * 120} />
        ))}
      </View>
    </View>
  );
}
