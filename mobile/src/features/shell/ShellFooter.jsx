import Constants from 'expo-constants';
import { useState } from 'react';
import { ICON_ROLES } from '../../../../common/iconRoles.mjs';
import { Pressable, Text, View } from 'react-native';

import { dotShape } from '../../components/dotShape';
import { Icon } from '../../components/Icon';
import { CHROME_H } from '../../lib/panes';
import { THEME_ORDER, nextThemePref } from '../../lib/nextThemePref';
import { usePane } from '../../nav/PaneContext';
import { useTheme } from '../../theme/ThemeContext';
import { mobile, radii, space } from '../../theme/tokens';

const HAIRLINE = 0.5;
const ENTRY_H = space.s11;
const ENTRY_SLOP = (CHROME_H - ENTRY_H) / 2;
export const ENTRY_INSET_X = 0;
export const LABEL_EM = 5.2;
export const LABEL_ROOM = space.s1;

const APP_VERSION = Constants.expoConfig?.version ?? '0.0.0';
const VERSION_EM = 0.6;
const VERSION_ROOM = space.s5;
const ICON_INK_INSET = (mobile.tap - 16) / 2;

const THEME_ICON = { system: 'sun-moon', light: 'sun', dark: 'moon' };
const THEME_LABEL = { system: 'System', light: 'Light', dark: 'Dark' };

const DOT_OFFSET = space.s1;

function DotAnchor({ show, color }) {
  if (!show) return null;
  return (
    <View
      testID="dot-anchor"
      pointerEvents="none"
      style={{ position: 'absolute', top: -DOT_OFFSET, right: -DOT_OFFSET, backgroundColor: color, ...dotShape('md') }}
    />
  );
}

export function ShellFooter({ unread = 0, onNotificationsPress, onSettingsPress, needsYou = 0, onActivityPress }) {
  const { colors, fonts, fontSizes, chromeScale, fontScale = 1, pref, setMode } = useTheme();
  const [width, setWidth] = useState(null);
  const themePref = THEME_ORDER.includes(pref) ? pref : 'system';
  const { twoPane } = usePane();
  const entryStyle = ({ pressed }) => ({
    ...(twoPane ? { width: mobile.tap } : { flex: 1 }),
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: space.s1 / 2,
    minHeight: ENTRY_H,
    minWidth: 0,
    paddingHorizontal: ENTRY_INSET_X,
    borderRadius: radii.xs,
    backgroundColor: pressed ? colors.selected : 'transparent',
  });
  const entries = 2 + (onNotificationsPress ? 1 : 0) + (onActivityPress ? 1 : 0);
  const slotWidth = width === null ? Infinity : (width - 2 * space.s5) / entries;
  const labelWidth = LABEL_EM * fontSizes.xs * Math.min(fontScale, chromeScale ?? Infinity);
  const versionWidth = VERSION_EM * fontSizes.xs * Math.min(fontScale, chromeScale ?? Infinity) * APP_VERSION.length;
  const showVersion = twoPane && (width === null || width - 2 * space.s5 - entries * mobile.tap >= versionWidth + ICON_INK_INSET + VERSION_ROOM);
  const showLabels = !twoPane && slotWidth >= labelWidth + LABEL_ROOM;
  const entryLabel = { fontFamily: fonts.sans.medium, fontSize: fontSizes.xs, color: colors.ink2 };
  return (
    <View
      onLayout={(e) => setWidth(e.nativeEvent.layout.width)}
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
        {showLabels ? (
          <Text maxFontSizeMultiplier={chromeScale} numberOfLines={1} style={entryLabel}>
            Settings
          </Text>
        ) : null}
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
            <DotAnchor show={unread > 0} color={colors.danger} />
          </View>
          {showLabels ? (
            <Text maxFontSizeMultiplier={chromeScale} numberOfLines={1} style={entryLabel}>
              Notifications
            </Text>
          ) : null}
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
            <DotAnchor show={needsYou > 0} color={colors.danger} />
          </View>
          {showLabels ? (
            <Text maxFontSizeMultiplier={chromeScale} numberOfLines={1} style={entryLabel}>
              Activity
            </Text>
          ) : null}
        </Pressable>
      ) : null}
      <Pressable
        onPress={() => setMode?.(nextThemePref(themePref))}
        style={entryStyle}
        hitSlop={ENTRY_SLOP}
        accessibilityRole="button"
        accessibilityLabel={`Theme: ${THEME_LABEL[themePref]}. Switch to ${THEME_LABEL[nextThemePref(themePref)]}`}
      >
        <Icon name={THEME_ICON[themePref]} size="md" color={colors.ink2} />
        {showLabels ? (
          <Text maxFontSizeMultiplier={chromeScale} numberOfLines={1} style={entryLabel}>
            {THEME_LABEL[themePref]}
          </Text>
        ) : null}
      </Pressable>
      {showVersion ? (
        <View style={{ flex: 1, minWidth: 0, alignItems: 'flex-end', paddingRight: ICON_INK_INSET }}>
          <Text
            accessibilityRole="text"
            maxFontSizeMultiplier={chromeScale}
            numberOfLines={1}
            style={{ flexShrink: 0, fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}
          >
            {APP_VERSION}
          </Text>
        </View>
      ) : null}
    </View>
  );
}
