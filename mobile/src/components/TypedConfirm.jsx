import { useEffect, useState } from 'react';
import { Modal, Pressable, Text, TextInput, View } from 'react-native';
import Animated, {
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withTiming,
} from 'react-native-reanimated';
import { radii, space , fontSizes} from '../theme/tokens';

import { useTheme } from '../theme/ThemeContext';
import { Button } from './Button';

// Same cubic-bezier as bottom sheets — one motion vocabulary across modals.
const EASE = Easing.bezier(0.2, 0.7, 0.2, 1);
const DURATION_IN = 200;
const DURATION_OUT = 160;
const UNMOUNT_BUFFER = 40;

// Inline code chip — use inside `body` for paths/handles. Renders as a tinted mono span that flows with surrounding text.
export function Code({ children }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <Text
      style={{
        fontFamily: fonts.monoMedium,
        fontSize: fontSizes.sm,
        color: colors.ink,
        backgroundColor: colors.bgInput,
        borderRadius: radii.xs,
        paddingHorizontal: space.s2,
      }}
    >
      {children}
    </Text>
  );
}

export function Bold({ children }) {
  const { colors, fonts } = useTheme();
  return (
    <Text style={{ fontFamily: fonts.sans.semibold, color: colors.ink }}>{children}</Text>
  );
}

export function TypedConfirm({
  open,
  onClose,
  title,
  body,
  expected,
  confirmLabel = 'Delete',
  onConfirm,
}) {
  const { colors, fonts, fontSizes } = useTheme();
  const [value, setValue] = useState('');
  const ready = value.trim() === String(expected ?? '').trim();

  // mounted lags `open` by DURATION_OUT so the exit animation can play before <Modal> unmounts.
  const [mounted, setMounted] = useState(open);
  const opacity = useSharedValue(0);
  const scale = useSharedValue(0.96);

  useEffect(() => {
    if (!open) setValue('');
    if (open) {
      setMounted(true);
      opacity.value = withTiming(1, { duration: DURATION_IN, easing: EASE });
      scale.value = withTiming(1, { duration: DURATION_IN, easing: EASE });
      return undefined;
    }
    opacity.value = withTiming(0, { duration: DURATION_OUT, easing: EASE });
    scale.value = withTiming(0.96, { duration: DURATION_OUT, easing: EASE });
    const t = setTimeout(() => setMounted(false), DURATION_OUT + UNMOUNT_BUFFER);
    return () => clearTimeout(t);
  }, [open, opacity, scale]);

  const backdropStyle = useAnimatedStyle(() => ({ opacity: opacity.value }));
  // Scale is bound to the dialog itself so the backdrop fades independently — matches how iOS native alerts feel (backdrop dims linearly, alert pops in).
  const dialogStyle = useAnimatedStyle(() => ({
    opacity: opacity.value,
    transform: [{ scale: scale.value }],
  }));

  return (
    <Modal visible={mounted} transparent animationType="none" statusBarTranslucent onRequestClose={onClose}>
      <Animated.View style={[{ flex: 1, backgroundColor: 'rgba(0,0,0,0.45)' }, backdropStyle]}>
        <Pressable
          onPress={onClose}
          style={{
            flex: 1,
            alignItems: 'center',
            justifyContent: 'center',
            padding: space.s9,
          }}
        >
          <Animated.View
            style={[
              {
                width: '100%',
                maxWidth: 420,
                backgroundColor: colors.bgPane,
                borderRadius: radii['3xl'],
                shadowColor: '#000',
                shadowOffset: { width: 0, height: 20 },
                shadowOpacity: 0.3,
                shadowRadius: 60,
                elevation: 24,
              },
              dialogStyle,
            ]}
          >
            <Pressable
              onPress={() => {}}
              style={{
                padding: space.s9,
                gap: space.s7,
              }}
            >
          <Text
            style={{
              fontFamily: fonts.sans.semibold,
              fontSize: fontSizes.xl,
              color: colors.danger,
              letterSpacing: -0.01 * fontSizes.xl,
            }}
          >
            {title}
          </Text>
          <Text
            style={{
              fontFamily: fonts.sans.regular,
              fontSize: fontSizes.md,
              color: colors.ink2,
              lineHeight: fontSizes.md * 1.55,
            }}
          >
            {body}
          </Text>
          <View style={{ gap: space.s3 }}>
            <Text
              style={{
                fontFamily: fonts.mono,
                fontSize: fontSizes.xs,
                color: colors.ink3,
                letterSpacing: 0.6,
              }}
            >
              TYPE <Code>{expected}</Code> TO CONFIRM
            </Text>
            <TextInput
              value={value}
              onChangeText={setValue}
              placeholder={String(expected ?? '')}
              placeholderTextColor={colors.ink4}
              autoCapitalize="none"
              autoCorrect={false}
              spellCheck={false}
              style={{
                backgroundColor: colors.bgInput,
                borderRadius: radii.lg,
                borderWidth: 0.5,
                borderColor: colors.line2,
                paddingHorizontal: space.s5,
                height: 44,
                fontFamily: fonts.mono,
                fontSize: fontSizes.md,
                color: colors.ink,
              }}
            />
          </View>
          <View style={{ gap: space.s3, marginTop: space.s1 }}>
            <Button
              title={confirmLabel}
              variant="danger"
              onPress={() => {
                setValue('');
                onConfirm?.();
              }}
              disabled={!ready}
              fullWidth
            />
            <Button title="Cancel" variant="ghost" onPress={onClose} fullWidth />
          </View>
            </Pressable>
          </Animated.View>
        </Pressable>
      </Animated.View>
    </Modal>
  );
}
