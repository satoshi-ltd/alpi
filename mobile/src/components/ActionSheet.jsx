import { Modal, Pressable, ScrollView, Text, useWindowDimensions, View } from 'react-native';
import { GestureDetector } from 'react-native-gesture-handler';
import Animated from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { radii, space } from '../theme/tokens';

import { usePane } from '../nav/PaneContext';
import { useTheme } from '../theme/ThemeContext';
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

// Action list caps at 60vh, scrolls internally above the cap.
export function ActionSheet({ open, onClose, title, subtitle, description, actions = [] }) {
  const { colors, fonts, fontSizes } = useTheme();
  const insets = useSafeAreaInsets();
  const { height } = useWindowDimensions();
  const { twoPane } = usePane();
  const { gesture, sheetStyle, backdropStyle, mounted } = useSheetGesture(open, onClose, height + 100);
  const maxListHeight = height * 0.6;
  const dialog = twoPane ? { ...CENTRED_DIALOG, marginBottom: Math.max(insets.bottom, 24) } : null;
  const view = useExitSnapshot(open, { title, subtitle, description, actions });

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
        style={[{ flex: 1, backgroundColor: 'rgba(0,0,0,0.45)' }, backdropStyle]}
      >
        <Pressable style={{ flex: 1 }} onPress={onClose} />
        <Animated.View
          style={[
            {
              backgroundColor: colors.bgPane,
              borderTopLeftRadius: radii['3xl'],
              borderTopRightRadius: radii['3xl'],
              overflow: 'hidden',
              ...dialog,
            },
            sheetStyle,
          ]}
        >
          <GestureDetector gesture={gesture}>
            <View>
              <View style={{ alignItems: 'center', paddingTop: space.s3 }}>
                <View
                  style={{ width: 36, height: 4, borderRadius: 2, backgroundColor: colors.ink4, opacity: 0.6 }}
                />
              </View>
              <View
                style={{
                  flexDirection: 'row',
                  alignItems: 'flex-start',
                  paddingLeft: space.s8,
                  paddingRight: space.s5,
                  paddingTop: space.s5,
                  paddingBottom: space.s6,
                  gap: space.s5,
                }}
              >
                <View style={{ flex: 1, gap: space.s2 }}>
                  {view.title ? (
                    <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.lg, color: colors.ink }}>
                      {view.title}
                    </Text>
                  ) : null}
                  {view.subtitle ? (
                    <Text style={{ fontFamily: fonts.monoMedium, fontSize: fontSizes.xs, color: colors.ink3 }}>
                      {view.subtitle}
                    </Text>
                  ) : null}
                  {view.description ? (
                    <Text
                      style={{
                        fontFamily: fonts.sans.regular,
                        fontSize: fontSizes.sm,
                        lineHeight: fontSizes.sm * 1.5,
                        color: colors.ink2,
                        marginTop: space.s1,
                      }}
                    >
                      {view.description}
                    </Text>
                  ) : null}
                </View>
                <SheetClose onPress={onClose} />
              </View>
              <View style={{ height: 0.5, backgroundColor: colors.line }} />
            </View>
          </GestureDetector>
          <ScrollView
            style={{ maxHeight: maxListHeight }}
            contentContainerStyle={{ paddingBottom: space.s1 }}
            showsVerticalScrollIndicator
          >
            {view.actions.map((a, i) => {
              if (a.divider) {
                return <View key={`d-${i}`} style={{ height: 0.5, backgroundColor: colors.line, marginLeft: 56 }} />;
              }
              return (
                <Pressable
                  key={a.id ?? i}
                  onPress={() => {
                    onClose?.();
                    a.onPress?.();
                  }}
                  android_ripple={{ color: colors.selected }}
                  style={({ pressed }) => ({
                    flexDirection: 'row',
                    alignItems: 'center',
                    gap: space.s6,
                    paddingHorizontal: space.s8,
                    paddingVertical: space.s6,
                    backgroundColor: pressed ? colors.selected : 'transparent',
                  })}
                >
                  {a.icon ? <View style={{ width: 24 }}>{a.icon}</View> : null}
                  <Text
                    style={{
                      flex: 1,
                      fontFamily: fonts.sans.regular,
                      fontSize: fontSizes.lg,
                      color: a.danger ? colors.danger : colors.ink,
                    }}
                  >
                    {a.label}
                  </Text>
                  {a.detail ? (
                    <Text style={{ fontFamily: fonts.monoMedium, fontSize: fontSizes.sm, color: colors.ink3 }}>
                      {a.detail}
                    </Text>
                  ) : null}
                </Pressable>
              );
            })}
          </ScrollView>
          <View style={{ paddingBottom: insets.bottom }} />
        </Animated.View>
      </Animated.View>
    </Modal>
  );
}
