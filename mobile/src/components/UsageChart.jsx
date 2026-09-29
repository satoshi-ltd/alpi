import { useState } from 'react';
import { Pressable, Text, View } from 'react-native';

import { mixHex } from '../../../common/color.mjs';
import { fmtTok, formatUsd } from '../../../common/format.mjs';
import {
  barHeights,
  costOf,
  hasUsage,
  pctLeft,
  todayOf,
  tokensOf,
  usageScale,
  usageTotals,
} from '../../../common/usage.mjs';
import { alpha, lineHeights, space, tracking } from '../theme/tokens';
import { Eyebrow } from './Eyebrow';
import { useTheme } from '../theme/ThemeContext';
import { usageRangeEmpty } from '../../../common/emptyCopy.mjs';

export const CHART_H = 104;
const BAR_MAX_W = 20;
const RING_W = 1.5;
const IN_TINT = 0.24;

function Stat({ label, children }) {
  const { fonts, fontSizes } = useTheme();
  return (
    <View style={{ flex: 1, minWidth: 0 }}>
      <Eyebrow style={{ fontFamily: fonts.mono, letterSpacing: fontSizes.xs * tracking.wider, marginBottom: space.s2 }}>
        {label}
      </Eyebrow>
      {children}
    </View>
  );
}

function MonoStat({ value, unit }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <Text
      numberOfLines={1}
      style={{
        fontFamily: fonts.monoMedium,
        fontSize: fontSizes.xl,
        lineHeight: fontSizes.xl * lineHeights.tight,
        color: colors.ink,
        fontVariant: ['tabular-nums'],
      }}
    >
      {value}
      {unit ? (
        <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>{` ${unit}`}</Text>
      ) : null}
    </Text>
  );
}

function Swatch({ color }) {
  return <View style={{ width: 9, height: 9, borderRadius: 2, backgroundColor: color }} />;
}

export const NARROW_TILES_W = 520;

