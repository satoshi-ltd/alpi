import { Pressable, Text, View } from 'react-native';
import { lineHeights, radii, space, typeLeading } from '../theme/tokens';

import { NAME_TEXT, nameColor, nameSize, nameStyle } from '../theme/name';
import { Icon } from './Icon';
import { MetaStrip, metaItems } from './MetaStrip';
import { useShowBack } from '../hooks/useShowBack';
import { backMargins, CHROME_BTN, PANE_PAD_X, TOGGLE_BLEED, tapSlop } from '../lib/panes';
import { usePane } from '../nav/PaneContext';
import { useTheme } from '../theme/ThemeContext';

const NAME_MIN_SIZE = 28;

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
        borderRadius: radii.pill,
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: pressed ? colors.pressed : 'transparent',
      })}
    >
      {children}
    </Pressable>
  );
}

export function headerRightBleed(node) {
  const height = node?.type?.touchHeight?.(node.props?.size);
  return height ? Math.max(0, (height - CHROME_BTN) / 2) : 0;
}

export function ScreenHeader({ title, subtitle, meta, onBack, right, leadingGlyph, accent, neutral = false, muted = false }) {
  const { colors, fonts, fontSizes, textScale = 1, fontScale = 1 } = useTheme();
  const { twoPane, sidebarOpen, toggleSidebar } = usePane();
  const showBack = useShowBack(onBack);
  const showSidebarToggle = twoPane && !sidebarOpen;
  const titleSize = fontSizes.xl;
  const named = typeof accent === 'string' && typeof title === 'string' && title.length > 0;
  const metaList = twoPane ? metaItems(meta) : [];
  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: metaList.length ? 'flex-start' : 'center',
        gap: space.s4,
        paddingHorizontal: PANE_PAD_X,
        paddingTop: twoPane ? space.s5 : space.s3,
        paddingBottom: space.s5,
        backgroundColor: colors.bg,
      }}
    >
      {showSidebarToggle ? (
        <View style={{ marginLeft: -TOGGLE_BLEED }}>
          <ChromeButton label="Show sidebar" onPress={toggleSidebar}>
            <Icon name="panel-left" size="md" color={colors.ink2} />
          </ChromeButton>
        </View>
      ) : null}
      {showBack ? (
        <Pressable
          onPress={onBack}
          hitSlop={tapSlop(CHROME_BTN)}
          accessibilityRole="button"
          accessibilityLabel="Back"
          style={{ width: CHROME_BTN, height: CHROME_BTN, alignItems: 'center', justifyContent: 'center', ...backMargins(!showSidebarToggle) }}
        >
          <Icon name="back" size="md" color={colors.ink2} />
        </Pressable>
      ) : null}
      <View style={{ flex: 1, minWidth: 0, flexDirection: 'column' }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: twoPane ? space.s4 : space.s2 }}>
          {leadingGlyph}
          {named ? (
            <Text {...NAME_TEXT} style={[nameStyle(nameSize(Math.max(Math.round(NAME_MIN_SIZE * textScale), titleSize), fontScale), neutral ? (muted ? colors.ink3 : colors.ink) : nameColor(accent, colors)), { flexShrink: 1 }]}>
              {title}
            </Text>
          ) : (
            <Text
              numberOfLines={1}
              style={{
                fontFamily: fonts.sans.semibold,
                fontSize: titleSize,
                lineHeight: Math.round(titleSize * typeLeading.title),
                color: colors.ink,
                flexShrink: 1,
              }}
            >
              {title}
            </Text>
          )}
          {twoPane && typeof subtitle === 'string' ? (
            <Text
              numberOfLines={1}
              style={{
                fontFamily: fonts.sans.regular,
                fontSize: fontSizes.sm,
                lineHeight: Math.round(fontSizes.sm * typeLeading.small),
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
                fontFamily: fonts.sans.regular,
                fontSize: fontSizes.sm,
                lineHeight: Math.round(fontSizes.sm * typeLeading.small),
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
      {right ? <View style={{ marginVertical: -headerRightBleed(right) }}>{right}</View> : null}
    </View>
  );
}
