import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { AccessibilityInfo, Animated, Easing, Modal, Pressable, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { mobile, radii, space } from '../theme/tokens';

import { useReduceMotion } from '../lib/reduceMotion';
import { useTheme } from '../theme/ThemeContext';
import { plainError } from '../../../common/plainError.mjs';

const ToastContext = createContext(null);

function dotColorFor(kind, colors) {
  if (kind === 'success') return colors.success;
  if (kind === 'warning') return colors.warning;
  if (kind === 'danger') return colors.danger;
  return colors.ink3;
}

// Title-based fallback so legacy toast({title:'…'}) sites still pick the right dot without rewriting.
const SUCCESS_RE = /\b(saved|removed|deleted|created|added|paired|kicked|revoked|enabled|disabled|signed out|copied|sent|joined|left)\b/;
const DANGER_RE = /\b(failed|error|invalid|denied)\b/;
function inferKind(title) {
  if (typeof title !== 'string' || !title) return 'info';
  const t = title.toLowerCase();
  if (DANGER_RE.test(t)) return 'danger';
  if (SUCCESS_RE.test(t)) return 'success';
  return 'info';
}

export function ToastProvider({ children }) {
  const [toast, setToast] = useState(null);
  const slide = useRef(new Animated.Value(-100)).current;
  const fade = useRef(new Animated.Value(0)).current;
  const timer = useRef(null);
  const reduceMotion = useReduceMotion();
  const reduceMotionRef = useRef(reduceMotion);
  reduceMotionRef.current = reduceMotion;

  const hide = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
    if (reduceMotionRef.current) {
      setToast(null);
      return;
    }
    Animated.parallel([
      Animated.timing(slide, { toValue: -100, duration: 200, useNativeDriver: true }),
      Animated.timing(fade, { toValue: 0, duration: 200, useNativeDriver: true }),
    ]).start(({ finished }) => { if (finished) setToast(null); });
  }, [slide, fade]);

  const show = useCallback(
    (next) => {
      if (timer.current) clearTimeout(timer.current);
      const danger = (next?.kind ?? inferKind(next?.title)) === 'danger';
      const shown = danger && typeof next.message === 'string' ? { ...next, message: plainError(next.message) } : next;
      setToast(shown);
      const spoken = [shown?.title, shown?.message].filter((part) => typeof part === 'string' && part).join('. ');
      if (spoken) AccessibilityInfo.announceForAccessibility?.(spoken);
      if (reduceMotionRef.current) {
        slide.setValue(0);
        fade.setValue(1);
      } else {
        Animated.parallel([
          Animated.timing(slide, { toValue: 0, duration: 220, useNativeDriver: true }),
          Animated.timing(fade, { toValue: 1, duration: 220, useNativeDriver: true }),
        ]).start();
      }
      timer.current = setTimeout(hide, next?.duration ?? 2800);
    },
    [slide, fade, hide],
  );

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  return (
    <ToastContext.Provider value={show}>
      {children}
      {toast ? <ToastView toast={toast} slide={slide} fade={fade} onDismiss={hide} /> : null}
    </ToastContext.Provider>
  );
}

function ToastView({ toast, slide, fade, onDismiss }) {
  const { colors, fonts, fontSizes, shadow } = useTheme();
  const kind = toast.kind ?? inferKind(toast.title);
  const dotColor = dotColorFor(kind, colors);
  const pulse = useRef(new Animated.Value(1)).current;
  const reduceMotion = useReduceMotion();
  useEffect(() => {
    if (kind === 'info' || reduceMotion) return undefined;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 0.4, duration: 700, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 1, duration: 700, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [kind, pulse, reduceMotion]);
  const actionable = !!(toast.action && toast.onAction);
  const onAction = () => {
    onDismiss();
    toast.onAction();
  };

  // <Modal> here forces a higher native layer than bottom-sheet Modals; <View pointerEvents="box-none"> is required so taps fall through.
  return (
    <Modal
      visible
      transparent
      animationType="none"
      statusBarTranslucent
      supportedOrientations={['portrait', 'landscape-left', 'landscape-right']}
      onRequestClose={onDismiss}
    >
      <View pointerEvents="box-none" style={{ flex: 1 }}>
        <SafeAreaView
          pointerEvents="box-none"
          edges={['top']}
          style={{ position: 'absolute', left: 0, right: 0, top: 0, alignItems: 'center', paddingHorizontal: space.s7 }}
        >
          <Animated.View
            pointerEvents={actionable ? 'box-none' : 'none'}
            style={{
              marginVertical: space.s7,
              width: '100%',
              maxWidth: 560,
              padding: space.s6,
              backgroundColor: colors.bgPane,
              borderRadius: radii.xs,
              ...shadow.base,
              transform: [{ translateY: slide }],
              opacity: fade,
              flexDirection: 'row',
              alignItems: 'flex-start',
              gap: space.s4,
            }}
          >
            <Animated.View
              style={{
                width: 8,
                height: 8,
                borderRadius: radii.xs,
                backgroundColor: dotColor,
                marginTop: toast.title ? 7 : 6,
                opacity: pulse,
              }}
            />
            <View style={{ flex: 1, minWidth: 0 }}>
              {toast.title ? (
                <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.md, color: colors.ink }}>
                  {toast.title}
                </Text>
              ) : null}
              {toast.message ? (
                <Text
                  style={{
                    fontFamily: fonts.sans.regular,
                    fontSize: fontSizes.md,
                    color: colors.ink2,
                    marginTop: toast.title ? 4 : 0,
                  }}
                >
                  {toast.message}
                </Text>
              ) : null}
            </View>
            {actionable ? (
              <Pressable
                onPress={onAction}
                accessibilityRole="button"
                accessibilityLabel={toast.action}
                style={({ pressed }) => ({
                  minHeight: mobile.tap,
                  minWidth: mobile.tap,
                  marginVertical: -space.s4,
                  marginRight: -space.s3,
                  paddingHorizontal: space.s4,
                  alignItems: 'center',
                  justifyContent: 'center',
                  borderRadius: radii.xs,
                  backgroundColor: pressed ? colors.selected : 'transparent',
                })}
              >
                <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.md, color: colors.ink }}>{toast.action}</Text>
              </Pressable>
            ) : null}
          </Animated.View>
        </SafeAreaView>
      </View>
    </Modal>
  );
}

export function useToast() {
  return useContext(ToastContext) ?? (() => {});
}
