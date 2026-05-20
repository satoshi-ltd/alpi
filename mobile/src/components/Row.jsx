import { Pressable, Text, View } from 'react-native';
import { space , fontSizes} from '../theme/tokens';

import { useTheme } from '../theme/ThemeContext';

export function SectionHeader({ children }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <View style={{ paddingHorizontal: space.s8, paddingTop: space.s9, paddingBottom: space.s3 }}>
      <Text
        style={{
          fontFamily: fonts.mono,
          fontSize: fontSizes.xs,
          letterSpacing: 0.6,
          textTransform: 'uppercase',
          color: colors.ink3,
        }}
      >
        {children}
      </Text>
    </View>
  );
}

export function Row({ label, helper, value, leading, trailing, onPress, onLongPress, danger, chevron = true, labelLines = 1 }) {
  const { colors, fonts, fontSizes } = useTheme();

  const body = (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        paddingHorizontal: space.s8,
        paddingVertical: space.s6,
        gap: space.s5,
        backgroundColor: colors.bgPane,
      }}
    >
      {leading ? <View>{leading}</View> : null}
      {/* Label container shrinks but always renders its label (min-width: 0 + flexShrink: 1 lets the value truncate before the label disappears). */}
      <View style={{ flex: 1, minWidth: 0, gap: space.s1 }}>
        <Text
          numberOfLines={labelLines}
          ellipsizeMode="tail"
          style={{
            fontFamily: fonts.sans.regular,
            fontSize: fontSizes.lg,
            color: danger ? colors.danger : colors.ink,
            lineHeight: fontSizes.lg * 1.3,
          }}
        >
          {label}
        </Text>
        {helper ? (
          <Text
            numberOfLines={1}
            style={{
              fontFamily: fonts.monoMedium,
              fontSize: fontSizes.xs,
              color: colors.ink4,
            }}
          >
            {helper}
          </Text>
        ) : null}
      </View>
      {value ? (
        typeof value === 'string' ? (
          <Text
            style={{
              fontFamily: fonts.sans.regular,
              fontSize: fontSizes.md,
              color: colors.ink3,
              flexShrink: 1,
              textAlign: 'right',
              maxWidth: '55%',
            }}
            numberOfLines={1}
            ellipsizeMode="middle"
          >
            {value}
          </Text>
        ) : (
          <View style={{ flexShrink: 0, maxWidth: '55%' }}>{value}</View>
        )
      ) : null}
      {trailing}
      {chevron && onPress && !danger ? (
        <Text style={{ color: colors.ink4, fontSize: fontSizes.xl }}>›</Text>
      ) : null}
    </View>
  );

  if (!onPress && !onLongPress) return body;
  return (
    <Pressable
      onPress={onPress}
      onLongPress={onLongPress}
      android_ripple={{ color: colors.selected }}
      style={({ pressed }) => ({ backgroundColor: pressed ? colors.selected : 'transparent' })}
    >
      {body}
    </Pressable>
  );
}

export function RowSeparator({ indent = 20 }) {
  const { colors } = useTheme();
  return <View style={{ height: 0.5, backgroundColor: colors.line, marginLeft: indent }} />;
}
