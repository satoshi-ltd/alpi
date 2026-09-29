import { View } from 'react-native';

import { SkeletonBar } from './SkeletonBar';
import { space } from '../theme/tokens';

const ROWS = [[120, 180], [90, 220], [140, 160], [70, 200], [110, 150]];

export function SettingsSkeleton({ wide = false }) {
  return (
    <View accessibilityLabel="Loading settings" style={{ paddingHorizontal: wide ? space.s9 : space.s8, paddingTop: space.s9, gap: space.s8 }}>
      <SkeletonBar width={72} height={10} />
      {ROWS.map(([label, helper], i) => (
        <View key={label} style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: space.s5 }}>
          <View style={{ gap: space.s2 }}>
            <SkeletonBar width={label} height={14} delay={i * 80} />
            <SkeletonBar width={helper} height={10} delay={i * 80 + 40} />
          </View>
          <SkeletonBar width={56} height={12} delay={i * 80} />
        </View>
      ))}
    </View>
  );
}
