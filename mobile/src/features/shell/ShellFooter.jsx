import Constants from 'expo-constants';
import { useState } from 'react';
import { ICON_ROLES } from '../../../../common/iconRoles.mjs';
import { Pressable, Text, View } from 'react-native';

import { dotShape } from '../../components/dotShape';
import { Icon } from '../../components/Icon';
import { CHROME_H } from '../../lib/panes';
import { usePane } from '../../nav/PaneContext';
import { useTheme } from '../../theme/ThemeContext';
import { iconSizes, mobile, radii, space } from '../../theme/tokens';

const ENTRY_H = mobile.tap;
const ENTRY_SLOP = (CHROME_H - ENTRY_H) / 2;
export const ENTRY_INSET_X = 0;
export const LABEL_EM = 5.2;
export const LABEL_ROOM = space.s1;

const APP_VERSION = Constants.expoConfig?.version ?? '0.0.0';
const VERSION_EM = 0.6;
const VERSION_ROOM = space.s2;
const PANE_ENTRY_W = 40;
const ICON_INK_INSET = (PANE_ENTRY_W - iconSizes.md) / 2;
const THEME_ORDER = ['light', 'dark', 'system'];
const THEME_LABEL = { system: 'System', light: 'Light', dark: 'Dark' };
const THEME_ICON = { system: 'sun-moon', light: 'sun', dark: 'moon' };
export const versionFits = (width, entries, versionWidth) => width - 2 * space.s2 - entries * PANE_ENTRY_W >= versionWidth + ICON_INK_INSET + VERSION_ROOM;
export const nextTheme = (pref) => THEME_ORDER[(THEME_ORDER.indexOf(pref) + 1) % THEME_ORDER.length];

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

export function ShellFooter({ unread = 0, onNotificationsPress, onSettingsPress, needsYou = 0, onActivityPress, searchOpen = false, onSearchPress }) {
  const { colors, fonts, fontSizes, chromeScale, fontScale = 1, pref = 'system', setMode } = useTheme();
  const [width, setWidth] = useState(null);
  const { twoPane } = usePane();
  const entryStyle = ({ pressed }) => ({
    ...(twoPane ? { width: PANE_ENTRY_W } : { flex: 1 }),
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: space.s1 / 2,
    minHeight: ENTRY_H,
    minWidth: 0,
    paddingHorizontal: ENTRY_INSET_X,
    borderRadius: radii.control,
    backgroundColor: pressed ? colors.pressed : 'transparent',
  });
  const slop = twoPane ? { top: ENTRY_SLOP, bottom: ENTRY_SLOP, left: 0, right: 0 } : ENTRY_SLOP;
  const showSearch = twoPane && !!onSearchPress;
  const showTheme = twoPane && !!setMode;
  const entries = 1 + (onNotificationsPress ? 1 : 0) + (onActivityPress ? 1 : 0) + (showSearch ? 1 : 0) + (showTheme ? 1 : 0);
  const padX = twoPane ? space.s2 : space.s5;
  const slotWidth = width === null ? Infinity : (width - 2 * padX) / entries;
  const labelWidth = LABEL_EM * fontSizes.xs * Math.min(fontScale, chromeScale ?? Infinity);
  const versionWidth = VERSION_EM * fontSizes.xs * Math.min(fontScale, chromeScale ?? Infinity) * APP_VERSION.length;
  const showVersion = twoPane && (width === null || versionFits(width, entries, versionWidth));
  const showLabels = !twoPane && slotWidth >= labelWidth + LABEL_ROOM;
  const entryLabel = { fontFamily: fonts.sans.medium, fontSize: fontSizes.xs, color: colors.ink2 };
  return (
    <View
      onLayout={(e) => setWidth(e.nativeEvent.layout.width)}
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        height: CHROME_H,
        paddingHorizontal: padX,
      }}
    >
      <Pressable onPress={onSettingsPress} style={entryStyle} hitSlop={slop} accessibilityRole="button" accessibilityLabel="Settings">
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
          hitSlop={slop}
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
          hitSlop={slop}
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
      {showSearch ? (
        <Pressable
          onPress={onSearchPress}
          style={(state) => ({ ...entryStyle(state), backgroundColor: state.pressed || searchOpen ? colors.selected : 'transparent' })}
          hitSlop={slop}
          accessibilityRole="button"
          accessibilityState={{ selected: searchOpen }}
          accessibilityLabel={searchOpen ? 'Close filter' : 'Filter profiles and workgroups'}
        >
          <Icon name={searchOpen ? 'x' : 'search'} size="md" color={colors.ink2} />
        </Pressable>
      ) : null}
      {showTheme ? (
        <Pressable
          onPress={() => setMode(nextTheme(pref))}
          style={entryStyle}
          hitSlop={slop}
          accessibilityRole="button"
          accessibilityLabel={`Theme: ${THEME_LABEL[pref] ?? THEME_LABEL.system}`}
          accessibilityHint={`Switches to ${THEME_LABEL[nextTheme(pref)]}`}
        >
          <Icon name={THEME_ICON[pref] ?? THEME_ICON.system} size="md" color={colors.ink2} />
        </Pressable>
      ) : null}
      {showVersion ? (
        <View style={{ flex: 1, minWidth: 0, alignItems: 'flex-end', paddingRight: ICON_INK_INSET }}>
          <Text
            accessibilityRole="text"
            maxFontSizeMultiplier={chromeScale}
            numberOfLines={1}
            style={{ flexShrink: 0, fontFamily: fonts.sans.medium, fontSize: fontSizes.xs, color: colors.ink3 }}
          >
            {APP_VERSION}
          </Text>
        </View>
      ) : null}
    </View>
  );
}
