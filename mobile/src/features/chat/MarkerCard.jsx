import { StyleSheet, Text, View } from 'react-native';
import { radii, space, lineHeights, tracking } from '../../theme/tokens';

import { Diamond } from '../../components/Diamond';
import { Icon } from '../../components/Icon';
import { Dot } from '../../components/Dot';
import { RichText } from '../../components/RichText';
import { BUBBLE_MAX_PANE } from '../../lib/panes';
import { usePane } from '../../nav/PaneContext';
import { useTheme } from '../../theme/ThemeContext';

const TINTS = { task: 0.18, working: 0.14, done: 0.18, skip: 0.12 };
const LABELS = { task: 'TASK', working: 'WORKING', done: 'DONE', skip: 'SKIP' };

const S = StyleSheet.create({
  wrapLeft: { alignItems: 'flex-start', paddingHorizontal: space.s7, gap: space.s1 },
  wrapRight: { alignItems: 'flex-end', paddingHorizontal: space.s7, gap: space.s1 },
  row: { flexDirection: 'row', alignItems: 'center', gap: space.s2 },
  card: {
    maxWidth: '90%',
    paddingHorizontal: space.s7,
    paddingVertical: space.s6,
  },
  cardCompact: { paddingVertical: space.s4 },
  paneCap: { maxWidth: BUBBLE_MAX_PANE },
  eyebrowRow: { flexDirection: 'row', alignItems: 'center', gap: space.s2, marginBottom: space.s2 },
  iconSlot: { width: 14, alignItems: 'center', justifyContent: 'center' },
  title: { marginBottom: space.s2 },
  skipDot: { width: 10, height: 10, borderRadius: 5, borderWidth: 1.5, overflow: 'hidden' },
  skipBar: { position: 'absolute', width: 14, height: 1.5, top: 3.5, left: -2.5, transform: [{ rotate: '45deg' }] },
  taskDot: { width: 6, height: 6, borderRadius: 3 },
});

function mixHex(hex, pct, base) {
  const fromHex = (h) => {
    const v = h.replace('#', '');
    return [parseInt(v.slice(0, 2), 16), parseInt(v.slice(2, 4), 16), parseInt(v.slice(4, 6), 16)];
  };
  const [r1, g1, b1] = fromHex(hex);
  const [r2, g2, b2] = fromHex(base);
  const r = Math.round(r1 * pct + r2 * (1 - pct));
  const g = Math.round(g1 * pct + g2 * (1 - pct));
  const b = Math.round(b1 * pct + b2 * (1 - pct));
  return `rgb(${r},${g},${b})`;
}

function MarkerIcon({ variant, color, stale }) {
  if (variant === 'working') {
    return stale
      ? <View style={[S.taskDot, { backgroundColor: color }]} />
      : <Dot color={color} pulse />;
  }
  if (variant === 'done') {
    return <Icon name="check" size="xs" strokeWidth={2.2} color={color} />;
  }
  if (variant === 'skip') {
    return (
      <View style={[S.skipDot, { borderColor: color }]}>
        <View style={[S.skipBar, { backgroundColor: color }]} />
      </View>
    );
  }
  return <View style={[S.taskDot, { backgroundColor: color }]} />;
}

export function MarkerCard({ variant = 'task', side = 'left', hubColor, speakerName, isFromHub, seq, cost, title, children, label, stale = false }) {
  const { colors, fonts, fontSizes } = useTheme();
  const { twoPane } = usePane();
  const pct = TINTS[variant] ?? 0.11;
  const baseAccent = variant === 'skip' ? colors.warning : hubColor ?? colors.ink3;
  const tint = mixHex(baseAccent, pct, colors.bgPane);
  const isRight = side === 'right';
  const hasBody = Boolean(children);
  const compact = !title && !hasBody;
  const corner = isRight
    ? { borderTopLeftRadius: 18, borderTopRightRadius: radii.xs, borderBottomRightRadius: 18, borderBottomLeftRadius: 18 }
    : { borderTopLeftRadius: radii.xs, borderTopRightRadius: 18, borderBottomRightRadius: 18, borderBottomLeftRadius: 18 };

  let costStr = null;
  const tok = typeof cost?.tokens === 'number' ? cost.tokens : 0;
  const usd = typeof cost?.usd === 'number' ? cost.usd : 0;
  if (tok > 0 || usd > 0) {
    const tokFmt = tok >= 1000 ? `${(tok / 1000).toFixed(1)}K` : `${tok}`;
    const usdFmt = usd >= 0.01 ? `$${usd.toFixed(2)}` : `$${usd.toFixed(4)}`;
    costStr = `${tokFmt} · ${usdFmt}`;
  }

  const metaStyle = { fontFamily: fonts.monoMedium, fontSize: fontSizes.xs, lineHeight: fontSizes.xs * lineHeights.cozy, color: colors.ink3 };

  const SpeakerEl = speakerName ? (
    <View style={S.row}>
      {!isRight ? <Diamond color={baseAccent} /> : null}
      <Text style={metaStyle}>{speakerName}</Text>
      {isRight ? <Diamond color={baseAccent} /> : null}
    </View>
  ) : null;

  return (
    <View style={isRight ? S.wrapRight : S.wrapLeft}>
      {speakerName || seq != null || costStr ? (
        <View style={S.row}>
          {isRight ? (
            <>
              {costStr ? <Text style={metaStyle}>{costStr}</Text> : null}
              {seq != null ? <Text style={metaStyle}>{`#${seq}`}</Text> : null}
              {SpeakerEl}
            </>
          ) : (
            <>
              {SpeakerEl}
              {seq != null ? <Text style={metaStyle}>{`#${seq}`}</Text> : null}
              {costStr ? <Text style={metaStyle}>{costStr}</Text> : null}
            </>
          )}
        </View>
      ) : null}
      <View style={[S.card, twoPane && S.paneCap, compact && S.cardCompact, corner, { backgroundColor: tint }]}>
        <View style={[S.eyebrowRow, compact && { marginBottom: 0 }]}>
          <View style={S.iconSlot}>
            <MarkerIcon variant={variant} color={baseAccent} stale={stale} />
          </View>
          <Text style={{ fontFamily: fonts.monoSemibold, fontSize: fontSizes.xs, lineHeight: fontSizes.xs * lineHeights.cozy, letterSpacing: fontSizes.xs * tracking.wider, color: baseAccent }}>
            {label || LABELS[variant]}
          </Text>
        </View>
        {title ? (
          <Text style={[S.title, { fontFamily: fonts.sans.semibold, fontSize: fontSizes.lg, lineHeight: fontSizes.lg * lineHeights.cozy, letterSpacing: fontSizes.lg * tracking.snug, color: colors.ink }]}>
            {title}
          </Text>
        ) : null}
        {children ? (
          typeof children === 'string'
            ? <RichText size={fontSizes.md} color={colors.ink}>{children}</RichText>
            : children
        ) : null}
      </View>
    </View>
  );
}
