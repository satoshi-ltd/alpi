import { memo, useCallback, useMemo } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { lineHeights, mobile, radii, space } from '../../theme/tokens';

import { Glyph } from '../../components/Glyph';
import { usePane } from '../../nav/PaneContext';
import { accentForProfile } from '../../theme/accents';
import { useTheme } from '../../theme/ThemeContext';
import { Pip } from './Pip';

export const GLYPH_SLOT = space.s9;
export const SEPARATOR_INSET = space.s7 + GLYPH_SLOT + space.s5;

const STATIC = StyleSheet.create({
  row: {
    minHeight: 64,
    paddingHorizontal: space.s7,
    paddingVertical: space.s5,
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.s5,
  },
  compactRow: {
    minHeight: mobile.tap,
    marginHorizontal: space.s5,
    paddingHorizontal: space.s4,
    paddingVertical: space.s3,
    borderRadius: radii.md,
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.s5,
  },
  glyph: { width: GLYPH_SLOT, alignItems: 'center', justifyContent: 'center', flexShrink: 0 },
  body: { flex: 1, minWidth: 0, flexDirection: 'column', gap: space.s1 },
  meta: { alignItems: 'flex-end', justifyContent: 'center', gap: space.s1, flexShrink: 0 },
  pip: { width: 16, height: 16 },
});

// onPress/onLongPress receive `item` so parents can pass stable refs and keep memo() effective.
export const InboxRow = memo(function InboxRow({ item, onPress, onLongPress, selected = false, showState = false }) {
  const { colors, fonts, fontSizes, alpha } = useTheme();
  const { twoPane } = usePane();
  // item.accent is computed upstream (useInbox); wg items already use the hub profile's accent.
  const accent = item.accent ?? accentForProfile(item.id);

  const unread = !!item.unread && !item.needsProvider;
  const needsProvider = !!item.needsProvider;
  const working = showState && item.state === 'working';
  const label = item.label ?? item.name ?? item.id;

  const handlePress = useCallback(() => onPress?.(item), [onPress, item]);
  const handleLongPress = useCallback(() => onLongPress?.(item), [onLongPress, item]);

  const rowStyle = useCallback(
    ({ pressed }) => [
      twoPane ? STATIC.compactRow : STATIC.row,
      {
        backgroundColor: pressed || selected ? colors.selected : 'transparent',
        opacity: needsProvider || item.paused ? alpha.muted : 1,
      },
    ],
    [twoPane, colors.selected, alpha.muted, needsProvider, item.paused, selected],
  );

  const nameVariant = useMemo(() => {
    if (!twoPane) {
      return {
        fontFamily: unread ? fonts.sans.bold : fonts.sans.semibold,
        fontSize: fontSizes.lg,
        lineHeight: fontSizes.lg * lineHeights.cozy,
        color: needsProvider ? colors.ink3 : colors.ink,
      };
    }
    return {
      fontFamily: unread
        ? fonts.sans.semibold
        : selected
          ? fonts.sans.medium
          : fonts.sans.regular,
      fontSize: fontSizes.lg,
      lineHeight: fontSizes.lg * lineHeights.cozy,
      color: needsProvider ? colors.ink3 : unread || selected ? colors.ink : colors.ink2,
    };
  }, [twoPane, unread, selected, needsProvider, fonts, fontSizes, colors]);
  const previewVariant = useMemo(
    () => ({
      fontFamily: needsProvider ? fonts.mono : fonts.sans.regular,
      fontSize: fontSizes.md,
      lineHeight: fontSizes.md * lineHeights.cozy,
      fontStyle: needsProvider ? 'italic' : 'normal',
      color: colors.ink3,
    }),
    [needsProvider, fonts, fontSizes, colors],
  );
  const tsVariant = useMemo(
    () => ({
      fontFamily: unread ? fonts.monoSemibold : fonts.monoMedium,
      fontSize: fontSizes.xs,
      lineHeight: fontSizes.xs * lineHeights.tight,
      color: unread ? colors.ink : colors.ink3,
    }),
    [unread, fonts, fontSizes, colors],
  );

  return (
    <Pressable
      onPress={handlePress}
      onLongPress={handleLongPress}
      android_ripple={{ color: colors.hover }}
      accessibilityLabel={unread ? `${label} unread` : undefined}
      style={rowStyle}
    >
      <View style={STATIC.glyph}>
        <Glyph kind={item.kind} color={accent} needsProvider={needsProvider} />
      </View>
      <View style={STATIC.body}>
        <Text numberOfLines={1} style={nameVariant}>
          {label}
        </Text>
        {twoPane ? null : (
          <Text numberOfLines={1} style={previewVariant}>
            {item.preview}
          </Text>
        )}
      </View>
      <View style={STATIC.meta}>
        {item.ts ? <Text style={tsVariant}>{item.ts}</Text> : null}
        {working ? (
          <View style={STATIC.pip} accessibilityLabel={`${label} working`}>
            <Pip kind="working" color={accent} bg={colors.bg} />
          </View>
        ) : null}
      </View>
    </Pressable>
  );
});
