import { useMemo } from 'react';
import { View } from 'react-native';

import { space } from '../theme/tokens';
import { SkeletonBar } from './SkeletonBar';

export function MessageSkeleton({ style }) {
  const widths = useMemo(() => {
    const lines = 2 + Math.round(Math.random());
    const pick = (min, max) => `${Math.round(min + Math.random() * (max - min))}%`;
    const ranges = [[80, 100], [55, 85], [30, 60]];
    return Array.from({ length: lines }, (_, i) => pick(...ranges[i]));
  }, []);
  return (
    <View style={[{ gap: space.s2 }, style]}>
      {widths.map((w, i) => (
        <SkeletonBar key={i} width={w} height={12} />
      ))}
    </View>
  );
}
