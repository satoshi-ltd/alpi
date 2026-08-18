import { useEffect, useState } from 'react';
import { Keyboard, Modal, Pressable, Text, useWindowDimensions, View } from 'react-native';
import { GestureDetector } from 'react-native-gesture-handler';
import Animated from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { radii, space, lineHeights } from '../theme/tokens';

import { usePane } from '../nav/PaneContext';
import { useTheme } from '../theme/ThemeContext';
import { Button } from './Button';
import { SheetClose } from './SheetClose';
import { useExitSnapshot } from './useExitSnapshot';
import { useSheetGesture } from './useSheetGesture';

const CENTRED_DIALOG = {
  alignSelf: 'center',
  width: '100%',
  maxWidth: 560,
  borderBottomLeftRadius: radii['3xl'],
  borderBottomRightRadius: radii['3xl'],
};

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
  const { height } = useWindowDimensions();
  const { twoPane } = usePane();
  const { gesture, sheetStyle, backdropStyle, mounted } = useSheetGesture(open, onClose, height + 100);
  const [kbHeight, setKbHeight] = useState(0);
  const dialog = twoPane ? { ...CENTRED_DIALOG, marginBottom: Math.max(insets.bottom, 24) } : null;
  const view = useExitSnapshot(open, {
    title,
    subtitle,
    headerRight,
    primaryAction,
    footer,
    children,
    maxHeight,
    hideHeader,
  });

  // Did* not Will*: Will* fires mid-focus on iOS and breaks single-tap input activation.
  useEffect(() => {
    const showSub = Keyboard.addListener('keyboardDidShow', (e) => setKbHeight(e.endCoordinates.height));
    const hideSub = Keyboard.addListener('keyboardDidHide', () => setKbHeight(0));
    return () => { showSub.remove(); hideSub.remove(); };
  }, []);

  return (
    <Modal
      visible={mounted}
      transparent
      animationType="none"
      supportedOrientations={['portrait', 'landscape-left', 'landscape-right']}
      onRequestClose={onClose}
    >
      <Animated.View
        pointerEvents={open ? 'auto' : 'none'}
        style={[
          { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', paddingBottom: kbHeight },
          backdropStyle,
        ]}
      >
        <Pressable style={{ flex: 1 }} onPress={onClose} />
        <Animated.View
          style={[
            {
              maxHeight: view.maxHeight,
              backgroundColor: colors.bgPane,
              borderTopLeftRadius: radii['3xl'],
              borderTopRightRadius: radii['3xl'],
              overflow: 'hidden',
              ...shadow.base,
              ...dialog,
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
              <View
                style={{
                  flexDirection: 'row',
                  alignItems: 'flex-start',
                  paddingLeft: space.s8,
                  paddingRight: space.s5,
                  paddingTop: space.s5,
                  paddingBottom: view.hideHeader ? 0 : space.s6,
                  gap: space.s5,
                }}
              >
                <View style={{ flex: 1 }}>
                  {view.hideHeader ? null : (
                    <>
                      <Text
                        style={{
                          fontFamily: fonts.sans.semibold,
                          fontSize: fontSizes.xl,
                          lineHeight: fontSizes.xl * lineHeights.cozy,
                          letterSpacing: -0.18,
                          color: colors.ink,
                        }}
                      >
                        {view.title}
                      </Text>
                      {view.subtitle ? (
                        <Text
                          style={{
                            fontFamily: fonts.mono,
                            fontSize: fontSizes.sm,
                            lineHeight: fontSizes.sm * lineHeights.cozy,
                            color: colors.ink3,
                            marginTop: space.s1,
                          }}
                        >
                          {view.subtitle}
                        </Text>
                      ) : null}
                    </>
                  )}
                </View>
                {view.headerRight}
                <SheetClose onPress={onClose} />
              </View>
            </View>
          </GestureDetector>
          <View
            style={{
              flexShrink: 1,
              paddingBottom: view.primaryAction ? 20 + 44 + (kbHeight > 0 ? 16 : Math.max(16, insets.bottom)) + 12 : 0,
            }}
          >
            {view.children}
          </View>
          {view.primaryAction ? (
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
              {(Array.isArray(view.primaryAction) ? view.primaryAction : [view.primaryAction]).map((a, i) => (
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
          ) : view.footer ? (
            <View
              style={{
                paddingHorizontal: space.s8,
                paddingTop: space.s5,
                paddingBottom: Math.max(8, insets.bottom),
              }}
            >
              {view.footer}
            </View>
          ) : (
            <View style={{ paddingBottom: insets.bottom }} />
          )}
        </Animated.View>
      </Animated.View>
    </Modal>
  );
}
