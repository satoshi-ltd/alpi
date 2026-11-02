import Animated, { useAnimatedStyle } from 'react-native-reanimated';
import { useKeyboardInset } from '../hooks/useKeyboardInset';

// Edge-to-edge makes reanimated report the full IME inset, nav bar included — the padding a screen-bottom pane needs.
export function KeyboardPane({ children, style }) {
  const inset = useKeyboardInset();
  const ride = useAnimatedStyle(() => ({ paddingBottom: inset.value }));
  return <Animated.View style={[style ?? { flex: 1 }, ride]}>{children}</Animated.View>;
}
