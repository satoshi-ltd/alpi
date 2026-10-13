import { useState } from 'react';
import { Text, View, useWindowDimensions } from 'react-native';
import Svg, { Circle, Line, Polyline, Rect, Text as SvgText } from 'react-native-svg';

import { chartCaption, chartLayout, chartLegend, describeChart } from '../../../common/chartSpec.mjs';
import { mixHex } from '../../../common/color.mjs';
import { BUBBLE_MAX_PANE, paneWidth } from '../lib/panes';
import { usePane } from '../nav/PaneContext';
import { useTheme } from '../theme/ThemeContext';
import { space } from '../theme/tokens';

const COMPACT_WIDTH = 420;
const BUBBLE_SHARE = parseFloat(BUBBLE_MAX_PANE) / 100;
const BUBBLE_INSET = 32;

export function Chart({ spec, accent = null }) {
  const { colors, fonts, fontSizes } = useTheme();
  const [width, setWidth] = useState(0);
  const screen = useWindowDimensions();
  const { twoPane, sidebarOpen } = usePane();
  const floor = Math.max(Math.min(Math.round((paneWidth(screen.width, twoPane, sidebarOpen) - BUBBLE_INSET) * BUBBLE_SHARE) - BUBBLE_INSET, 300), 0);
  const tinted = typeof accent === 'string' && /^#(?:[0-9a-f]{3}){1,2}$/i.test(accent);
  const palette = tinted
    ? [accent, mixHex(accent, 0.58, colors.ink), mixHex(accent, 0.4, colors.bgPane), mixHex(accent, 0.55, colors.ink3)]
    : [colors.ink, colors.ink3, colors.ink4, colors.ink2];
  const compact = width > 0 && width < COMPACT_WIDTH;
  const layout = width > 0 ? chartLayout(spec, { width, height: compact ? 150 : 170, compact }) : null;
  const legend = chartLegend(spec);

  return (
    <View accessible accessibilityRole="image" accessibilityLabel={describeChart(spec)} style={{ gap: space.s3, minWidth: floor }} onLayout={(e) => setWidth(Math.floor(e.nativeEvent.layout.width))}>
      {chartCaption(spec) ? <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.sm, color: colors.ink }}>{chartCaption(spec)}</Text> : null}
      {layout ? (
        <Svg width={layout.width} height={layout.height}>
          {layout.items.map((it, i) => {
            const colour = palette[it.series ?? 0];
            if (it.k === 'grid') return <Line key={i} x1={it.x1} x2={it.x2} y1={it.y} y2={it.y} stroke={colors.line2} strokeWidth={0.5} />;
            if (it.k === 'line') {
              return (
                <Polyline key={i} points={it.points.map(([x, y]) => `${x},${y}`).join(' ')} fill="none" stroke={colour}
                  strokeWidth={it.series > 0 ? 1.5 : 2} strokeDasharray={it.series > 0 ? '3 3' : undefined} strokeLinejoin="round" strokeLinecap="round" />
              );
            }
            if (it.k === 'dot') return <Circle key={i} cx={it.cx} cy={it.cy} r={it.r} fill={colour} />;
            if (it.k === 'bar') return <Rect key={i} x={it.x} y={it.y} width={it.w} height={Math.max(it.h, 0)} fill={colour} />;
            const value = it.k === 'value';
            return (
              <SvgText key={i} x={it.x} y={it.y} textAnchor={it.anchor} fontFamily={it.k === 'label' ? fonts.sans.regular : fonts.mono}
                fontSize={it.k === 'label' ? 11 : 10} fill={value ? colors.ink : it.k === 'label' ? colors.ink2 : colors.ink3}>
                {it.text}
              </SvgText>
            );
          })}
        </Svg>
      ) : null}
      {legend.length ? (
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: space.s4 }}>
          {legend.map((l) => (
            <View key={l.series} style={{ flexDirection: 'row', alignItems: 'center', gap: space.s2 }}>
              <View style={l.dashed
                ? { width: 12, borderTopWidth: 1.5, borderStyle: 'dashed', borderColor: palette[l.series] }
                : { width: 9, height: 9, borderRadius: 2, backgroundColor: palette[l.series] }}
              />
              <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink2 }}>{l.name}</Text>
            </View>
          ))}
        </View>
      ) : null}
    </View>
  );
}
