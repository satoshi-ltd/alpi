import { useCallback } from 'react';
import { Pressable, Text, View } from 'react-native';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import Animated, {
  runOnJS,
  useAnimatedStyle,
  useSharedValue,
  withSpring,
  withTiming,
} from 'react-native-reanimated';
import { space , fontSizes} from '../theme/tokens';

import { useTheme } from '../theme/ThemeContext';

const ACTION_W = 78;
const TRIGGER_DIST = 60;

export function Swipeable({ leftActions = [], rightActions = [], children, rowHeight = 64 }) {
  const { colors, fonts, fontSizes } = useTheme();
  const tx = useSharedValue(0);

  const leftWidth = leftActions.length * ACTION_W;
  const rightWidth = rightActions.length * ACTION_W;

  const close = useCallback(() => {
    tx.value = withTiming(0, { duration: 180 });
  }, [tx]);

  const fire = useCallback((cb) => {
    cb?.();
    close();
  }, [close]);

  const pan = Gesture.Pan()
    .activeOffsetX([-12, 12])
    .failOffsetY([-10, 10])
    .onUpdate((e) => {
      let v = e.translationX;
      if (v > leftWidth) v = leftWidth + (v - leftWidth) * 0.3;
      if (v < -rightWidth) v = -rightWidth + (v + rightWidth) * 0.3;
      tx.value = v;
    })
    .onEnd((e) => {
      const v = e.translationX;
      if (v > TRIGGER_DIST && leftActions.length) {
        tx.value = withSpring(leftWidth, { damping: 18 });
      } else if (v < -TRIGGER_DIST && rightActions.length) {
        tx.value = withSpring(-rightWidth, { damping: 18 });
      } else {
        tx.value = withSpring(0, { damping: 18 });
      }
    });

  const animatedStyle = useAnimatedStyle(() => ({
    transform: [{ translateX: tx.value }],
  }));

  const leftStyle = useAnimatedStyle(() => ({
    opacity: tx.value > 0 ? 1 : 0,
    width: Math.max(0, tx.value),
  }));

  const rightStyle = useAnimatedStyle(() => ({
    opacity: tx.value < 0 ? 1 : 0,
    width: Math.max(0, -tx.value),
  }));

  const renderActions = (list, side) => (
    <View
      style={{
        flexDirection: 'row',
        height: rowHeight,
        position: 'absolute',
        top: 0,
        ...(side === 'left' ? { left: 0 } : { right: 0 }),
        justifyContent: side === 'left' ? 'flex-start' : 'flex-end',
      }}
    >
      {list.map((a, i) => (
        <Pressable
          key={a.id ?? i}
          onPress={() => runOnJS(fire)(a.onPress)}
          style={{
            width: ACTION_W,
            height: '100%',
            backgroundColor: a.tone === 'danger' ? colors.danger : a.tone === 'warning' ? colors.warning : colors.ink2,
            alignItems: 'center',
            justifyContent: 'center',
            gap: space.s1,
          }}
        >
          {a.icon}
          <Text style={{ color: colors.bgPane, fontFamily: fonts.sans.medium, fontSize: fontSizes.xs }}>
            {a.label}
          </Text>
        </Pressable>
      ))}
    </View>
  );

  return (
    <View style={{ position: 'relative', overflow: 'hidden', backgroundColor: colors.bg }}>
      {leftActions.length ? (
        <Animated.View style={[{ position: 'absolute', left: 0, top: 0, bottom: 0, overflow: 'hidden' }, leftStyle]}>
          {renderActions(leftActions, 'left')}
        </Animated.View>
      ) : null}
      {rightActions.length ? (
        <Animated.View style={[{ position: 'absolute', right: 0, top: 0, bottom: 0, overflow: 'hidden' }, rightStyle]}>
          {renderActions(rightActions, 'right')}
        </Animated.View>
      ) : null}
      <GestureDetector gesture={pan}>
        <Animated.View style={[{ backgroundColor: colors.bg }, animatedStyle]}>{children}</Animated.View>
      </GestureDetector>
    </View>
  );
}
