import { useEffect, useRef } from 'react';
import { Animated, View } from 'react-native';

import { useTheme } from '../theme/ThemeContext';

export function SyncBar({ syncing }) {
  const { colors } = useTheme();
  const x = useRef(new Animated.Value(-1)).current;

  useEffect(() => {
    if (!syncing) {
      x.stopAnimation();
      x.setValue(-1);
      return undefined;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(x, { toValue: 1, duration: 900, useNativeDriver: true }),
        Animated.timing(x, { toValue: -1, duration: 0, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [syncing, x]);

  return (
    <View style={{ height: 2, overflow: 'hidden', backgroundColor: colors.line }}>
      {syncing ? (
        <Animated.View
          style={{
            width: '44%',
            height: 2,
            backgroundColor: colors.accent,
            transform: [{
              translateX: x.interpolate({
                inputRange: [-1, 1],
                outputRange: [-180, 420],
              }),
            }],
          }}
        />
      ) : null}
    </View>
  );
}
