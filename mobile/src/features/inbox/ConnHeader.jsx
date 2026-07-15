import { Pressable, Text, View } from 'react-native';
import { lineHeights, radii, space } from '../../theme/tokens';

import { Icon } from '../../components/Icon';
import { useTheme } from '../../theme/ThemeContext';


export function ConnHeader({
  name = 'Local',
  host = 'host.sock',
  status = 'online',
  unread = 0,
  onConnPress,
  onBellPress,
  onGearPress,
}) {
  const { colors, fonts, fontSizes } = useTheme();
  const statusColor =
    status === 'online' || status === 'connected'
      ? colors.success
      : status === 'offline' || status === 'auth-failed'
        ? colors.danger
        : status === 'disabled'
          ? colors.ink3
        : colors.warning;

  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        gap: space.s3,
        paddingHorizontal: space.s5,
        paddingTop: space.s3,
        paddingBottom: space.s4,
        backgroundColor: colors.bg,
      }}
    >
      <Pressable
        onPress={onConnPress}
        style={({ pressed }) => ({
          flexDirection: 'row',
          alignItems: 'center',
          gap: space.s3,
          paddingLeft: space.s3,
          paddingRight: space.s4,
          paddingVertical: space.s2,
          backgroundColor: pressed ? colors.selected : colors.bgInput,
          borderRadius: radii.pill,
          maxWidth: 200,
          minWidth: 0,
        })}
      >
        <View style={{ position: 'relative' }}>
          <Icon name="cpu" size={16} color={colors.ink2} strokeWidth={1.7} />
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
              borderColor: colors.bgInput,
            }}
          />
        </View>
        <View style={{ flexDirection: 'column', minWidth: 0 }}>
          <Text
            numberOfLines={1}
            style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.base, lineHeight: fontSizes.base * lineHeights.cozy, color: colors.ink }}
          >
            {name}
          </Text>
          <Text
            numberOfLines={1}
            style={{ fontFamily: fonts.mono, fontSize: fontSizes.xxs, lineHeight: fontSizes.xxs * lineHeights.cozy, color: colors.ink3 }}
          >
            {host}
          </Text>
        </View>
        <Icon name="chevright" size={11} color={colors.ink3} strokeWidth={2} />
      </Pressable>

      <View style={{ flex: 1 }} />

      {onBellPress ? (
        <Pressable
          onPress={onBellPress}
          style={({ pressed }) => ({
            width: 38,
            height: 38,
            borderRadius: radii.md,
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: pressed ? colors.selected : 'transparent',
            position: 'relative',
          })}
        >
          <Icon name="bell" size={22} color={colors.ink2} strokeWidth={1.7} />
          {unread > 0 ? (
            <View
              style={{
                position: 'absolute',
                top: 2,
                right: 2,
                minWidth: space.s6,
                height: space.s6,
                paddingHorizontal: space.s1,
                borderRadius: radii.pill,
                backgroundColor: colors.danger,
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.xxs, lineHeight: space.s6, color: '#fff' }}>
                {unread}
              </Text>
            </View>
          ) : null}
        </Pressable>
      ) : null}

      <Pressable
        onPress={onGearPress}
        style={({ pressed }) => ({
          width: 38,
          height: 38,
          borderRadius: radii.md,
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: pressed ? colors.selected : 'transparent',
        })}
      >
        <Icon name="gear" size={22} color={colors.ink2} strokeWidth={1.7} />
      </Pressable>
    </View>
  );
}
