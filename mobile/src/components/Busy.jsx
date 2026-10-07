import { useEffect, useMemo, useRef } from 'react';
import { Animated, Easing, Text, View } from 'react-native';
import Svg, { Polygon } from 'react-native-svg';

import { ALPACA_FOLD, BRAND_INK, foldPolygons } from '../../../common/folds.mjs';
import { BUSY_LABEL, BUSY_MIN_MARK_PX, BUSY_WAVE_S, busyFacetDelays } from '../../../common/busy.mjs';
import { useBusyVisible } from '../hooks/useBusyVisible';
import { busyWaveRange } from '../lib/busyWave';
import { useReduceMotion } from '../lib/reduceMotion';
import { useTheme } from '../theme/ThemeContext';
import { space } from '../theme/tokens';

const INLINE_MAX = 24;

const pointsOf = (points) => points.map((p) => p.map((v) => v.toFixed(2)).join(',')).join(' ');

const facet = ({ points, fill }, i) => <Polygon key={i} points={pointsOf(points)} fill={fill} />;

function Wave({ polygons, px }) {
  const driver = useRef(new Animated.Value(0)).current;
  const facets = useMemo(() => {
    const delays = busyFacetDelays(polygons.length);
    return polygons.map((_, i) => driver.interpolate(busyWaveRange(delays[i])));
  }, [polygons, driver]);
  useEffect(() => {
    const loop = Animated.loop(Animated.timing(driver, { toValue: 1, duration: BUSY_WAVE_S * 1000, easing: Easing.linear, useNativeDriver: true }));
    loop.start();
    return () => {
      loop.stop();
      driver.setValue(0);
    };
  }, [driver]);
  return (
    <View style={{ width: px, height: px }}>
      {polygons.map((polygon, i) => (
        <Animated.View key={i} data-facet={i} style={{ position: 'absolute', top: 0, left: 0, width: px, height: px, opacity: facets[i] }}>
          <Svg width={px} height={px} viewBox="0 0 100 100">{facet(polygon, i)}</Svg>
        </Animated.View>
      ))}
    </View>
  );
}

export function Busy({ label, size = 40, active = true, visible, fill = false, style }) {
  const { colors, fonts, fontSizes, mode } = useTheme();
  const delayed = useBusyVisible(visible === undefined && active);
  const shown = visible ?? delayed;
  const reduceMotion = useReduceMotion();
  const px = Math.max(size, BUSY_MIN_MARK_PX);
  const ink = BRAND_INK[mode === 'dark' ? 'dark' : 'light'];
  const polygons = useMemo(() => foldPolygons(ALPACA_FOLD, ink, px) ?? [], [ink, px]);

  if (!shown) return fill ? <View style={[{ flex: 1 }, style]} /> : null;

  const inline = px <= INLINE_MAX;
  const mark = reduceMotion
    ? <Svg width={px} height={px} viewBox="0 0 100 100" data-still="">{polygons.map(facet)}</Svg>
    : <Wave polygons={polygons} px={px} />;

  return (
    <View
      accessible
      accessibilityRole="progressbar"
      accessibilityLabel={label || BUSY_LABEL}
      style={[
        inline
          ? { flexDirection: 'row', alignItems: 'center', gap: space.s3 }
          : { alignItems: 'center', justifyContent: 'center', gap: space.s5, padding: space.s8 },
        fill ? { flex: 1, alignItems: 'center', justifyContent: 'center' } : null,
        style,
      ]}
    >
      {mark}
      {label ? (
        <Text style={{ flexShrink: 1, textAlign: inline ? 'left' : 'center', fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink2 }}>
          {label}
        </Text>
      ) : null}
    </View>
  );
}
