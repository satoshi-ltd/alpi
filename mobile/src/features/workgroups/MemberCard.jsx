import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { lineHeights, radii, space } from '../../theme/tokens';

import { Fold } from '../../components/Fold';
import { Icon } from '../../components/Icon';
import { nameColor, nameSize, nameStyle } from '../../theme/name';
import { useTheme } from '../../theme/ThemeContext';
import { code } from '../../theme/code';

const STYLES = StyleSheet.create({
  card: {
    paddingHorizontal: space.s7,
    paddingVertical: space.s5,
    gap: space.s2,
    minHeight: 64,
    justifyContent: 'center',
  },
  head: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.s3,
    minHeight: 44,
  },
  name: {
    flexShrink: 1,
  },
  more: {
    marginLeft: 'auto',
    width: 44,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  owns: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: space.s2,
  },
  tag: {
    paddingHorizontal: space.s3,
    paddingVertical: 2,
    borderRadius: radii.pill,
  },
});

export function MemberCard({ label, accent, shape, isHub, bio, owns = null, invited = false, onMore }) {
  const { colors, fonts, fontSizes, fontScale = 1 } = useTheme();
  const [expanded, setExpanded] = useState(false);
  const name = label.replace(/^@/, '');
  return (
    <View style={STYLES.card}>
      <View style={STYLES.head}>
        <Fold shape={shape} color={accent} size="md" />
        <View style={STYLES.name}>
          <Text numberOfLines={1} style={nameStyle(nameSize(fontSizes.xl, fontScale), accent ? nameColor(accent, colors) : colors.ink)}>{accent ? name : label}</Text>
        </View>
        {isHub ? <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink3 }}>hub</Text> : null}
        {invited ? <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink3 }}>invited</Text> : null}
        {onMore ? (
          <Pressable style={STYLES.more} onPress={onMore} accessibilityRole="button" accessibilityLabel={`More for ${label}`}>
            <Icon name="ellipsis" size="md" color={colors.ink2} />
          </Pressable>
        ) : null}
      </View>
      {bio ? (
        <Pressable onPress={() => setExpanded((e) => !e)} hitSlop={{ top: 12, bottom: 12 }} accessibilityRole="button" accessibilityState={{ expanded }}>
          <Text
            numberOfLines={expanded ? undefined : 1}
            style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.md, lineHeight: fontSizes.md * lineHeights.normal, color: colors.ink2 }}
          >
            {bio}
          </Text>
        </Pressable>
      ) : null}
      {Array.isArray(owns) ? (
        <View style={STYLES.owns}>
          <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.xs, color: colors.ink3 }}>owns</Text>
          {owns.length > 0 ? (
            owns.map((slug) => (
              <View key={slug} style={[STYLES.tag, { backgroundColor: colors.selected }]}>
                <Text style={{ ...code(fonts, fontSizes.xs), color: colors.ink2 }}>#{slug}</Text>
              </View>
            ))
          ) : (
            <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.xs, color: colors.ink3 }}>
              {isHub ? 'none · the hub routes every phase' : 'no phase'}
            </Text>
          )}
        </View>
      ) : null}
    </View>
  );
}
