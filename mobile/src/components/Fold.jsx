import { useEffect, useMemo } from 'react';
import { Animated, View } from 'react-native';
import Svg, { Polygon } from 'react-native-svg';

import { ALPACA_FOLD, alpacaDrawnSize, BRAND_INK, FOLD_SIZES, foldPolygons, normaliseFold } from '../../../common/folds.mjs';
import { alpacaTones, isTonalSize } from '../../../common/alpacaTones.mjs';
import { pulseSteps } from '../lib/pulse';
import { useReduceMotion } from '../lib/reduceMotion';
import { motion } from '../theme/tokens';
import { useTheme } from '../theme/ThemeContext';


export function Fold({ fold, color, size, pulse = false, outlined = false, unfolded = false }) {
  const { colors, mode } = useTheme();
  const px = typeof size === 'number' ? size : size === 'md' ? FOLD_SIZES.header : FOLD_SIZES.row;
  const id = normaliseFold(fold);
  const tint = id === ALPACA_FOLD ? BRAND_INK[mode === 'dark' ? 'dark' : 'light'] : typeof color === 'string' && color.startsWith('#') ? color : colors.ink3;
  const alpaca = id === ALPACA_FOLD;
  const drawn = alpaca && typeof size !== 'number' ? alpacaDrawnSize(px) : px;
  const tonal = alpaca && !unfolded && !outlined && isTonalSize(drawn);
  const toneMode = mode === 'dark' ? 'dark' : 'light';
  const polygons = useMemo(() => {
    const flat = foldPolygons(id, tint, px);
    if (!tonal) return flat;
    const tones = alpacaTones(toneMode);
    return flat.map((polygon) => ({ ...polygon, fill: tones[polygon.tone] }));
  }, [id, tint, px, tonal, toneMode]);
  const reduceMotion = useReduceMotion();
  const rippling = pulse && !reduceMotion && !unfolded;
  const cellOpacity = useMemo(() => (polygons ?? []).map(() => new Animated.Value(1)), [polygons]);
  useEffect(() => {
    if (!rippling) return;
    const loops = cellOpacity.map((value, i) =>
      Animated.sequence([
        Animated.delay((i / cellOpacity.length) * motion.pulse),
        Animated.loop(
          Animated.sequence(pulseSteps(value)),
        ),
      ]),
    );
    loops.forEach((loop) => loop.start());
    return () => {
      loops.forEach((loop) => loop.stop());
      cellOpacity.forEach((value) => value.setValue(1));
    };
  }, [rippling, cellOpacity]);

  const cell = ({ points, fill }, i) => (
    <Polygon
      key={i}
      points={points.map((p) => p.map((v) => v.toFixed(2)).join(',')).join(' ')}
      fill={unfolded ? 'none' : fill}
      fillOpacity={unfolded ? undefined : outlined ? 0.22 : 1}
      stroke={unfolded ? colors.ink3 : outlined ? fill : undefined}
      strokeWidth={unfolded ? 1 : outlined ? 3 : undefined}
      strokeDasharray={unfolded ? '2 1.5' : undefined}
      vectorEffect={unfolded ? 'non-scaling-stroke' : undefined}
      strokeLinejoin="round"
    />
  );
  if (rippling) {
    const offset = (px - drawn) / 2;
    return (
      <View style={{ width: px, height: px, flexShrink: 0, overflow: 'visible' }}>
        {polygons.map((polygon, i) => (
          <Animated.View key={i} data-cell={i} style={{ position: 'absolute', top: offset, left: offset, width: drawn, height: drawn, opacity: cellOpacity[i] }}>
            <Svg width={drawn} height={drawn} viewBox="0 0 100 100" data-fold={id}>
              {cell(polygon, i)}
            </Svg>
          </Animated.View>
        ))}
      </View>
    );
  }
  return (
    <View style={{ width: px, height: px, flexShrink: 0, alignItems: 'center', justifyContent: 'center', overflow: 'visible' }}>
      <Svg width={drawn} height={drawn} viewBox="0 0 100 100" data-fold={id} data-unfolded={unfolded ? '' : undefined}>
        {polygons.map(cell)}
      </Svg>
    </View>
  );
}
