import Constants from 'expo-constants';
import { Pressable, Text, View } from 'react-native';

import { Icon } from '../../components/Icon';
import { CHROME_H } from '../../lib/panes';
import { usePane } from '../../nav/PaneContext';
import { useTheme } from '../../theme/ThemeContext';
import { lineHeights, radii, space } from '../../theme/tokens';

const HAIRLINE = 0.5;
const APP_VERSION = Constants.expoConfig?.version ?? '0.0.0';

const THEME_ORDER = ['light', 'dark', 'system'];
const THEME_ICON = { light: 'sun', dark: 'moon', system: 'sun-moon' };
const THEME_LABEL = { light: 'Light', dark: 'Dark', system: 'System' };

export function nextThemePref(pref) {
  return THEME_ORDER[(THEME_ORDER.indexOf(pref) + 1) % THEME_ORDER.length];
}

export function ShellFooter({ unread = 0, onNotificationsPress, onSettingsPress }) {
  const { colors, fonts, fontSizes, pref, setMode } = useTheme();
  const { twoPane } = usePane();
  const themePref = THEME_ORDER.includes(pref) ? pref : 'system';
  const entryStyle = ({ pressed }) => ({
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.s2,
    paddingHorizontal: space.s3,
    paddingVertical: space.s2,
    borderRadius: radii.lg,
    backgroundColor: pressed ? colors.selected : 'transparent',
  });
  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        gap: space.s2,
        height: CHROME_H,
        paddingHorizontal: space.s5,
        borderTopWidth: twoPane ? 0 : HAIRLINE,
        borderTopColor: colors.line,
      }}
    >
      <Pressable onPress={onSettingsPress} style={entryStyle} accessibilityLabel="Settings">
        <Icon name="gear" size="md" color={colors.ink2} />
        <Text style={{ fontFamily: fonts.sans.medium, fontSize: fontSizes.sm, color: colors.ink2 }}>
          Settings
        </Text>
      </Pressable>
      {onNotificationsPress ? (
        <Pressable
          onPress={onNotificationsPress}
          style={entryStyle}
          accessibilityLabel={unread > 0 ? `Notifications · ${unread} unread` : 'Notifications'}
        >
          <View style={{ position: 'relative' }}>
            <Icon name="bell" size="md" color={colors.ink2} />
            {unread > 0 ? (
              <View
                style={{
                  position: 'absolute',
                  top: -space.s2,
                  right: -space.s3,
                  minWidth: 18,
                  height: 18,
                  paddingHorizontal: space.s2,
                  flexDirection: 'row',
                  borderRadius: radii.pill,
                  borderWidth: 1.5,
                  borderColor: twoPane ? colors.bgSide : colors.bg,
                  backgroundColor: colors.danger,
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Text
                  numberOfLines={1}
                  style={{
                    fontFamily: fonts.sans.semibold,
                    fontSize: fontSizes.label,
                    lineHeight: fontSizes.label * lineHeights.cozy,
                    includeFontPadding: false,
                    color: colors.onDanger ?? '#fff',
                  }}
                >
                  {unread > 99 ? '99+' : unread}
                </Text>
              </View>
            ) : null}
          </View>
        </Pressable>
      ) : null}
      {twoPane ? (
        <Pressable
          onPress={() => setMode?.(nextThemePref(themePref))}
          style={entryStyle}
          accessibilityRole="button"
          accessibilityLabel={`Theme: ${THEME_LABEL[themePref]}`}
        >
          <Icon name={THEME_ICON[themePref]} size="md" color={colors.ink2} />
        </Pressable>
      ) : null}
      <View style={{ flex: 1 }} />
      <Text style={{ fontFamily: fonts.monoMedium, fontSize: fontSizes.xs, color: colors.ink4 }}>
        v{APP_VERSION}
      </Text>
    </View>
  );
}
