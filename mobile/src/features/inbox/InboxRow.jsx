import { memo, useCallback, useMemo } from 'react';
import { Keyboard, Pressable, StyleSheet, Text, View } from 'react-native';
import { lineHeights, mobile, radii, space, status, typeLeading } from '../../theme/tokens';

import { FALLBACK_ACCENT } from '../../../../common/shapes.mjs';
import { MARK_SIZES } from '../../../../common/agentMarks.mjs';
import { nameColor, nameStyle } from '../../theme/name';
import { Glyph } from '../../components/Glyph';
import { sessionMarkKey, useSharedSessionMark } from '../../lib/sessionMark';
import { usePane } from '../../nav/PaneContext';
import { useTheme } from '../../theme/ThemeContext';
import { Pip } from './Pip';
import { RowState, STATE_TEXT } from './RowState';

export const GLYPH_SLOT = MARK_SIZES.list;
export const ROW_H = 64;
export const ROW_GUTTER = space.s3;
const PIP_SIZE = 10;
const PIP_RING = 2;
const PIP_BLEED = 2;

const STATIC = StyleSheet.create({
  row: {
    minHeight: ROW_H,
    marginHorizontal: ROW_GUTTER,
    paddingHorizontal: space.s7 - ROW_GUTTER,
    borderRadius: radii.control,
    paddingVertical: space.s3,
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.s5,
  },
  tile: {
    alignSelf: 'stretch',
    alignItems: 'center',
    gap: space.s2,
    paddingVertical: space.s3,
    borderRadius: radii.surface - space.s1,
  },
  tileMark: { width: MARK_SIZES.tile, height: MARK_SIZES.tile },
  tilePip: { position: 'absolute', top: -PIP_BLEED, right: -PIP_BLEED, width: PIP_SIZE, height: PIP_SIZE, borderRadius: radii.pill, borderWidth: PIP_RING },
  compactRow: {
    minHeight: mobile.tap,
    marginHorizontal: space.s5,
    paddingHorizontal: space.s4,
    paddingVertical: space.s2,
    borderRadius: radii.control,
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.s5,
  },
  glyph: { width: GLYPH_SLOT, alignItems: 'center', justifyContent: 'center', flexShrink: 0 },
  compactGlyph: { width: MARK_SIZES.row, alignItems: 'center', justifyContent: 'center', flexShrink: 0 },
  body: { flex: 1, minWidth: 0, flexDirection: 'column', gap: space.s1 },
  meta: { alignItems: 'flex-end', justifyContent: 'center', gap: space.s1, flexShrink: 0 },
  pip: { width: 16, height: 16 },
});

