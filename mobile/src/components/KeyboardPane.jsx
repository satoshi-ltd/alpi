import Animated, { useAnimatedKeyboard, useAnimatedStyle } from 'react-native-reanimated';

// Edge-to-edge makes reanimated report the full IME inset, nav bar included — the padding a screen-bottom pane needs.
export function KeyboardPane({ children, style }) {
  const keyboard = useAnimatedKeyboard();
  const ride = useAnimatedStyle(() => ({ paddingBottom: keyboard.height.value }));
  return <Animated.View style={[style ?? { flex: 1 }, ride]}>{children}</Animated.View>;
}
