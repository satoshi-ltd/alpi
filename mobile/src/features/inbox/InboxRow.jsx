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
export const SELECTED_BAR = 3;
export const selectedFill = (colors) => `${colors.ink}12`;
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

export const InboxRow = memo(function InboxRow({ item, onPress, onLongPress, selected = false, showState = false, offline = false }) {
  const { colors, fonts, fontSizes } = useTheme();
  const { twoPane } = usePane();
  const accent = item.accent ?? FALLBACK_ACCENT;

  const unread = !!item.unread && !item.needsProvider;
  const needsProvider = !!item.needsProvider;
  const muted = needsProvider || !!item.paused;
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
    item.paused ? 'paused' : null,
    item.preview,
    item.ts,
  ].filter(Boolean).join(', ');

  const handlePress = useCallback(() => onPress?.(item), [onPress, item]);
  const handleLongPress = useCallback(() => onLongPress?.(item), [onLongPress, item]);

  const rowStyle = useCallback(
    ({ pressed }) => [
      twoPane ? STATIC.compactRow : STATIC.row,
      twoPane && selected ? STATIC.tab : null,
      { backgroundColor: selected ? selectedFill(colors) : pressed ? colors.selected : 'transparent' },
    ],
    [twoPane, colors, selected],
  );

  const nameVariant = useMemo(() => {
    if (!twoPane) {
      return {
        fontFamily: unread || needsYou ? fonts.sans.bold : fonts.sans.semibold,
        fontSize: fontSizes.lg,
        lineHeight: fontSizes.lg * lineHeights.cozy,
        color: muted ? colors.ink3 : colors.ink,
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
      color: muted ? colors.ink3 : unread || selected || needsYou ? colors.ink : colors.ink2,
    };
  }, [twoPane, unread, needsYou, selected, muted, fonts, fontSizes, colors]);
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
      accessibilityState={{ selected }}
      style={rowStyle}
    >
      {selected ? (
        <View
          testID="selected-bar"
          pointerEvents="none"
          style={{ position: 'absolute', left: 0, top: space.s2, bottom: space.s2, width: SELECTED_BAR, borderTopRightRadius: radii.tag, borderBottomRightRadius: radii.tag, backgroundColor: accent }}
        />
      ) : null}
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
      {item.ts || working || rowState || item.paused ? (
        <View style={STATIC.meta}>
          {item.ts ? <Text style={tsVariant}>{item.ts}</Text> : null}
          {item.paused && !needsProvider ? (
            <Text style={{ fontFamily: fonts.monoMedium, fontSize: fontSizes.xs, lineHeight: fontSizes.xs * lineHeights.tight, color: colors.ink3 }}>paused</Text>
          ) : null}
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
