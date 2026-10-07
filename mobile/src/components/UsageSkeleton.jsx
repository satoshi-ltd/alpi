import { View } from 'react-native';

import { CHART_H } from './UsageChart';
import { SkeletonBar } from './SkeletonBar';

export function UsageSkeleton() {
  return (
    <View accessible accessibilityRole="progressbar" accessibilityLabel="Loading usage" data-skeleton="usage">
      <SkeletonBar width="100%" height={CHART_H} />
    </View>
  );
}
