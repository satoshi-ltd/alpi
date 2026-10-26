import { useEffect, useState } from 'react';
import { Keyboard, Modal, Pressable, ScrollView, Text, TextInput, View } from 'react-native';
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withTiming,
} from 'react-native-reanimated';
import { motion, radii, space, lineHeights, tracking, typography, veil } from '../theme/tokens';
import { EASE_ENTER, EASE_EXIT } from '../lib/motionEasing';

import { selection, warning } from '../lib/haptics';
import { useTheme } from '../theme/ThemeContext';
import { Button } from './Button';
import { useExitSnapshot } from './useExitSnapshot';
import { useWell } from './well';
const EASE_IN = EASE_ENTER;
const EASE_OUT = EASE_EXIT;
const DURATION_IN = motion.enter;
const DURATION_OUT = motion.exit;
const UNMOUNT_BUFFER = 40;
export function Code({ children }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <Text
      style={{
        fontFamily: fonts.monoMedium,
        fontSize: fontSizes.sm,
        color: colors.ink,
        backgroundColor: colors.field,
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

export function ConfirmDialog({
  open,
  onClose,
  title,
  body,
  expected,
  confirmLabel = 'Delete',
  onConfirm,
  tone = 'danger',
  typed = true,
  cancelLabel = 'Cancel',
  alternateLabel = null,
  onAlternate,
}) {
  const { colors, fonts, fontSizes, shadow } = useTheme();
  const [well, focus] = useWell(colors);
  const [value, setValue] = useState('');
  const [kbHeight, setKbHeight] = useState(0);
  const danger = tone === 'danger';
  const typedField = typed && expected != null;
  const ready = typedField ? value.trim() === String(expected ?? '').trim() : true;
  const confirm = () => {
    if (!ready) return;
    setValue('');
    if (danger) warning();
    else selection();
    onConfirm?.();
  };

  useEffect(() => {
    const showSub = Keyboard.addListener('keyboardDidShow', (e) => setKbHeight(e.endCoordinates.height));
    const hideSub = Keyboard.addListener('keyboardDidHide', () => setKbHeight(0));
    return () => { showSub.remove(); hideSub.remove(); };
  }, []);
  const view = useExitSnapshot(open, { title, body, expected, confirmLabel, cancelLabel, alternateLabel });
  const [mounted, setMounted] = useState(open);
  const opacity = useSharedValue(0);
  const scale = useSharedValue(0.96);

  useEffect(() => {
    if (!open) setValue('');
    if (open) {
      setMounted(true);
      opacity.value = withTiming(1, { duration: DURATION_IN, easing: EASE_IN });
      scale.value = withTiming(1, { duration: DURATION_IN, easing: EASE_IN });
      return undefined;
    }
    opacity.value = withTiming(0, { duration: DURATION_OUT, easing: EASE_OUT });
    scale.value = withTiming(0.96, { duration: DURATION_OUT, easing: EASE_OUT });
    const t = setTimeout(() => setMounted(false), DURATION_OUT + UNMOUNT_BUFFER);
    return () => clearTimeout(t);
  }, [open, opacity, scale]);

  const backdropStyle = useAnimatedStyle(() => ({ opacity: opacity.value }));
  const dialogStyle = useAnimatedStyle(() => ({
    opacity: opacity.value,
    transform: [{ scale: scale.value }],
  }));

  return (
    <Modal
      visible={mounted}
      transparent
      animationType="none"
      statusBarTranslucent
      supportedOrientations={['portrait', 'landscape-left', 'landscape-right']}
      onRequestClose={onClose}
    >
      <Animated.View style={[{ flex: 1, backgroundColor: veil(colors), paddingBottom: kbHeight }, backdropStyle]}>
        <Pressable
          onPress={onClose}
          accessible={false}
          style={{
            flex: 1,
            alignItems: 'center',
            justifyContent: 'center',
            padding: space.s9,
          }}
        >
          <Animated.View
            pointerEvents={open ? 'auto' : 'none'}
            style={[
              {
                width: '100%',
                maxWidth: 420,
                maxHeight: '100%',
                backgroundColor: colors.bgPane,
                borderRadius: radii.xs,
                ...shadow.dialog,
              },
              dialogStyle,
            ]}
          >
            <ScrollView keyboardShouldPersistTaps="handled" bounces={false}>
              <Pressable
                onPress={() => {}}
                accessible={false}
                style={{
                  padding: space.s9,
                  gap: space.s7,
                }}
              >
            <Text
              style={{
                fontFamily: fonts.sans.semibold,
                fontSize: fontSizes[typography.dialogTitle.size],
                color: danger ? colors.dangerText : colors.ink,
                letterSpacing: fontSizes[typography.dialogTitle.size] * tracking.snug,
              }}
            >
              {view.title}
            </Text>
            <Text
              style={{
                fontFamily: fonts.sans.regular,
                fontSize: fontSizes.md,
                color: colors.ink2,
                lineHeight: fontSizes[typography.body.size] * lineHeights[typography.body.leading],
              }}
            >
              {view.body}
            </Text>
            {typedField ? <View style={{ gap: space.s3 }}>
              <Text
                style={{
                  fontFamily: fonts.mono,
                  fontSize: fontSizes.xs,
                  color: colors.ink3,
                  letterSpacing: 0.6,
                }}
              >
                TYPE <Code>{view.expected}</Code> TO CONFIRM
              </Text>
              <TextInput
                value={value}
                onChangeText={setValue}
                placeholder={String(view.expected ?? '')}
                placeholderTextColor={colors.ink3}
                autoFocus
                accessibilityLabel={`Type ${view.expected} to confirm`}
                returnKeyType="done"
                onSubmitEditing={confirm}
                autoCapitalize="none"
                autoCorrect={false}
                spellCheck={false}
                {...focus}
                style={{
                  ...well,
                  paddingHorizontal: space.s5,
                  minHeight: 44,
                  fontFamily: fonts.mono,
                  fontSize: fontSizes.md,
                  color: colors.ink,
                }}
              />
            </View> : null}
            <View style={{ gap: space.s3, marginTop: space.s1 }}>
              <Button
                title={view.confirmLabel}
                variant={danger ? 'danger' : 'primary'}
                onPress={confirm}
                disabled={!ready}
                fullWidth
              />
              {view.alternateLabel ? <Button title={view.alternateLabel} variant="secondary" onPress={onAlternate} fullWidth /> : null}
              <Button title={cancelLabel} variant="ghost" onPress={onClose} fullWidth />
            </View>
              </Pressable>
            </ScrollView>
          </Animated.View>
        </Pressable>
      </Animated.View>
    </Modal>
  );
}
