import { View } from 'react-native';

import { SkeletonBar } from './SkeletonBar';
import { useTheme } from '../theme/ThemeContext';
import { lineHeights } from '../theme/tokens';

export function SubtitleSkeleton({ width = 96 }) {
  const { fontSizes } = useTheme();
  const line = fontSizes.xs * lineHeights.cozy;
  return (
    <View data-skeleton="subtitle" accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={{ height: line, justifyContent: 'center' }}>
      <SkeletonBar width={width} height={fontSizes.xs} />
    </View>
  );
}
