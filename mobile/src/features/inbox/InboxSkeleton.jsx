import { View } from 'react-native';
import { radii, space } from '../../theme/tokens';

import { SkeletonBar } from '../../components/SkeletonBar';
import { useTheme } from '../../theme/ThemeContext';

function Row() {
  const { colors } = useTheme();
  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        gap: space.s5,
        paddingHorizontal: space.s7,
        paddingVertical: space.s5,
        minHeight: 64,
      }}
    >
      <View
        style={{
          width: 40,
          height: 40,
          borderRadius: radii.pill,
          backgroundColor: colors.hover,
        }}
      />
      <View style={{ flex: 1, gap: space.s2 }}>
        <SkeletonBar width="45%" height={13} />
        <SkeletonBar width="78%" height={11} />
      </View>
    </View>
  );
}

export function InboxSkeleton({ rows = 6 }) {
  const { colors } = useTheme();
  return (
    <View style={{ flex: 1 }}>
      {Array.from({ length: rows }).map((_, i) => (
        <View key={i}>
          {i > 0 ? (
            <View style={{ height: 0.5, backgroundColor: colors.line, marginLeft: 64 }} />
          ) : null}
          <Row />
        </View>
      ))}
    </View>
  );
}