export function UsageChart({ days = [], accent, capLine = null, total30 = null, height = CHART_H }) {
  const { colors, fonts, fontSizes } = useTheme();
  const [selected, setSelected] = useState(null);
  const [tilesW, setTilesW] = useState(0);
  if (!days.length) return null;
  const narrow = tilesW > 0 && tilesW < NARROW_TILES_W;
  const empty = !hasUsage(days);

  const tint = accent ?? colors.accent;
  const inColor = mixHex(tint, IN_TINT, colors.bgPane);
  const today = todayOf(days);
  const totals = usageTotals(days);
  const avg = totals.cost / days.length;
  const scale = usageScale(days);
  const capNum = typeof capLine === 'number' && capLine > 0 ? capLine : null;
  const todayCost = costOf(today);
  const left = pctLeft(todayCost, capNum);
  const picked = !empty && selected != null && selected < days.length ? days[selected] : null;

  const foot = total30
    ? `30-day total ${formatUsd(total30.cost || 0)} · ${fmtTok(total30.tokIn || 0)} in / ${fmtTok(total30.tokOut || 0)} out`
    : `14-day total ${formatUsd(totals.cost)} · ${fmtTok(totals.tokIn)} in / ${fmtTok(totals.tokOut)} out`;

  return (
    <View>
      <View
        onLayout={(e) => setTilesW(e.nativeEvent.layout.width)}
        style={{
          flexDirection: 'row',
          alignItems: 'flex-start',
          paddingBottom: space.s6,
          borderBottomWidth: 0.5,
          borderBottomColor: colors.line2,
        }}
      >
        <Stat label="Today">
          <Text
            numberOfLines={1}
            style={{
              fontFamily: fonts.sans.semibold,
              fontSize: fontSizes.display,
              lineHeight: fontSizes.display * lineHeights.tight,
              letterSpacing: fontSizes.display * tracking.tight,
              color: tint,
              fontVariant: ['tabular-nums'],
            }}
          >
            {formatUsd(todayCost)}
          </Text>
        </Stat>
        <Stat label="Input">
          <MonoStat value={fmtTok(today.tokIn || 0)} unit={narrow ? null : 'tok'} />
        </Stat>
        <Stat label="Output">
          <MonoStat value={fmtTok(today.tokOut || 0)} unit={narrow ? null : 'tok'} />
        </Stat>
        <Stat label={capNum == null ? 'Avg / day' : narrow ? `Cap · ${left}% left` : 'Cap / day'}>
          <MonoStat
            value={formatUsd(capNum != null ? capNum : avg)}
            unit={capNum != null && !narrow ? `${left}% left` : null}
          />
        </Stat>
      </View>

      {empty ? (
        <Text
          accessibilityLabel="No usage"
          style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink4, marginTop: space.s6 }}
        >
          {usageRangeEmpty(days.length)}
        </Text>
      ) : null}
      {empty ? null : (
      <View style={{ marginTop: space.s8 }}>
        <View style={{ height, flexDirection: 'row', alignItems: 'flex-end', gap: space.s1 }}>
          {days.map((d, i) => {
            const { total, out } = barHeights(d, scale, height);
            const hasData = tokensOf(d) > 0 || costOf(d) > 0;
            const dim = picked != null && selected !== i;
            const bar = (
              <View
                style={{
                  width: '100%',
                  maxWidth: BAR_MAX_W,
                  height: total,
                  borderRadius: 3,
                  overflow: 'hidden',
                  opacity: dim ? alpha.faint : 1,
                }}
              >
                <View style={{ height: out, backgroundColor: tint }} />
                <View style={{ flex: 1, backgroundColor: inColor }} />
              </View>
            );
            return (
              <Pressable
                key={d.iso}
                accessibilityLabel={`${d.day} usage`}
                onPress={() => setSelected(hasData ? (selected === i ? null : i) : null)}
                style={{ flex: 1, height: '100%', justifyContent: 'flex-end', alignItems: 'center' }}
              >
                {d.today && total > 0 ? (
                  <View
                    style={{
                      width: '100%',
                      maxWidth: BAR_MAX_W + RING_W * 4,
                      padding: RING_W,
                      borderRadius: 3 + RING_W * 2,
                      borderWidth: RING_W,
                      borderColor: tint,
                      backgroundColor: colors.bgPane,
                      alignItems: 'center',
                    }}
                  >
                    {bar}
                  </View>
                ) : (
                  bar
                )}
              </Pressable>
            );
          })}
        </View>
        <View style={{ flexDirection: 'row', gap: space.s1, marginTop: space.s3 }}>
          {days.map((d) => (
            <Text
              key={d.iso}
              style={{
                flex: 1,
                textAlign: 'center',
                fontFamily: d.today ? fonts.monoSemibold : fonts.mono,
                fontSize: fontSizes.xxs,
                lineHeight: fontSizes.xxs * lineHeights.tight,
                color: d.today ? tint : colors.ink3,
              }}
            >
              {d.label}
            </Text>
          ))}
        </View>
      </View>
      )}

      {picked ? (
        <View
          accessibilityLabel="Selected day"
          style={{ flexDirection: 'row', alignItems: 'baseline', gap: space.s4, marginTop: space.s5, flexWrap: 'wrap' }}
        >
          <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.label, color: colors.ink4 }}>
            {picked.day}
            {picked.today ? ' · today' : ''}
          </Text>
          <Text
            style={{
              fontFamily: fonts.sans.semibold,
              fontSize: fontSizes.xl,
              lineHeight: fontSizes.xl * lineHeights.tight,
              color: colors.ink,
              fontVariant: ['tabular-nums'],
            }}
          >
            {formatUsd(costOf(picked))}
          </Text>
          <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink2 }}>
            {`${fmtTok(picked.tokIn || 0)} in / ${fmtTok(picked.tokOut || 0)} out`}
          </Text>
        </View>
      ) : null}

      {empty ? null : (
      <View
        style={{
          flexDirection: 'row',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: space.s3,
          marginTop: space.s6,
        }}
      >
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s2 }}>
          <Swatch color={inColor} />
          <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.xs, color: colors.ink3 }}>input</Text>
          <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.xs, color: colors.ink4 }}>·</Text>
          <Swatch color={tint} />
          <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.xs, color: colors.ink3 }}>output</Text>
        </View>
        <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3, fontVariant: ['tabular-nums'] }}>
          {foot}
        </Text>
      </View>
      )}
    </View>
  );
}
