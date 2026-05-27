import { useEffect, useState } from 'react';
import { Keyboard, Modal, Pressable, Text, View } from 'react-native';
import { GestureDetector } from 'react-native-gesture-handler';
import Animated from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { radii, space , fontSizes} from '../theme/tokens';

import { useTheme } from '../theme/ThemeContext';
import { Button } from './Button';
import { useSheetGesture } from './useSheetGesture';

export function Sheet({
  open,
  onClose,
  title,
  subtitle,
  headerRight,
  primaryAction,
  footer,
  children,
  maxHeight = '88%',
  hideHeader = false,
}) {
  const { colors, fonts, shadow , fontSizes} = useTheme();
  const insets = useSafeAreaInsets();
  const { gesture, sheetStyle, backdropStyle, mounted } = useSheetGesture(open, onClose);
  const [kbHeight, setKbHeight] = useState(0);

  // Push the sheet above the keyboard. Use Did* (not Will*) so the layout
  // shift happens AFTER iOS commits the focus/becomeFirstResponder — Will*
  // fires mid-focus and breaks single-tap input activation.
  useEffect(() => {
    const showSub = Keyboard.addListener('keyboardDidShow', (e) => setKbHeight(e.endCoordinates.height));
    const hideSub = Keyboard.addListener('keyboardDidHide', () => setKbHeight(0));
    return () => { showSub.remove(); hideSub.remove(); };
  }, []);

  return (
    <Modal visible={mounted} transparent animationType="none" onRequestClose={onClose}>
      <Animated.View
        style={[
          { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', paddingBottom: kbHeight },
          backdropStyle,
        ]}
      >
        <Pressable style={{ flex: 1 }} onPress={onClose} />
        <Animated.View
          style={[
            {
              maxHeight,
              backgroundColor: colors.bgPane,
              borderTopLeftRadius: radii['3xl'],
              borderTopRightRadius: radii['3xl'],
              overflow: 'hidden',
              ...shadow.base,
            },
            sheetStyle,
          ]}
        >
          <GestureDetector gesture={gesture}>
            <View>
              <View style={{ alignItems: 'center', paddingTop: space.s3 }}>
                <View
                  style={{
                    width: 36,
                    height: 4,
                    borderRadius: 2,
                    backgroundColor: colors.ink4,
                    opacity: 0.6,
                  }}
                />
              </View>
              {hideHeader ? null : (
              <View
                style={{
                  flexDirection: 'row',
                  alignItems: 'baseline',
                  paddingHorizontal: space.s8,
                  paddingTop: space.s2,
                  paddingBottom: space.s6,
                  gap: space.s5,
                }}
              >
                <View style={{ flex: 1 }}>
                  <Text
                    style={{
                      fontFamily: fonts.sans.semibold,
                      fontSize: fontSizes.xl,
                      lineHeight: 22,
                      letterSpacing: -0.18,
                      color: colors.ink,
                    }}
                  >
                    {title}
                  </Text>
                  {subtitle ? (
                    <Text
                      style={{
                        fontFamily: fonts.mono,
                        fontSize: fontSizes.sm,
                        lineHeight: 15.6,
                        color: colors.ink3,
                        marginTop: space.s1,
                      }}
                    >
                      {subtitle}
                    </Text>
                  ) : null}
                </View>
                {headerRight ?? (
                  <Pressable onPress={onClose} hitSlop={10}>
                    <Text style={{ fontFamily: fonts.sans.medium, fontSize: fontSizes.md, color: colors.ink3 }}>
                      Cancel
                    </Text>
                  </Pressable>
                )}
              </View>
              )}
            </View>
          </GestureDetector>
          <View
            style={{
              flexShrink: 1,
              paddingBottom: primaryAction ? 20 + 44 + (kbHeight > 0 ? 16 : Math.max(16, insets.bottom)) + 12 : 0,
            }}
          >
            {children}
          </View>
          {primaryAction ? (
            <View
              pointerEvents="box-none"
              style={{
                position: 'absolute',
                left: 0,
                right: 0,
                bottom: 0,
                flexDirection: 'row',
                gap: space.s4,
                paddingHorizontal: space.s7,
                paddingTop: space.s8,
                paddingBottom: kbHeight > 0 ? 16 : Math.max(16, insets.bottom),
                backgroundColor: colors.bgPane,
              }}
            >
              {(Array.isArray(primaryAction) ? primaryAction : [primaryAction]).map((a, i) => (
                <View key={a.id ?? i} style={{ flex: 1 }}>
                  <Button
                    title={a.label}
                    variant={a.variant ?? 'primary'}
                    onPress={a.onPress}
                    disabled={!!a.disabled}
                    loading={!!a.loading}
                    fullWidth
                  />
                </View>
              ))}
            </View>
          ) : footer ? (
            <View
              style={{
                paddingHorizontal: space.s8,
                paddingTop: space.s5,
                paddingBottom: Math.max(8, insets.bottom),
              }}
            >
              {footer}
            </View>
          ) : (
            <View style={{ paddingBottom: insets.bottom }} />
          )}
        </Animated.View>
      </Animated.View>
    </Modal>
  );
}
