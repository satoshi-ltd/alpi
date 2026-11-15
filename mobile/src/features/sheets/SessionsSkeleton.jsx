import { View } from 'react-native';
import { space } from '../../theme/tokens';

import { SkeletonBar } from '../../components/SkeletonBar';

function SessionRow() {
  return (
    <View
      style={{
        paddingHorizontal: space.s7,
        paddingVertical: space.s5,
        gap: space.s2,
      }}
    >
      <SkeletonBar width="68%" height={13} />
      <SkeletonBar width="42%" height={11} />
    </View>
  );
}

export function SessionsSkeleton({ rows = 5 }) {
  return (
    <View>
      {Array.from({ length: rows }).map((_, i) => (
        <View key={i}>
          <SessionRow />
        </View>
      ))}
    </View>
  );
}
