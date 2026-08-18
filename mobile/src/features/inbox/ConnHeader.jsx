import { Pressable, Text, View } from 'react-native';
import { lineHeights, radii, space } from '../../theme/tokens';

import { Eyebrow } from '../../components/Eyebrow';
import { Icon } from '../../components/Icon';
import { CHROME_BTN, tapSlop } from '../../lib/panes';
import { usePane } from '../../nav/PaneContext';
import { useTheme } from '../../theme/ThemeContext';

export function ConnHeader({
  name = 'Local',
  host = 'host.sock',
  status = 'online',
  searchOpen = false,
  onToggleSearch,
  onConnPress,
}) {
  const { colors, fonts, fontSizes } = useTheme();
  const { twoPane } = usePane();
  const statusColor =
    status === 'online' || status === 'connected'
      ? colors.success
      : status === 'offline' || status === 'auth-failed'
        ? colors.danger
        : status === 'disabled'
          ? colors.ink3
        : colors.warning;

  const searchToggle = onToggleSearch ? (
    <Pressable
      onPress={onToggleSearch}
      hitSlop={tapSlop(CHROME_BTN)}
      style={({ pressed }) => ({
        width: CHROME_BTN,
        height: CHROME_BTN,
        borderRadius: radii.md,
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: pressed || searchOpen ? colors.selected : 'transparent',
      })}
      accessibilityLabel={searchOpen ? 'Close filter' : 'Filter profiles and workgroups'}
    >
      <Icon name={searchOpen ? 'x' : 'search'} size="md" color={colors.ink2} />
    </Pressable>
  ) : null;

  const trigger = ({ pressed }) => ({
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.s4,
    paddingHorizontal: space.s5,
    paddingVertical: space.s2,
    borderWidth: 0.5,
    borderColor: colors.line,
    borderRadius: radii.lg,
    backgroundColor: pressed ? colors.selected : colors.bgElev,
  });

  const identity = (
    <>
      <View style={{ position: 'relative' }}>
        <Icon name="cpu" size="md" color={colors.ink2} />
        <View
          style={{
            position: 'absolute',
            right: -2,
            bottom: -2,
            width: 8,
            height: 8,
            borderRadius: radii.xs,
            backgroundColor: statusColor,
            borderWidth: 2,
            borderColor: colors.bgElev,
          }}
        />
      </View>
      <View style={{ flexDirection: 'column', minWidth: 0, flex: 1 }}>
        <Text
          numberOfLines={1}
          style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.md, lineHeight: fontSizes.md * lineHeights.cozy, color: colors.ink }}
        >
          {name}
        </Text>
        <Text
          numberOfLines={1}
          style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, lineHeight: fontSizes.xs * lineHeights.cozy, color: colors.ink3 }}
        >
          {host}
        </Text>
      </View>
      <Icon name="chevron-down" size="xs" color={colors.ink3} />
    </>
  );

  return (
    <View
      style={{
        gap: space.s1,
        paddingHorizontal: space.s5,
        paddingTop: space.s2,
        paddingBottom: space.s3,
        backgroundColor: twoPane ? colors.bgSide : colors.bg,
        borderBottomWidth: twoPane ? 0 : 0.5,
        borderBottomColor: colors.line,
      }}
    >
      <View style={{ flexDirection: 'row', alignItems: 'center' }}>
        <Eyebrow style={{ flex: 1 }}>Connection</Eyebrow>
        {searchToggle}
      </View>
      <Pressable onPress={onConnPress} style={trigger}>
        {identity}
      </Pressable>
    </View>
  );
}
