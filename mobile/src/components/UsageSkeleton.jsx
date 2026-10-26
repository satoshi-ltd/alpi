import { useState } from 'react';
import { View } from 'react-native';

import { CHART_H, NARROW_TILES_W, usageMetrics } from './UsageChart';
import { SkeletonBar, STAGGER_MS } from './SkeletonBar';
import { useTheme } from '../theme/ThemeContext';
import { radii, space } from '../theme/tokens';

export const BAR_SHAPES = [0.43, 0.57, 0.17, 0.4, 1, 0.26, 0.49, 0.31, 0.14, 0.51, 0.29, 0.86, 0.54, 0.23];
const DAYS = BAR_SHAPES.length;
const BONE = 8;

function Slot({ height, children }) {
  return <View style={{ height, justifyContent: 'center' }}>{children}</View>;
}

function Tile({ label, value, big = false, metrics, index, end = false }) {
  const delay = index * STAGGER_MS;
  return (
    <View data-tile="" style={{ flex: 1, minWidth: 0, gap: space.s2, alignItems: end ? 'flex-end' : 'flex-start' }}>
      <Slot height={metrics.label}>
        <SkeletonBar width={label} height={BONE} radius={radii.tag} delay={delay} />
      </Slot>
      <Slot height={big ? metrics.today : metrics.mono}>
        <SkeletonBar width={value} height={big ? 22 : 14} radius={radii.tag} delay={delay} />
      </Slot>
    </View>
  );
}

export function UsageSkeleton() {
  const { colors, fontSizes } = useTheme();
  const metrics = usageMetrics(fontSizes);
  const [tilesW, setTilesW] = useState(0);
  const narrow = tilesW > 0 && tilesW < NARROW_TILES_W;
  return (
    <View accessible accessibilityRole="progressbar" accessibilityLabel="Loading usage" data-skeleton="usage" data-narrow={String(narrow)}>
      <View onLayout={(e) => setTilesW(e.nativeEvent.layout.width)} style={{ paddingBottom: space.s6, borderBottomWidth: 0.5, borderBottomColor: colors.line2 }}>
        {narrow ? (
          <>
            <View data-row="" style={{ flexDirection: 'row', alignItems: 'flex-end' }}>
              <Tile label={34} value={84} big metrics={metrics} index={0} />
              <Tile label={52} value={58} metrics={metrics} index={1} end />
            </View>
            <View data-row="" style={{ flexDirection: 'row', alignItems: 'flex-start', marginTop: space.s6 }}>
              <Tile label={38} value={52} metrics={metrics} index={2} />
              <Tile label={44} value={40} metrics={metrics} index={3} />
            </View>
          </>
        ) : (
          <View data-row="" style={{ flexDirection: 'row', alignItems: 'flex-start' }}>
            <Tile label={34} value={96} big metrics={metrics} index={0} />
            <Tile label={38} value={56} metrics={metrics} index={1} />
            <Tile label={44} value={44} metrics={metrics} index={2} />
            <Tile label={52} value={60} metrics={metrics} index={3} />
          </View>
        )}
      </View>
      <View style={{ marginTop: space.s8 }}>
        <View data-bars="" style={{ height: CHART_H, flexDirection: 'row', alignItems: 'flex-end', gap: space.s1 }}>
          {BAR_SHAPES.map((shape, i) => (
            <View key={i} style={{ flex: 1, alignItems: 'center', justifyContent: 'flex-end' }}>
              <SkeletonBar width="100%" height={Math.round(CHART_H * shape)} radius={3} delay={i * STAGGER_MS} style={{ maxWidth: 20 }} />
            </View>
          ))}
        </View>
        <View data-days="" style={{ flexDirection: 'row', gap: space.s1, marginTop: space.s3 }}>
          {Array.from({ length: DAYS }, (_, i) => (
            <View key={i} style={{ flex: 1, height: metrics.dayLabel, alignItems: 'center', justifyContent: 'center' }}>
              <SkeletonBar width={8} height={6} radius={radii.tag} delay={i * STAGGER_MS} />
            </View>
          ))}
        </View>
      </View>
      <View data-legend="" style={{ height: metrics.legend, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: space.s6 }}>
        <SkeletonBar width={96} height={BONE} radius={radii.tag} />
        <SkeletonBar width={150} height={BONE} radius={radii.tag} delay={STAGGER_MS} />
      </View>
    </View>
  );
}
