import { View } from 'react-native';

import { SkeletonBar } from './SkeletonBar';
import { space } from '../theme/tokens';

const LINES = ['92%', '84%', '88%', '56%'];

export function ReaderSkeleton({ label, style }) {
  return (
    <View
      accessible
      accessibilityRole="progressbar"
      accessibilityLabel={label}
      data-skeleton="reader"
      style={[{ paddingHorizontal: space.s8, paddingVertical: space.s8, gap: space.s4 }, style]}
    >
      {LINES.map((width, i) => <SkeletonBar key={i} width={width} height={12} delay={i * 80} />)}
    </View>
  );
}
