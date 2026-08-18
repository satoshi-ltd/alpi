import Constants from 'expo-constants';
import { Pressable, Text, View } from 'react-native';

import { Icon } from '../../components/Icon';
import { CHROME_H } from '../../lib/panes';
import { usePane } from '../../nav/PaneContext';
import { useTheme } from '../../theme/ThemeContext';
import { radii, space } from '../../theme/tokens';

const HAIRLINE = 0.5;
const APP_VERSION = Constants.expoConfig?.version ?? '0.0.0';

export function ShellFooter({ unread = 0, onNotificationsPress, onSettingsPress }) {
  const { colors, fonts, fontSizes } = useTheme();
  const { twoPane } = usePane();
  const entryStyle = ({ pressed }) => ({
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.s2,
    paddingHorizontal: space.s3,
    paddingVertical: space.s2,
    borderRadius: radii.md,
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
                  minWidth: space.s6,
                  height: space.s6,
                  paddingHorizontal: space.s1,
                  borderRadius: radii.pill,
                  backgroundColor: colors.danger,
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Text
                  style={{
                    fontFamily: fonts.sans.semibold,
                    fontSize: fontSizes.xxs,
                    lineHeight: space.s6,
                    color: '#fff',
                  }}
                >
                  {unread > 99 ? '99+' : unread}
                </Text>
              </View>
            ) : null}
          </View>
        </Pressable>
      ) : null}
      <View style={{ flex: 1 }} />
      <Text style={{ fontFamily: fonts.monoMedium, fontSize: fontSizes.xs, color: colors.ink4 }}>
        v{APP_VERSION}
      </Text>
    </View>
  );
}
