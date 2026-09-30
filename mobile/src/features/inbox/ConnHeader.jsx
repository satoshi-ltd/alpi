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
  onCollapse,
  onActivityPress,
  needsYou = 0,
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
        borderRadius: radii.lg,
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

  const activityButton = onActivityPress ? (
    <Pressable
      onPress={onActivityPress}
      hitSlop={tapSlop(CHROME_BTN)}
      accessibilityRole="button"
      accessibilityLabel={needsYou > 0 ? `Activity · ${needsYou} need you` : 'Activity'}
      style={({ pressed }) => ({
        width: CHROME_BTN,
        height: CHROME_BTN,
        borderRadius: radii.lg,
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: pressed ? colors.selected : 'transparent',
      })}
    >
      <Icon name="activity" size="md" color={needsYou > 0 ? colors.warningText ?? colors.warning : colors.ink2} />
      {needsYou > 0 ? (
        <View
          testID="needs-you-dot"
          style={{
            position: 'absolute',
            top: space.s2,
            right: space.s2,
            width: 8,
            height: 8,
            borderRadius: radii.xs,
            backgroundColor: colors.warning,
            borderWidth: 1.5,
            borderColor: twoPane ? colors.bgSide : colors.bg,
          }}
        />
      ) : null}
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
    borderRadius: radii.xl,
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
        {onCollapse ? (
          <Pressable
            onPress={onCollapse}
            hitSlop={tapSlop(CHROME_BTN)}
            accessibilityRole="button"
            accessibilityLabel="Hide sidebar"
            style={({ pressed }) => ({
              width: CHROME_BTN,
              height: CHROME_BTN,
              borderRadius: radii.lg,
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: pressed ? colors.selected : 'transparent',
            })}
          >
            <Icon name="panel-left" size="md" color={colors.ink2} />
          </Pressable>
        ) : null}
        {activityButton}
        {searchToggle}
      </View>
      <Pressable
        onPress={onConnPress}
        style={trigger}
        accessibilityRole="button"
        accessibilityLabel={`Connection ${name}, ${host}`}
      >
        {identity}
      </Pressable>
    </View>
  );
}
