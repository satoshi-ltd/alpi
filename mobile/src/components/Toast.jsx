import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { AccessibilityInfo, Animated, Easing, Keyboard, Modal, Pressable, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { lineHeights, mobile, motion, radii, space } from '../theme/tokens';

import { pulseSteps } from '../lib/pulse';
import { useReduceMotion } from '../lib/reduceMotion';
import { dotShape } from './dotShape';
import { Icon } from './Icon';
import { useTheme } from '../theme/ThemeContext';
import { plainError } from '../../../common/plainError.mjs';

const enterEasing = () => Easing.bezier(...motion.easeEnter);
const exitEasing = () => Easing.bezier(...motion.easeExit);

export const TOAST_MS = { info: 2800, undo: 5000, error: 6000 };
export const TOAST_CLEARANCE = 72;
const OFFSCREEN = 140;
export const BUTTON_LINE = mobile.tap - 2 * space.s4;
export const firstLineHeight = (fontSize, hasButton) => (hasButton ? BUTTON_LINE : Math.round(fontSize * lineHeights.cozy));

const ToastContext = createContext(null);

export const isErrorToast = (toast) => (toast?.kind ?? inferKind(toast?.title)) === 'danger';

function dotColorFor(kind, colors) {
  if (kind === 'success') return colors.success;
  if (kind === 'warning') return colors.warning;
  if (kind === 'danger') return colors.danger;
  return colors.ink3;
}

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
  const slide = useRef(new Animated.Value(OFFSCREEN)).current;
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
      Animated.timing(slide, { toValue: OFFSCREEN, duration: motion.exit, easing: exitEasing(), useNativeDriver: true }),
      Animated.timing(fade, { toValue: 0, duration: motion.exit, easing: exitEasing(), useNativeDriver: true }),
    ]).start(({ finished }) => { if (finished) setToast(null); });
  }, [slide, fade]);

  const show = useCallback(
    (next) => {
      if (timer.current) clearTimeout(timer.current);
      const shown = isErrorToast(next) && typeof next.message === 'string' ? { ...next, message: plainError(next.message) } : next;
      setToast(shown);
      const spoken = [shown?.title, shown?.message].filter((part) => typeof part === 'string' && part).join('. ');
      if (spoken) AccessibilityInfo.announceForAccessibility?.(spoken);
      if (reduceMotionRef.current) {
        slide.setValue(0);
        fade.setValue(1);
      } else {
        Animated.parallel([
          Animated.timing(slide, { toValue: 0, duration: motion.enter, easing: enterEasing(), useNativeDriver: true }),
          Animated.timing(fade, { toValue: 1, duration: motion.enter, easing: enterEasing(), useNativeDriver: true }),
        ]).start();
      }
      const undoable = !!(next?.action && next?.onAction);
      const error = isErrorToast(next);
      const sticky = error && typeof next.onRetry === 'function';
      const lasts = undoable ? (next.duration ?? TOAST_MS.undo) : error ? TOAST_MS.error : TOAST_MS.info;
      timer.current = sticky ? null : setTimeout(hide, lasts);
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
    const loop = Animated.loop(Animated.sequence(pulseSteps(pulse)));
    loop.start();
    return () => loop.stop();
  }, [kind, pulse, reduceMotion]);
  const error = kind === 'danger';
  const actionable = !!(toast.action && toast.onAction);
  const retryable = error && typeof toast.onRetry === 'function';
  const [kbHeight, setKbHeight] = useState(0);
  useEffect(() => {
    const showSub = Keyboard.addListener('keyboardDidShow', (e) => setKbHeight(e.endCoordinates.height));
    const hideSub = Keyboard.addListener('keyboardDidHide', () => setKbHeight(0));
    return () => { showSub.remove(); hideSub.remove(); };
  }, []);
  const onAction = () => {
    onDismiss();
    toast.onAction();
  };
  const onRetry = () => {
    onDismiss();
    toast.onRetry();
  };
  const firstLine = firstLineHeight(fontSizes.md, actionable || error);
  const textButton = (label, onPress) => (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={({ pressed }) => ({
        minHeight: mobile.tap,
        minWidth: mobile.tap,
        marginVertical: -space.s4,
        paddingHorizontal: space.s4,
        alignItems: 'center',
        justifyContent: 'center',
        borderRadius: radii.xs,
        backgroundColor: pressed ? colors.selected : 'transparent',
      })}
    >
      <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.md, color: colors.ink }}>{label}</Text>
    </Pressable>
  );

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
          edges={['bottom']}
          style={{ position: 'absolute', left: 0, right: 0, bottom: kbHeight, alignItems: 'center', paddingHorizontal: space.s7 }}
        >
          <Animated.View
            pointerEvents={actionable || error ? 'box-none' : 'none'}
            accessibilityRole={error ? 'alert' : undefined}
            accessibilityLiveRegion={error ? 'assertive' : 'polite'}
            style={{
              marginBottom: kbHeight > 0 ? space.s7 : TOAST_CLEARANCE,
              width: '100%',
              maxWidth: 560,
              padding: space.s6,
              backgroundColor: colors.bgPane,
              borderRadius: radii.xs,
              ...shadow.toast,
              transform: [{ translateY: slide }],
              opacity: fade,
              flexDirection: 'row',
              alignItems: 'flex-start',
              gap: space.s4,
            }}
          >
            <View style={{ height: firstLine, justifyContent: 'center' }}>
              <Animated.View style={{ ...dotShape('md'), backgroundColor: dotColor, opacity: pulse }} />
            </View>
            <View style={{ flex: 1, minWidth: 0 }}>
              {toast.title ? (
                <Text numberOfLines={1} style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.md, lineHeight: firstLine, color: colors.ink }}>
                  {toast.title}
                </Text>
              ) : null}
              {toast.message ? (
                <Text
                  numberOfLines={2}
                  style={{
                    fontFamily: fonts.sans.regular,
                    fontSize: fontSizes.md,
                    lineHeight: toast.title ? Math.round(fontSizes.md * lineHeights.cozy) : firstLine,
                    color: colors.ink2,
                    marginTop: toast.title ? space.s1 : 0,
                  }}
                >
                  {toast.message}
                </Text>
              ) : null}
            </View>
            {actionable ? textButton(toast.action, onAction) : null}
            {retryable ? textButton('Retry', onRetry) : null}
            {error ? (
              <Pressable
                onPress={onDismiss}
                accessibilityRole="button"
                accessibilityLabel="Dismiss"
                style={({ pressed }) => ({
                  width: mobile.tap,
                  height: mobile.tap,
                  marginVertical: -space.s4,
                  marginRight: -space.s4,
                  alignItems: 'center',
                  justifyContent: 'center',
                  borderRadius: radii.xs,
                  backgroundColor: pressed ? colors.selected : 'transparent',
                })}
              >
                <Icon name="x" size="md" color={colors.ink2} />
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
