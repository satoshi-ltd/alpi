import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { Animated, Easing, Modal, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { radii, space , fontSizes} from '../theme/tokens';

import { useTheme } from '../theme/ThemeContext';

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

  const show = useCallback(
    (next) => {
      if (timer.current) clearTimeout(timer.current);
      setToast(next);
      Animated.parallel([
        Animated.timing(slide, { toValue: 0, duration: 220, useNativeDriver: true }),
        Animated.timing(fade, { toValue: 1, duration: 220, useNativeDriver: true }),
      ]).start();
      const duration = next?.duration ?? 2800;
      timer.current = setTimeout(() => {
        Animated.parallel([
          Animated.timing(slide, { toValue: -100, duration: 200, useNativeDriver: true }),
          Animated.timing(fade, { toValue: 0, duration: 200, useNativeDriver: true }),
        ]).start(() => setToast(null));
      }, duration);
    },
    [slide, fade],
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
      {toast ? <ToastView toast={toast} slide={slide} fade={fade} /> : null}
    </ToastContext.Provider>
  );
}

function ToastView({ toast, slide, fade }) {
  const { colors, fonts, fontSizes } = useTheme();
  const kind = toast.kind ?? inferKind(toast.title);
  const dotColor = dotColorFor(kind, colors);
  const pulse = useRef(new Animated.Value(1)).current;
  useEffect(() => {
    if (kind === 'info') return undefined;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 0.4, duration: 700, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 1, duration: 700, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [kind, pulse]);

  // <Modal> here forces a higher native layer than bottom-sheet Modals; <View pointerEvents="box-none"> is required so taps fall through.
  return (
    <Modal
      visible
      transparent
      animationType="none"
      statusBarTranslucent
      onRequestClose={() => {}}
    >
      <View pointerEvents="box-none" style={{ flex: 1 }}>
        <SafeAreaView
          pointerEvents="box-none"
          edges={['top']}
          style={{ position: 'absolute', left: 0, right: 0, top: 0 }}
        >
          <Animated.View
            pointerEvents="none"
            style={{
              margin: space.s7,
              padding: space.s6,
              backgroundColor: colors.bgPane,
              borderRadius: radii.lg,
              shadowColor: '#000',
              shadowOffset: { width: 0, height: 8 },
              shadowOpacity: 0.18,
              shadowRadius: 18,
              elevation: 12,
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
          </Animated.View>
        </SafeAreaView>
      </View>
    </Modal>
  );
}

export function useToast() {
  return useContext(ToastContext) ?? (() => {});
}
