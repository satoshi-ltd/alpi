import { Pressable, Text, View } from 'react-native';
import { lineHeights, radii, space } from '../theme/tokens';

import { Icon } from './Icon';
import { useShowBack } from '../hooks/useShowBack';
import { CHROME_BTN, tapSlop } from '../lib/panes';
import { usePane } from '../nav/PaneContext';
import { useTheme } from '../theme/ThemeContext';

const STRIPE_H = 1.5;

function ChromeButton({ label, onPress, children }) {
  const { colors } = useTheme();
  return (
    <Pressable
      onPress={onPress}
      hitSlop={tapSlop(CHROME_BTN)}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={({ pressed }) => ({
        width: CHROME_BTN,
        height: CHROME_BTN,
        borderRadius: radii.md,
        alignItems: 'center',
        justifyContent: 'center',
        marginLeft: -space.s2,
        backgroundColor: pressed ? colors.selected : 'transparent',
      })}
    >
      {children}
    </Pressable>
  );
}

export function ScreenHeader({ title, subtitle, onBack, right, leadingGlyph, accent }) {
  const { colors, fonts, fontSizes } = useTheme();
  const { twoPane, sidebarOpen, toggleSidebar } = usePane();
  const showBack = useShowBack(onBack);
  const showSidebarToggle = twoPane && !sidebarOpen;
  const titleSize = fontSizes.xl;
  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        gap: space.s4,
        paddingHorizontal: twoPane ? space.s9 : space.s5,
        paddingTop: twoPane ? space.s5 : space.s3,
        paddingBottom: space.s5,
        backgroundColor: colors.bg,
        borderBottomWidth: 0.5,
        borderBottomColor: colors.line,
      }}
    >
      {showSidebarToggle ? (
        <ChromeButton label="Show sidebar" onPress={toggleSidebar}>
          <Icon name="panel-left" size="lg" color={colors.ink2} />
        </ChromeButton>
      ) : null}
      {showBack ? (
        <Pressable
          onPress={onBack}
          hitSlop={space.s3}
          style={{ width: 28, height: 36, alignItems: 'center', justifyContent: 'center', marginLeft: -space.s2 }}
        >
          <Icon name="back" size="lg" color={colors.ink2} />
        </Pressable>
      ) : null}
      <View style={{ flex: 1, minWidth: 0, flexDirection: 'column' }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s2 }}>
          {leadingGlyph}
          <Text
            numberOfLines={1}
            style={{
              fontFamily: fonts.sans.semibold,
              fontSize: titleSize,
              lineHeight: titleSize * lineHeights.cozy,
              color: colors.ink,
            }}
          >
            {title}
          </Text>
        </View>
        {subtitle ? (
          typeof subtitle === 'string' ? (
            <Text
              numberOfLines={1}
              style={{
                fontFamily: fonts.mono,
                fontSize: fontSizes.xs,
                lineHeight: fontSizes.xs * lineHeights.cozy,
                color: colors.ink3,
              }}
            >
              {subtitle}
            </Text>
          ) : (
            <View>{subtitle}</View>
          )
        ) : null}
      </View>
      {right}
      {twoPane ? (
        <View
          style={{
            position: 'absolute',
            left: space.s9,
            bottom: -0.5,
            height: STRIPE_H,
            width: space.s11,
            backgroundColor: accent ?? colors.accent,
          }}
        />
      ) : null}
    </View>
  );
}
