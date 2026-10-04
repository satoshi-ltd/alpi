import Constants from 'expo-constants';
import { badgeCount } from '../../../../common/countBadge.mjs';
import { ICON_ROLES } from '../../../../common/iconRoles.mjs';
import { Pressable, Text, View } from 'react-native';

import { Icon } from '../../components/Icon';
import { CHROME_H } from '../../lib/panes';
import { usePane } from '../../nav/PaneContext';
import { useTheme } from '../../theme/ThemeContext';
import { countBadge, radii, space } from '../../theme/tokens';

const HAIRLINE = 0.5;
const ENTRY_H = space.s11;
const ENTRY_SLOP = (CHROME_H - ENTRY_H) / 2;
const APP_VERSION = Constants.expoConfig?.version ?? '0.0.0';

const THEME_ORDER = ['light', 'dark', 'system'];
const THEME_ICON = { light: 'sun', dark: 'moon', system: 'sun-moon' };
const THEME_LABEL = { light: 'Light', dark: 'Dark', system: 'System' };

export function nextThemePref(pref) {
  return THEME_ORDER[(THEME_ORDER.indexOf(pref) + 1) % THEME_ORDER.length];
}

export function countBadgeText(fonts, color) {
  return {
    fontFamily: fonts.sans.semibold,
    fontSize: countBadge.fontSize,
    lineHeight: countBadge.fontSize,
    includeFontPadding: false,
    color,
  };
}

const BADGE_OUTSET = space.s3;
const BADGE_LIFT = countBadge.size - space.s2;

export function CountBadge({ count, ring }) {
  const { colors, fonts } = useTheme();
  if (!(count > 0)) return null;
  return (
    <View
      testID="badge-anchor"
      pointerEvents="none"
      style={{ position: 'absolute', top: -BADGE_LIFT, right: -BADGE_OUTSET, flexDirection: 'row' }}
    >
      <View
        style={{
          minWidth: countBadge.size,
          height: countBadge.size,
          paddingHorizontal: space.s1,
          flexDirection: 'row',
          borderRadius: radii.pill,
          borderWidth: countBadge.border,
          borderColor: ring,
          backgroundColor: colors.danger,
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Text numberOfLines={1} allowFontScaling={false} style={countBadgeText(fonts, colors.onDanger ?? '#fff')}>
          {badgeCount(count)}
        </Text>
      </View>
    </View>
  );
}

export function ShellFooter({ unread = 0, onNotificationsPress, onSettingsPress, needsYou = 0, onActivityPress }) {
  const { colors, fonts, fontSizes, pref, setMode, chromeScale } = useTheme();
  const { twoPane } = usePane();
  const themePref = THEME_ORDER.includes(pref) ? pref : 'system';
  const ring = twoPane ? colors.bgSide : colors.bg;
  const entryStyle = ({ pressed }) => ({
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.s2,
    minHeight: ENTRY_H,
    paddingHorizontal: space.s3,
    borderRadius: radii.xs,
    backgroundColor: pressed ? colors.selected : 'transparent',
  });
  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        height: CHROME_H,
        paddingHorizontal: space.s5,
        borderTopWidth: twoPane ? 0 : HAIRLINE,
        borderTopColor: colors.line,
      }}
    >
      <Pressable onPress={onSettingsPress} style={entryStyle} hitSlop={ENTRY_SLOP} accessibilityRole="button" accessibilityLabel="Settings">
        <Icon name={ICON_ROLES.settings} size="md" color={colors.ink2} />
        <Text maxFontSizeMultiplier={chromeScale} style={{ fontFamily: fonts.sans.medium, fontSize: fontSizes.sm, color: colors.ink2 }}>
          Settings
        </Text>
      </Pressable>
      {onNotificationsPress ? (
        <Pressable
          onPress={onNotificationsPress}
          style={entryStyle}
          hitSlop={ENTRY_SLOP}
          accessibilityRole="button"
          accessibilityLabel={unread > 0 ? `Notifications · ${unread} unread` : 'Notifications'}
        >
          <View style={{ position: 'relative' }}>
            <Icon name={ICON_ROLES.notifications} size="md" color={colors.ink2} />
            <CountBadge count={unread} ring={ring} />
          </View>
        </Pressable>
      ) : null}
      {onActivityPress ? (
        <Pressable
          onPress={onActivityPress}
          style={entryStyle}
          hitSlop={ENTRY_SLOP}
          accessibilityRole="button"
          accessibilityLabel={needsYou > 0 ? `Activity · ${needsYou} need you` : 'Activity'}
        >
          <View style={{ position: 'relative' }}>
            <Icon name={ICON_ROLES.activity} size="md" color={colors.ink2} />
            <CountBadge count={needsYou} ring={ring} />
          </View>
        </Pressable>
      ) : null}
      {twoPane ? (
        <Pressable
          onPress={() => setMode?.(nextThemePref(themePref))}
          style={entryStyle}
          hitSlop={ENTRY_SLOP}
          accessibilityRole="button"
          accessibilityLabel={`Theme: ${THEME_LABEL[themePref]}`}
        >
          <Icon name={THEME_ICON[themePref]} size="md" color={colors.ink2} />
        </Pressable>
      ) : null}
      <View style={{ flex: 1 }} />
      <Text maxFontSizeMultiplier={chromeScale} style={{ fontFamily: fonts.monoMedium, fontSize: fontSizes.xs, color: colors.ink4 }}>
        v{APP_VERSION}
      </Text>
    </View>
  );
}
