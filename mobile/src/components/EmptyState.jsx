import { Text, View } from 'react-native';

import { lineHeights, space, tracking } from '../theme/tokens';
import { useTheme } from '../theme/ThemeContext';
import { Button } from './Button';

export function EmptyState({ title, detail, action, mark, hero = false, monoDetail = false, maxWidth, alert = false }) {
  const { colors, fonts, fontSizes } = useTheme();
  const titleSize = hero ? fontSizes.xxl : fontSizes.xl;
  return (
    <View
      accessibilityRole={alert ? 'alert' : undefined}
      style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: space.s9, minHeight: 240 }}
    >
      <View style={{ alignSelf: 'center', width: '100%', maxWidth, alignItems: 'center', gap: space.s3 }}>
        {mark ?? null}
        <Text
          style={{
            fontFamily: fonts.sans.semibold,
            fontSize: titleSize,
            lineHeight: titleSize * lineHeights.cozy,
            letterSpacing: titleSize * tracking.tight,
            color: colors.ink,
            textAlign: 'center',
            marginTop: mark ? space.s4 : 0,
          }}
        >
          {title}
        </Text>
        {detail ? (
          <Text
            style={{
              fontFamily: monoDetail ? fonts.mono : fonts.sans.regular,
              fontSize: monoDetail ? fontSizes.xs : fontSizes.md,
              lineHeight: (monoDetail ? fontSizes.xs : fontSizes.md) * lineHeights.cozy,
              color: colors.ink3,
              textAlign: 'center',
              maxWidth: 320,
            }}
          >
            {detail}
          </Text>
        ) : null}
        {action ? (
          <View style={{ marginTop: space.s3 }}>
            <Button title={action.label} variant="secondary" size="md" onPress={action.onPress} />
          </View>
        ) : null}
      </View>
    </View>
  );
}
