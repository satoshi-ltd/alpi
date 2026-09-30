import { View } from 'react-native';
import Animated, { useAnimatedStyle, useSharedValue } from 'react-native-reanimated';

import { usePresence } from '../lib/usePresence';
import { motionMs } from '../theme/tokens';

const UNCLAMPED = 100000;

export function Expand({ open, children, contentStyle, duration = motionMs.expand }) {
  const { mounted, progress, moving } = usePresence(open, duration);
  const height = useSharedValue(0);
  const style = useAnimatedStyle(() => (moving.value
    ? { maxHeight: height.value * progress.value, opacity: progress.value, overflow: 'hidden' }
    : { maxHeight: UNCLAMPED, opacity: 1, overflow: 'visible' }));
  if (!mounted) return null;
  return (
    <Animated.View testID="expand" style={style}>
      <View style={contentStyle} onLayout={(e) => { height.value = e.nativeEvent.layout.height; }}>
        {children}
      </View>
    </Animated.View>
  );
}
