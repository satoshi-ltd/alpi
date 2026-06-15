import { memo, useCallback, useMemo } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { space , fontSizes, lineHeights} from '../../theme/tokens';

import { Dot } from '../../components/Dot';
import { Glyph } from '../../components/Glyph';
import { accentForProfile } from '../../theme/accents';
import { useTheme } from '../../theme/ThemeContext';

const STATIC = StyleSheet.create({
  row: {
    minHeight: 64,
    paddingHorizontal: space.s7,
    paddingVertical: space.s5,
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.s5,
  },
  body: { flex: 1, minWidth: 0, flexDirection: 'column', gap: space.s1 },
  header: { flexDirection: 'row', alignItems: 'center', gap: space.s2 },
  meta: { alignItems: 'flex-end', justifyContent: 'center', gap: space.s1, flexShrink: 0 },
  name: { fontSize: fontSizes.lg, lineHeight: fontSizes.lg * lineHeights.cozy },
  preview: { fontSize: fontSizes.md, lineHeight: fontSizes.md * lineHeights.cozy },
  ts: { fontSize: fontSizes.xs, lineHeight: fontSizes.xs * lineHeights.tight },
});

// onPress/onLongPress receive `item` so parents can pass stable refs and keep memo() effective.
export const InboxRow = memo(function InboxRow({ item, onPress, onLongPress }) {
  const { colors, fonts, alpha , fontSizes} = useTheme();
  // item.accent is computed upstream (useInbox); wg items already use the hub profile's accent.
  const accent = item.accent ?? accentForProfile(item.id);

  const unread = !!item.unread && !item.needsProvider;
  const needsProvider = !!item.needsProvider;
  const label = item.kind === 'workgroup'
    ? `#${item.label ?? item.name ?? item.id}`
    : (item.label ?? item.name ?? item.id);

  const handlePress = useCallback(() => onPress?.(item), [onPress, item]);
  const handleLongPress = useCallback(() => onLongPress?.(item), [onLongPress, item]);

  const rowStyle = useCallback(
    ({ pressed }) => [
      STATIC.row,
      {
        backgroundColor: pressed ? colors.selected : 'transparent',
        opacity: needsProvider || item.paused ? alpha.muted : 1,
      },
    ],
    [colors.selected, alpha.muted, needsProvider, item.paused],
  );

  const nameVariant = useMemo(
    () => ({
      fontFamily: unread ? fonts.sans.bold : fonts.sans.semibold,
      color: needsProvider ? colors.ink3 : colors.ink,
    }),
    [unread, needsProvider, fonts, colors],
  );
  const previewVariant = useMemo(
    () => ({
      fontFamily: needsProvider ? fonts.mono : fonts.sans.regular,
      fontStyle: needsProvider ? 'italic' : 'normal',
      color: unread ? colors.ink2 : colors.ink3,
    }),
    [needsProvider, unread, fonts, colors],
  );
  const tsVariant = useMemo(
    () => ({
      fontFamily: unread ? fonts.monoSemibold : fonts.monoMedium,
      color: unread ? colors.ink : colors.ink3,
    }),
    [unread, fonts, colors],
  );

  return (
    <Pressable
      onPress={handlePress}
      onLongPress={handleLongPress}
      android_ripple={{ color: colors.hover }}
      style={rowStyle}
    >
      <Glyph kind={item.kind} color={accent} size={36} needsProvider={needsProvider} />
      <View style={STATIC.body}>
        <View style={STATIC.header}>
          <Text numberOfLines={1} style={[STATIC.name, nameVariant]}>
            {label}
          </Text>
          {item.pinned ? (
            <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink4 }}>·</Text>
          ) : null}
        </View>
        <Text numberOfLines={1} style={[STATIC.preview, previewVariant]}>
          {item.preview}
        </Text>
      </View>
      <View style={STATIC.meta}>
        {item.ts ? <Text style={[STATIC.ts, tsVariant]}>{item.ts}</Text> : null}
        {unread ? <Dot color={colors.accent} /> : null}
      </View>
    </Pressable>
  );
});
