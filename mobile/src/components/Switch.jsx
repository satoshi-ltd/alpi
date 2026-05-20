import { useEffect, useRef } from 'react';
import { Animated, Easing, Pressable, View } from 'react-native';
import { radii } from '../theme/tokens';

import { useTheme } from '../theme/ThemeContext';

const EASE = Easing.bezier(0.2, 0.7, 0.2, 1);

export function Switch({ checked = false, disabled = false, onChange, accent }) {
  const { colors } = useTheme();
  const tint = accent ?? colors.ink;
  const progress = useRef(new Animated.Value(checked ? 1 : 0)).current;

  useEffect(() => {
    Animated.timing(progress, {
      toValue: checked ? 1 : 0,
      duration: 180,
      easing: EASE,
      useNativeDriver: false,
    }).start();
  }, [checked, progress]);

  const thumbTranslate = progress.interpolate({ inputRange: [0, 1], outputRange: [0, 14] });
  const fillOpacity = progress.interpolate({ inputRange: [0, 1], outputRange: [0, 0.12] });
  const borderColor = progress.interpolate({
    inputRange: [0, 1],
    outputRange: [colors.line2, tint],
  });
  const thumbBg = progress.interpolate({
    inputRange: [0, 1],
    outputRange: [colors.ink, tint],
  });

  return (
    <Pressable
      onPress={!disabled && onChange ? () => onChange(!checked) : undefined}
      hitSlop={6}
      style={{
        width: 40,
        height: 26,
        opacity: disabled ? 0.5 : 1,
      }}
    >
      <Animated.View
        style={{
          width: 40,
          height: 26,
          borderRadius: radii.sm,
          borderWidth: 1,
          borderColor,
          backgroundColor: colors.bg,
          overflow: 'hidden',
          alignItems: 'flex-start',
          justifyContent: 'center',
          paddingHorizontal: 2,
        }}
      >
        <Animated.View
          pointerEvents="none"
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            top: 0,
            bottom: 0,
            backgroundColor: tint,
            opacity: fillOpacity,
          }}
        />
        <Animated.View
          style={{
            transform: [{ translateX: thumbTranslate }],
          }}
        >
          <Animated.View
            style={{
              width: 16,
              height: 16,
              borderRadius: radii.sm,
              backgroundColor: thumbBg,
            }}
          />
        </Animated.View>
      </Animated.View>
    </Pressable>
  );
}
