import { View } from 'react-native';

import { SkeletonBar, STAGGER_MS } from './SkeletonBar';
import { radii, space } from '../theme/tokens';

const ROWS = [180, 220, 160, 200, 150];

export function SettingsSkeleton({ wide = false }) {
  return (
    <View accessible accessibilityRole="progressbar" accessibilityLabel="Loading settings" style={{ paddingHorizontal: wide ? space.s9 : space.s8, paddingTop: space.s9, gap: space.s8 }}>
      {ROWS.map((helper, i) => (
        <View key={helper} style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: space.s5 }}>
          <SkeletonBar width={helper} height={10} delay={i * STAGGER_MS} />
          <SkeletonBar width={64} height={14} radius={radii.tag} delay={i * STAGGER_MS} />
        </View>
      ))}
    </View>
  );
}
