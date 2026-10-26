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
        <Text allowFontScaling={false} style={countBadgeText(fonts, colors.onDanger ?? '#fff')}>
          {badgeCount(count)}
        </Text>
      </View>
    </View>
  );
}

export function ShellFooter({ unread = 0, onNotificationsPress, onSettingsPress, needsYou = 0, onActivityPress }) {
  const { colors, fonts, fontSizes, chromeScale } = useTheme();
  const { twoPane } = usePane();
  const ring = twoPane ? colors.bgSide : colors.bg;
  const entryStyle = ({ pressed }) => ({
    flex: 1,
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: space.s1 / 2,
    minHeight: ENTRY_H,
    paddingHorizontal: space.s3,
    borderRadius: radii.xs,
    backgroundColor: pressed ? colors.selected : 'transparent',
  });
  const entryLabel = { fontFamily: fonts.sans.medium, fontSize: fontSizes.xs, color: colors.ink2 };
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
        <Text maxFontSizeMultiplier={chromeScale} numberOfLines={1} style={entryLabel}>
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
          <Text maxFontSizeMultiplier={chromeScale} numberOfLines={1} style={entryLabel}>
            Notifications
          </Text>
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
          <Text maxFontSizeMultiplier={chromeScale} numberOfLines={1} style={entryLabel}>
            Activity
          </Text>
        </Pressable>
      ) : null}
      <Text maxFontSizeMultiplier={chromeScale} style={{ fontFamily: fonts.monoMedium, fontSize: fontSizes.xs, color: colors.ink3, marginLeft: space.s3 }}>
        v{APP_VERSION}
      </Text>
    </View>
  );
}
