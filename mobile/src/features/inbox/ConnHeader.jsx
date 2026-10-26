import { Pressable, Text, View } from 'react-native';
import { lineHeights, mobile, radii, space } from '../../theme/tokens';

import { Eyebrow } from '../../components/Eyebrow';
import { Icon } from '../../components/Icon';
import { CHROME_BTN, tapSlop } from '../../lib/panes';
import { usePane } from '../../nav/PaneContext';
import { useTheme } from '../../theme/ThemeContext';

export function statusWord(status) {
  if (status === 'online' || status === 'connected') return 'online';
  if (status === 'offline') return 'offline · retrying…';
  if (status === 'auth-failed') return 'sign-in failed';
  if (status === 'disabled') return 'disabled';
  return 'connecting…';
}

export function ConnHeader({
  name = 'Local',
  host = 'host.sock',
  status = 'online',
  searchOpen = false,
  onToggleSearch,
  onConnPress,
  onCollapse,
}) {
  const { colors, fonts, fontSizes } = useTheme();
  const { twoPane } = usePane();
  const word = statusWord(status);
  const [statusColor, statusInk] =
    status === 'online' || status === 'connected'
      ? [colors.success, colors.successText ?? colors.ink2]
      : status === 'offline' || status === 'auth-failed'
        ? [colors.danger, colors.dangerText ?? colors.ink2]
        : status === 'disabled'
          ? [colors.ink3, colors.ink3]
          : [colors.warning, colors.warningText ?? colors.ink2];

  const searchToggle = onToggleSearch ? (
    <Pressable
      onPress={onToggleSearch}
      hitSlop={tapSlop(CHROME_BTN)}
      style={({ pressed }) => ({
        width: CHROME_BTN,
        height: CHROME_BTN,
        borderRadius: radii.xs,
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: pressed || searchOpen ? colors.selected : 'transparent',
      })}
      accessibilityRole="button"
      accessibilityLabel={searchOpen ? 'Close filter' : 'Filter profiles and workgroups'}
    >
      <Icon name={searchOpen ? 'x' : 'search'} size="md" color={colors.ink2} />
    </Pressable>
  ) : null;

  const trigger = ({ pressed }) => ({
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.s4,
    minHeight: mobile.tap,
    paddingHorizontal: space.s5,
    paddingVertical: space.s2,
    borderWidth: 0.5,
    borderColor: colors.line,
    borderRadius: radii.xs,
    backgroundColor: pressed ? colors.selected : colors.bgElev,
  });

  const identity = (
    <>
      <Icon name="cpu" size="md" color={colors.ink2} />
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
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s2, flexShrink: 0 }}>
        <View style={{ width: 8, height: 8, borderRadius: radii.xs, backgroundColor: statusColor }} />
        <Text
          numberOfLines={1}
          style={{ fontFamily: fonts.sans.medium ?? fonts.sans.semibold, fontSize: fontSizes.sm ?? fontSizes.xs, color: statusInk }}
        >
          {word}
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
        {onCollapse ? (
          <Pressable
            onPress={onCollapse}
            hitSlop={tapSlop(CHROME_BTN)}
            accessibilityRole="button"
            accessibilityLabel="Hide sidebar"
            style={({ pressed }) => ({
              width: CHROME_BTN,
              height: CHROME_BTN,
              borderRadius: radii.xs,
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: pressed ? colors.selected : 'transparent',
            })}
          >
            <Icon name="panel-left" size="md" color={colors.ink2} />
          </Pressable>
        ) : null}
        {searchToggle}
      </View>
      <Pressable
        onPress={onConnPress}
        style={trigger}
        accessibilityRole="button"
        accessibilityLabel={`Connection ${name}, ${host}, ${word}`}
      >
        {identity}
      </Pressable>
    </View>
  );
}
