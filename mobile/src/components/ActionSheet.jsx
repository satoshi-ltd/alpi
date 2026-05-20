import { Dimensions, Modal, Pressable, ScrollView, Text, View } from 'react-native';
import { GestureDetector } from 'react-native-gesture-handler';
import Animated from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { radii, space , fontSizes} from '../theme/tokens';

import { useTheme } from '../theme/ThemeContext';
import { useSheetGesture } from './useSheetGesture';

// Action list caps at 60vh, scrolls internally above the cap.
export function ActionSheet({ open, onClose, title, subtitle, description, actions = [] }) {
  const { colors, fonts, fontSizes } = useTheme();
  const insets = useSafeAreaInsets();
  const { gesture, sheetStyle, backdropStyle, mounted } = useSheetGesture(open, onClose);
  const maxListHeight = Dimensions.get('window').height * 0.6;

  return (
    <Modal visible={mounted} transparent animationType="none" onRequestClose={onClose}>
      <Animated.View style={[{ flex: 1, backgroundColor: 'rgba(0,0,0,0.45)' }, backdropStyle]}>
        <Pressable style={{ flex: 1 }} onPress={onClose} />
        <Animated.View
          style={[
            {
              backgroundColor: colors.bgPane,
              borderTopLeftRadius: radii['3xl'],
              borderTopRightRadius: radii['3xl'],
              overflow: 'hidden',
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
              {title || description ? (
                <View style={{ paddingHorizontal: space.s8, paddingTop: space.s6, paddingBottom: space.s6, gap: space.s2 }}>
                  {title ? (
                    <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.lg, color: colors.ink }}>
                      {title}
                    </Text>
                  ) : null}
                  {subtitle ? (
                    <Text style={{ fontFamily: fonts.monoMedium, fontSize: fontSizes.xs, color: colors.ink3 }}>
                      {subtitle}
                    </Text>
                  ) : null}
                  {description ? (
                    <Text
                      style={{
                        fontFamily: fonts.sans.regular,
                        fontSize: fontSizes.sm,
                        lineHeight: fontSizes.sm * 1.5,
                        color: colors.ink2,
                        marginTop: space.s1,
                      }}
                    >
                      {description}
                    </Text>
                  ) : null}
                </View>
              ) : null}
              <View style={{ height: 0.5, backgroundColor: colors.line }} />
            </View>
          </GestureDetector>
          <ScrollView
            style={{ maxHeight: maxListHeight }}
            contentContainerStyle={{ paddingBottom: space.s1 }}
            showsVerticalScrollIndicator
          >
            {actions.map((a, i) => {
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
