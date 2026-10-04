import { sheetStyles } from './sheetStyles';
import { useEffect, useState } from 'react';
import { Keyboard, Modal, Pressable, Text, useWindowDimensions, View } from 'react-native';
import { GestureDetector } from 'react-native-gesture-handler';
import Animated from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { radii, space, lineHeights, typography, veil } from '../theme/tokens';

import { usePane } from '../nav/PaneContext';
import { useTheme } from '../theme/ThemeContext';
import { Button } from './Button';
import { SheetClose } from './SheetClose';
import { useExitSnapshot } from './useExitSnapshot';
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
  dismissible = true,
}) {
  const { colors, fonts, shadow , fontSizes} = useTheme();
  const insets = useSafeAreaInsets();
  const { height } = useWindowDimensions();
  const { twoPane } = usePane();
  const dismiss = dismissible ? onClose : undefined;
  const { gesture, sheetStyle, backdropStyle, mounted } = useSheetGesture(open, dismiss, height + 100);
  const [kbHeight, setKbHeight] = useState(0);
  const [barHeight, setBarHeight] = useState(0);
  const dialog = twoPane ? sheetStyles.dialog : null;
  const bottomPad = kbHeight > 0 || twoPane ? 16 : Math.max(16, insets.bottom);
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

  const header = (
    <View>
              <View style={sheetStyles.grabberWrap}>
                <View
                  style={[sheetStyles.grabber, { backgroundColor: colors.ink4 }]}
                />
              </View>
              <View
                style={[sheetStyles.header, view.hideHeader && { paddingBottom: 0 }]}
              >
                <View style={{ flex: 1 }}>
                  {view.hideHeader ? null : (
                    <>
                      <Text
                        style={{
                          fontFamily: fonts.sans.semibold,
                          fontSize: fontSizes[typography.dialogTitle.size],
                          lineHeight: fontSizes[typography.dialogTitle.size] * lineHeights[typography.dialogTitle.leading],
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
  );

  return (
    <Modal
      visible={mounted}
      transparent
      animationType="none"
      supportedOrientations={['portrait', 'landscape-left', 'landscape-right']}
      onRequestClose={dismiss ?? (() => {})}
    >
      <Animated.View
        pointerEvents={open ? 'auto' : 'none'}
        style={[
          { flex: 1, backgroundColor: veil(colors), paddingBottom: kbHeight, justifyContent: twoPane ? 'center' : 'flex-end' },
          backdropStyle,
        ]}
      >
        <Pressable style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }} onPress={dismiss} accessible={false} />
        <Animated.View
          style={[
            {
              maxHeight: view.maxHeight,
              backgroundColor: colors.bgPane,
              borderTopLeftRadius: radii.xs,
              borderTopRightRadius: radii.xs,
              overflow: 'hidden',
              ...shadow.base,
              ...dialog,
            },
            sheetStyle,
          ]}
        >
          {dismissible ? <GestureDetector gesture={gesture}>{header}</GestureDetector> : header}
          <View
            style={{
              flexShrink: 1,
              paddingBottom: view.primaryAction ? (barHeight || 20 + 48 + bottomPad) + 12 : 0,
            }}
          >
            {view.children}
          </View>
          {view.primaryAction ? (
            <View
              pointerEvents="box-none"
              onLayout={(e) => setBarHeight(e.nativeEvent.layout.height)}
              style={{
                position: 'absolute',
                left: 0,
                right: 0,
                bottom: 0,
                gap: space.s4,
                paddingHorizontal: space.s7,
                paddingTop: space.s8,
                paddingBottom: bottomPad,
                backgroundColor: colors.bgPane,
              }}
            >
              <View style={{ flexDirection: 'row', gap: space.s4 }}>
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
              {view.footer ?? null}
            </View>
          ) : view.footer ? (
            <View
              style={{
                paddingHorizontal: space.s8,
                paddingTop: space.s5,
                paddingBottom: twoPane ? 8 : Math.max(8, insets.bottom),
              }}
            >
              {view.footer}
            </View>
          ) : (
            <View style={{ paddingBottom: twoPane ? 0 : insets.bottom }} />
          )}
        </Animated.View>
      </Animated.View>
    </Modal>
  );
}
