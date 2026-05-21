import { View } from 'react-native';
import { radii, space } from '../../theme/tokens';

import { SkeletonBar } from '../../components/SkeletonBar';
import { useTheme } from '../../theme/ThemeContext';

export function ChatSkeleton({ kind = 'profile', accent }) {
  const { colors } = useTheme();
  if (kind === 'workgroup') {
    return (
      <View style={{ flex: 1, padding: space.s7, gap: space.s8 }}>
        <View style={{ alignItems: 'flex-start', gap: space.s2 }}>
          <SkeletonBar width="32%" height={10} />
          <SkeletonBar width="78%" height={14} />
        </View>
        <View style={{ alignItems: 'flex-start', gap: space.s2 }}>
          <SkeletonBar width="40%" height={10} />
          <SkeletonBar width="62%" height={14} />
          <SkeletonBar width="55%" height={14} />
        </View>
        <View style={{ alignItems: 'flex-start', gap: space.s2 }}>
          <SkeletonBar width="28%" height={10} />
          <SkeletonBar width="48%" height={14} />
        </View>
      </View>
    );
  }
  return (
    <View style={{ flex: 1, padding: space.s7, gap: space.s8 }}>
      <View style={{ alignItems: 'flex-end' }}>
        <View
          style={{
            width: '60%',
            backgroundColor: accent ? `${accent}22` : colors.bgInput,
            borderRadius: radii['2xl'],
            padding: space.s5,
            gap: space.s2,
          }}
        >
          <SkeletonBar width="95%" height={12} />
          <SkeletonBar width="62%" height={12} />
        </View>
      </View>
      <View style={{ alignItems: 'flex-start', gap: space.s3 }}>
        <SkeletonBar width="78%" height={14} />
        <SkeletonBar width="92%" height={14} />
        <SkeletonBar width="55%" height={14} />
      </View>
    </View>
  );
}
