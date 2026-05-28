import { Pressable, Text, View } from 'react-native';
import { radii, space , fontSizes, lineHeights} from '../../theme/tokens';

import { Diamond } from '../../components/Diamond';
import { Icon } from '../../components/Icon';
import { useTheme } from '../../theme/ThemeContext';

export function ChatHeader({ kind, accent, title, meta, onBack, onMore, onPickSession, right }) {
  const { colors, fonts , fontSizes} = useTheme();

  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        gap: space.s4,
        paddingHorizontal: space.s5,
        paddingTop: space.s3,
        paddingBottom: space.s5,
        backgroundColor: colors.bg,
        borderBottomWidth: 0.5,
        borderBottomColor: colors.line,
      }}
    >
      <Pressable
        onPress={onBack}
        hitSlop={8}
        style={{ width: 28, height: 36, alignItems: 'center', justifyContent: 'center', marginLeft: -6 }}
      >
        <Icon name="back" size={22} color={colors.ink2} strokeWidth={2} />
      </Pressable>
      <View style={{ flex: 1, minWidth: 0, flexDirection: 'column' }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s2 }}>
          {kind === 'profile' ? (
            <Diamond color={accent} size={11} />
          ) : (
            <Text style={{ fontFamily: fonts.monoMedium, fontSize: fontSizes.lg, color: colors.ink3 }}>#</Text>
          )}
          <Text
            numberOfLines={1}
            style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.lg, lineHeight: fontSizes.lg * lineHeights.cozy, color: colors.ink }}
          >
            {title}
          </Text>
        </View>
        {meta ? (
          <Text
            numberOfLines={1}
            style={{
              fontFamily: fonts.mono,
              fontSize: fontSizes.xs,
              lineHeight: fontSizes.xs * lineHeights.cozy,
              color: colors.ink3,
              marginTop: 1,
            }}
          >
            {meta}
          </Text>
        ) : null}
      </View>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 0, flexShrink: 0 }}>
        {right}
        {onPickSession ? (
          <Pressable
            onPress={onPickSession}
            style={({ pressed }) => ({
              width: 36,
              height: 36,
              borderRadius: radii.sm,
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: pressed ? colors.selected : 'transparent',
            })}
          >
            <Icon name="clock" size={20} color={colors.ink2} strokeWidth={1.8} />
          </Pressable>
        ) : null}
        {onMore ? (
          <Pressable
            onPress={onMore}
            style={({ pressed }) => ({
              width: 36,
              height: 36,
              borderRadius: radii.sm,
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: pressed ? colors.selected : 'transparent',
            })}
          >
            <Icon name="more" size={22} color={colors.ink2} strokeWidth={1.7} />
          </Pressable>
        ) : null}
      </View>
    </View>
  );
}
