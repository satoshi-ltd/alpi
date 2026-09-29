import { Pressable, Text, View } from 'react-native';
import { lineHeights, radii, space, tracking } from '../theme/tokens';

import { Icon } from './Icon';
import { MetaStrip, metaItems } from './MetaStrip';
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
        backgroundColor: pressed ? colors.selected : 'transparent',
      })}
    >
      {children}
    </Pressable>
  );
}

export function ScreenHeader({ title, subtitle, meta, onBack, right, leadingGlyph, accent }) {
  const { colors, fonts, fontSizes } = useTheme();
  const { twoPane, sidebarOpen, toggleSidebar } = usePane();
  const showBack = useShowBack(onBack);
  const showSidebarToggle = twoPane && !sidebarOpen;
  const titleSize = fontSizes.xl;
  const metaList = twoPane ? metaItems(meta) : [];
  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: metaList.length ? 'flex-start' : 'center',
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
        <View style={{ marginLeft: -space.s2 }}>
          <ChromeButton label="Show sidebar" onPress={toggleSidebar}>
            <Icon name="panel-left" size="lg" color={colors.ink2} />
          </ChromeButton>
        </View>
      ) : null}
      {showBack && !twoPane ? (
        <Pressable
          onPress={onBack}
          hitSlop={space.s3}
          accessibilityRole="button"
          accessibilityLabel="Back"
          style={{ width: 28, height: 36, alignItems: 'center', justifyContent: 'center', marginLeft: -space.s2 }}
        >
          <Icon name="back" size="lg" color={colors.ink2} />
        </Pressable>
      ) : null}
      <View style={{ flex: 1, minWidth: 0, flexDirection: 'column' }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: twoPane ? space.s4 : space.s2 }}>
          {leadingGlyph}
          <Text
            numberOfLines={1}
            style={{
              fontFamily: fonts.sans.semibold,
              fontSize: titleSize,
              lineHeight: titleSize * lineHeights.cozy,
              color: colors.ink,
              flexShrink: 1,
            }}
          >
            {title}
          </Text>
          {twoPane && typeof subtitle === 'string' ? (
            <Text
              numberOfLines={1}
              style={{
                fontFamily: fonts.mono,
                fontSize: fontSizes.xs,
                lineHeight: fontSizes.xs * lineHeights.cozy,
                letterSpacing: fontSizes.xs * tracking.wide,
                color: colors.ink3,
                marginTop: space.s1,
              }}
            >
              {subtitle}
            </Text>
          ) : null}
        </View>
        {subtitle && !(twoPane && typeof subtitle === 'string') ? (
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
        {metaList.length ? <MetaStrip style={{ marginTop: space.s3 }}>{metaList}</MetaStrip> : null}
      </View>
      {right}
      {showBack && twoPane ? (
        <ChromeButton label="Back" onPress={onBack}>
          <Icon name="arrow-left" size="md" color={colors.ink2} />
        </ChromeButton>
      ) : null}
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