export const InboxRow = memo(function InboxRow({ item, onPress, onLongPress, selected = false, showState = false, offline = false, tile = false, full = false }) {
  const { colors, fonts, fontSizes } = useTheme();
  const { twoPane } = usePane();
  const compact = twoPane && !full;
  const accent = item.accent ?? FALLBACK_ACCENT;

  const unread = !!item.unread && !item.needsProvider;
  const needsProvider = !!item.needsProvider;
  const muted = needsProvider || !!item.paused;
  const liveState = item.activity?.state ? item.activity : null;
  const rowState = offline && liveState?.state === 'working' ? null : liveState;
  const working = !offline && !rowState && showState && item.state === 'working';
  const needsYou = rowState?.state === 'needs-you';
  const shared = useSharedSessionMark(selected && item.kind !== 'workgroup' ? sessionMarkKey(item.id) : null);
  const sessionState = offline ? null : shared;
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

  const handlePress = useCallback(() => {
    Keyboard.dismiss();
    onPress?.(item);
  }, [onPress, item]);
  const handleLongPress = useCallback(() => onLongPress?.(item), [onLongPress, item]);

  const rowStyle = useCallback(
    ({ pressed }) => [
      tile ? STATIC.tile : compact ? STATIC.compactRow : STATIC.row,
      { backgroundColor: pressed ? colors.pressed : selected ? colors.selected : 'transparent' },
    ],
    [tile, compact, colors, selected],
  );

  const nameVariant = useMemo(() => {
    if (!compact) {
      return {
        fontFamily: unread || needsYou ? fonts.sans.bold : fonts.sans.semibold,
        fontSize: fontSizes.md,
        lineHeight: Math.round(fontSizes.md * typeLeading.ui),
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
      lineHeight: Math.round(fontSizes.md * typeLeading.ui),
      color: muted ? colors.ink3 : unread || selected || needsYou ? colors.ink : colors.ink2,
    };
  }, [compact, unread, needsYou, selected, muted, fonts, fontSizes, colors]);
  const previewVariant = useMemo(
    () => ({
      fontFamily: fonts.sans.regular,
      fontSize: fontSizes.sm,
      lineHeight: Math.round(fontSizes.sm * typeLeading.small),
      fontStyle: needsProvider ? 'italic' : 'normal',
      color: needsProvider ? colors.ink3 : item.previewTone === 'warning' ? colors.warningText : item.previewTone === 'danger' ? colors.dangerText : colors.ink2,
    }),
    [needsProvider, item.previewTone, fonts, fontSizes, colors],
  );
  const tsVariant = useMemo(
    () => ({
      fontFamily: fonts.sans.medium,
      fontSize: fontSizes.xs,
      lineHeight: fontSizes.xs * lineHeights.tight,
      color: selected ? colors.ink2 : colors.ink3,
    }),
    [selected, fonts, fontSizes, colors],
  );

  if (tile) {
    const pip = needsYou ? status.warning : rowState?.state === 'failed' ? status.danger : unread ? colors.ink : null;
    return (
      <Pressable
        onPress={handlePress}
        onLongPress={handleLongPress}
        android_ripple={{ color: colors.pressed }}
        accessibilityRole="button"
        accessibilityLabel={spoken}
        accessibilityState={{ selected }}
        style={rowStyle}
      >
        <View style={STATIC.tileMark}>
          <Glyph
            kind={item.kind}
            color={accent}
            shape={item.shape}
            name={item.id}
            active={selected}
            state={item.kind === 'workgroup' ? null : sessionState}
            needsProvider={needsProvider}
            working={!offline && (item.state === 'working' || rowState?.state === 'working')}
            paused={!!item.paused}
            offline={offline}
            rowState={rowState?.state ?? null}
            unread={unread}
            phase={rowState?.phases ?? null}
            phaseSlug={rowState?.phase ?? null}
            workgroup={item.raw ?? null}
            accentOf={item.accentOf ?? null}
            size={MARK_SIZES.tile}
          />
          {pip ? <View testID="tile-pip" style={[STATIC.tilePip, { backgroundColor: pip, borderColor: twoPane ? colors.bgSide : colors.bg }]} /> : null}
        </View>
        <Text numberOfLines={1} style={[nameStyle(fontSizes.sm, muted ? colors.ink3 : item.kind === 'workgroup' ? colors.ink : nameColor(accent, colors)), { alignSelf: 'stretch', textAlign: 'center' }]}>
          {label}
        </Text>
      </Pressable>
    );
  }

  return (
    <Pressable
      onPress={handlePress}
      onLongPress={handleLongPress}
      android_ripple={{ color: colors.pressed }}
      accessibilityRole="button"
      accessibilityLabel={spoken}
      accessibilityState={{ selected }}
      style={rowStyle}
    >
      <View style={compact ? STATIC.compactGlyph : STATIC.glyph}>
        <Glyph
          kind={item.kind}
          color={accent}
          shape={item.shape}
          name={item.id}
          active={selected}
          state={item.kind === 'workgroup' ? null : sessionState}
          needsProvider={needsProvider}
          working={!offline && (item.state === 'working' || rowState?.state === 'working')}
          paused={!!item.paused}
          offline={offline}
          rowState={rowState?.state ?? null}
          unread={unread}
          phase={rowState?.phases ?? null}
          phaseSlug={rowState?.phase ?? null}
          workgroup={item.raw ?? null}
          accentOf={item.accentOf ?? null}
          size={compact ? MARK_SIZES.row : MARK_SIZES.list}
        />
      </View>
      <View style={STATIC.body}>
        <Text numberOfLines={1} style={nameVariant}>
          {label}
        </Text>
        {compact ? null : (
          <Text numberOfLines={1} style={previewVariant}>
            {item.preview}
          </Text>
        )}
      </View>
      {item.ts || working || rowState || item.paused ? (
        <View style={STATIC.meta}>
          {item.ts ? <Text style={tsVariant}>{item.ts}</Text> : null}
          {item.paused && !needsProvider ? (
            <Text style={{ fontFamily: fonts.sans.medium, fontSize: fontSizes.xs, lineHeight: fontSizes.xs * lineHeights.tight, color: colors.ink3 }}>paused</Text>
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
