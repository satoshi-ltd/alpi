import { useEffect, useRef, useState } from 'react';
import { Pressable, ScrollView, Text, useWindowDimensions, View } from 'react-native';
import Animated, { cancelAnimation, useAnimatedStyle, useSharedValue, withRepeat, withTiming } from 'react-native-reanimated';

import { Icon } from '../../components/Icon';
import { useReduceMotion } from '../../lib/reduceMotion';
import { useTheme } from '../../theme/ThemeContext';
import { lineHeights, mobile, space } from '../../theme/tokens';
import { thoughtLabel } from '../../../../common/reasoningLabel.mjs';

const SHIMMER_HALF_MS = 700;

function toLines(text) {
  return String(text || '')
    .split('\n')
    .map((s) => s.replace(/\s+$/, ''))
    .filter((s) => s.trim());
}

export function Reasoning({ text, seconds, streaming = false, answered = false, flat = false }) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (answered) setOpen(false);
  }, [answered]);
  if (!streaming && !String(text || '').trim()) return null;
  const lines = toLines(text);
  return (
    <View style={{ paddingHorizontal: flat ? space.s7 : 0 }}>
      <Pressable
        onPress={() => setOpen((v) => !v)}
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        accessibilityLabel={open ? 'Collapse reasoning' : 'Expand reasoning'}
        style={{ flexDirection: 'row', alignItems: 'center', gap: space.s3, minHeight: mobile.tap }}
      >
        <Chevron open={open} />
        {streaming ? <Thinking hint={open ? '' : lines[lines.length - 1]} /> : <Thought seconds={seconds} />}
      </Pressable>
      {open && lines.length ? <Body lines={lines} follow={streaming} /> : null}
    </View>
  );
}

function Chevron({ open }) {
  const { colors } = useTheme();
  return (
    <View style={{ transform: [{ rotate: open ? '90deg' : '0deg' }] }}>
      <Icon name="chevron-right" size="sm" color={colors.ink3} />
    </View>
  );
}

function Shimmer({ children, style }) {
  const reduceMotion = useReduceMotion();
  const opacity = useSharedValue(1);
  useEffect(() => {
    if (reduceMotion) {
      cancelAnimation(opacity);
      opacity.value = 1;
      return undefined;
    }
    opacity.value = withRepeat(withTiming(0.4, { duration: SHIMMER_HALF_MS }), -1, true);
    return () => cancelAnimation(opacity);
  }, [reduceMotion, opacity]);
  const animated = useAnimatedStyle(() => ({ opacity: opacity.value }));
  return (
    <Animated.Text style={[style, animated]} accessibilityLiveRegion="polite">
      {children}
    </Animated.Text>
  );
}

function Thinking({ hint }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <>
      <Shimmer style={{ fontFamily: fonts.sans.medium, fontSize: fontSizes.md, color: colors.ink2 }}>
        Thinking…
      </Shimmer>
      {hint ? (
        <Text numberOfLines={1} style={{ flex: 1, fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.ink3 }}>
          {hint}
        </Text>
      ) : null}
    </>
  );
}

function Thought({ seconds }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.md, color: colors.ink2 }}>
      {thoughtLabel(seconds)}
    </Text>
  );
}

function Body({ lines, follow }) {
  const { colors, fonts, fontSizes } = useTheme();
  const { height } = useWindowDimensions();
  const scrollRef = useRef(null);
  const size = fontSizes.md;
  return (
    <ScrollView
      ref={scrollRef}
      style={{ maxHeight: height * 0.45, marginLeft: space.s3, borderLeftWidth: 2, borderLeftColor: colors.line }}
      contentContainerStyle={{ paddingLeft: space.s6, paddingBottom: space.s3 }}
      nestedScrollEnabled
      onContentSizeChange={follow ? () => scrollRef.current?.scrollToEnd?.({ animated: false }) : undefined}
    >
      {lines.map((line, i) => (
        <Text
          key={i}
          selectable
          style={{
            color: colors.ink2,
            fontFamily: fonts.sans.regular,
            fontSize: size,
            lineHeight: size * lineHeights.relaxed,
            marginTop: i === 0 ? 0 : space.s2,
          }}
        >
          {line}
        </Text>
      ))}
    </ScrollView>
  );
}
