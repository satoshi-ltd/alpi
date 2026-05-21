import { View } from 'react-native';
import { space } from '../../theme/tokens';

import { SkeletonBar } from '../../components/SkeletonBar';
import { useTheme } from '../../theme/ThemeContext';

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
  const { colors } = useTheme();
  return (
    <View>
      {Array.from({ length: rows }).map((_, i) => (
        <View key={i}>
          {i > 0 ? (
            <View style={{ height: 0.5, backgroundColor: colors.line, marginLeft: space.s7 }} />
          ) : null}
          <SessionRow />
        </View>
      ))}
    </View>
  );
}
