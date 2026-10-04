import { memo, useCallback, useMemo } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { lineHeights, mobile, radii, space } from '../../theme/tokens';

import { FALLBACK_ACCENT } from '../../../../common/folds.mjs';
import { Glyph } from '../../components/Glyph';
import { usePane } from '../../nav/PaneContext';
import { useTheme } from '../../theme/ThemeContext';
import { Pip } from './Pip';
import { RowState, STATE_TEXT } from './RowState';

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
  tab: {
    marginHorizontal: 0,
    paddingHorizontal: space.s4 + space.s5,
    borderRadius: 0,
  },
  compactRow: {
    minHeight: mobile.tap,
    marginHorizontal: space.s5,
    paddingHorizontal: space.s4,
    paddingVertical: space.s2,
    borderRadius: radii.xs,
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
export const InboxRow = memo(function InboxRow({ item, onPress, onLongPress, selected = false, showState = false, offline = false }) {
  const { colors, fonts, fontSizes, alpha } = useTheme();
  const { twoPane } = usePane();
  // item.accent is computed upstream (useInbox); wg items already use the hub profile's accent.
  const accent = item.accent ?? FALLBACK_ACCENT;

  const unread = !!item.unread && !item.needsProvider;
  const needsProvider = !!item.needsProvider;
  const liveState = item.activity?.state ? item.activity : null;
  const rowState = offline && liveState?.state === 'working' ? null : liveState;
  const working = !offline && !rowState && showState && item.state === 'working';
  const needsYou = rowState?.state === 'needs-you';
  const label = item.label ?? item.name ?? item.id;
  const spoken = [
    label,
    unread ? 'unread' : null,
    rowState ? STATE_TEXT[rowState.state] : working ? 'working' : null,
    rowState?.phases ? `phase ${rowState.phases.replace('/', ' of ')}` : null,
    item.preview,
    item.ts,
  ].filter(Boolean).join(', ');

  const handlePress = useCallback(() => onPress?.(item), [onPress, item]);
  const handleLongPress = useCallback(() => onLongPress?.(item), [onLongPress, item]);

  const rowStyle = useCallback(
    ({ pressed }) => [
      twoPane ? STATIC.compactRow : STATIC.row,
      twoPane && selected ? STATIC.tab : null,
      {
        backgroundColor: selected ? colors.bgPane : pressed ? colors.selected : 'transparent',
        opacity: needsProvider || item.paused ? alpha.muted : 1,
      },
    ],
    [twoPane, colors.selected, colors.bgPane, alpha.muted, needsProvider, item.paused, selected],
  );

  const nameVariant = useMemo(() => {
    if (!twoPane) {
      return {
        fontFamily: unread || needsYou ? fonts.sans.bold : fonts.sans.semibold,
        fontSize: fontSizes.lg,
        lineHeight: fontSizes.lg * lineHeights.cozy,
        color: needsProvider ? colors.ink3 : colors.ink,
      };
    }
    return {
      fontFamily: unread || needsYou
        ? fonts.sans.semibold
        : selected
          ? fonts.sans.medium
          : fonts.sans.regular,
      fontSize: fontSizes.md,
      lineHeight: fontSizes.md * lineHeights.cozy,
      color: needsProvider ? colors.ink3 : unread || selected || needsYou ? colors.ink : colors.ink2,
    };
  }, [twoPane, unread, needsYou, selected, needsProvider, fonts, fontSizes, colors]);
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
      accessibilityRole="button"
      accessibilityLabel={spoken}
      style={rowStyle}
    >
      <View style={STATIC.glyph}>
        <Glyph
          kind={item.kind}
          color={accent}
          fold={item.fold}
          needsProvider={needsProvider}
          working={!offline && (item.state === 'working' || rowState?.state === 'working')}
          paused={!!item.paused}
          offline={offline}
        />
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
      {item.ts || working || rowState ? (
        <View style={STATIC.meta}>
          {item.ts ? <Text style={tsVariant}>{item.ts}</Text> : null}
          {rowState ? <RowState state={rowState.state} phases={rowState.phases} color={item.accent} /> : null}
          {working ? (
            <View style={STATIC.pip} accessibilityLabel={`${label} working`}>
              <Pip kind="working" color={accent} bg={colors.bg} />
            </View>
          ) : null}
        </View>
      ) : null}
    </Pressable>
  );
});
