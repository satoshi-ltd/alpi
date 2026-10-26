import { useEffect } from 'react';
import { POPOVER_W, popoverPosition, sheetStyles } from './sheetStyles';
import { Dimensions, Modal, Pressable, ScrollView, Text, useWindowDimensions, View } from 'react-native';
import { GestureDetector } from 'react-native-gesture-handler';
import Animated from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { alpha, radii, space, lineHeights, typography, veil } from '../theme/tokens';

import { selection } from '../lib/haptics';
import { usePane } from '../nav/PaneContext';
import { dotShape } from './dotShape';
import { useTheme } from '../theme/ThemeContext';
import { PICKER_GAP, PickerLead, PICKER_TEXT_EDGE } from './PickerLead';
import { SheetClose } from './SheetClose';
import { Toggle } from './Toggle';
import { useExitSnapshot } from './useExitSnapshot';
import { useSheetGesture } from './useSheetGesture';



// Action list caps at 60vh, scrolls internally above the cap.
export function ActionSheet({ open, onClose, title, subtitle, description, actions = [], anchor = null }) {
  const { colors, fonts, fontSizes, shadow } = useTheme();
  const insets = useSafeAreaInsets();
  const { height, width } = useWindowDimensions();
  const { twoPane } = usePane();
  const { gesture, sheetStyle, backdropStyle, mounted } = useSheetGesture(open, onClose, height + 100);
  const maxListHeight = height * 0.6;
  const dialog = twoPane ? sheetStyles.dialog : null;
  const popover = twoPane && anchor ? popoverPosition(anchor, width, height, maxListHeight, insets.bottom) : null;
  const view = useExitSnapshot(open, { title, subtitle, description, actions });
  const pickable = view.actions.some((a) => 'selected' in a);

  useEffect(() => {
    if (open && pickable) selection();
  }, [open]);

  const anchored = !!popover && open;
  useEffect(() => {
    if (!anchored) return undefined;
    const subscription = Dimensions.addEventListener('change', () => onClose?.());
    return () => subscription.remove();
  }, [anchored, onClose]);

  const header = (
    <View>
      {twoPane ? null : (
        <View style={sheetStyles.grabberWrap}>
          <View
            style={[sheetStyles.grabber, { backgroundColor: colors.ink4 }]}
          />
        </View>
      )}
      <View
        style={[sheetStyles.header, twoPane && sheetStyles.dialogHeader]}
      >
        <View style={{ flex: 1, gap: space.s2 }}>
          {view.title ? (
            <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes[typography.dialogTitle.size], lineHeight: fontSizes[typography.dialogTitle.size] * lineHeights[typography.dialogTitle.leading], color: colors.ink }}>
              {view.title}
            </Text>
          ) : null}
          {view.subtitle ? (
            <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes[typography.caption.size], color: colors.ink3 }}>
              {view.subtitle}
            </Text>
          ) : null}
          {view.description ? (
            <Text
              style={{
                fontFamily: fonts.sans.regular,
                fontSize: fontSizes[typography.body.size],
                lineHeight: fontSizes[typography.body.size] * lineHeights[typography.body.leading],
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
  );

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
        style={[{ flex: 1, backgroundColor: popover ? 'transparent' : veil(colors), justifyContent: twoPane ? 'center' : 'flex-end' }, backdropStyle]}
      >
        <Pressable style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }} onPress={onClose} accessible={false} />
        <Animated.View
          style={[
            popover
              ? {
                  position: 'absolute',
                  ...popover,
                  width: POPOVER_W,
                  backgroundColor: colors.bgPane,
                  ...shadow.popover,
                  borderRadius: radii.xs,
                  overflow: 'hidden',
                  paddingVertical: space.s1,
                }
              : {
                  backgroundColor: colors.bgPane,
                  ...(twoPane ? shadow.dialog : shadow.sheet),
                  borderTopLeftRadius: radii.xs,
                  borderTopRightRadius: radii.xs,
                  overflow: 'hidden',
                  ...dialog,
                },
            popover ? null : sheetStyle,
          ]}
        >
          {popover ? null : twoPane ? header : <GestureDetector gesture={gesture}>{header}</GestureDetector>}
          <ScrollView
            style={{ maxHeight: maxListHeight }}
            contentContainerStyle={{ paddingBottom: space.s1 }}
            showsVerticalScrollIndicator
          >
            {view.actions.map((a, i) => {
              if (a.divider) {
                return <View key={`d-${i}`} style={{ height: 0.5, backgroundColor: colors.line, marginLeft: pickable ? PICKER_TEXT_EDGE : 52 }} />;
              }
              const isSwitch = a.kind === 'switch';
              return (
                <Pressable
                  key={a.id ?? i}
                  accessibilityRole={isSwitch ? 'switch' : 'button'}
                  disabled={!!a.disabled}
                  onPress={() => {
                    if (a.disabled) return;
                    if (isSwitch) {
                      a.onValueChange?.(!a.value);
                      return;
                    }
                    onClose?.();
                    a.onPress?.();
                  }}
                  android_ripple={{ color: colors.selected }}
                  accessibilityState={isSwitch ? { disabled: !!a.disabled, checked: !!a.value } : { disabled: !!a.disabled, selected: !!a.selected }}
                  style={({ pressed }) => ({
                    flexDirection: 'row',
                    alignItems: 'center',
                    gap: PICKER_GAP,
                    paddingHorizontal: space.s7,
                    paddingVertical: space.s6,
                    backgroundColor: pressed || a.selected ? colors.selected : 'transparent',
                    opacity: a.disabled ? alpha.disabled : 1,
                  })}
                >
                  {pickable ? <PickerLead selected={!!a.selected} /> : null}
                  {a.icon ? (
                    <View style={{ width: 24 }}>
                      {a.icon}
                      {a.badge ? (
                        <View
                          testID="action-badge"
                          style={{ position: 'absolute', top: -2, right: 0, ...dotShape('md'), backgroundColor: colors.danger }}
                        />
                      ) : null}
                    </View>
                  ) : null}
                  <Text
                    style={{
                      flex: 1,
                      fontFamily: fonts.sans.regular,
                      fontSize: fontSizes.lg,
                      color: a.danger ? colors.dangerText : colors.ink,
                    }}
                  >
                    {a.label}
                  </Text>
                  {a.detail ? (
                    <Text style={{ fontFamily: fonts.monoMedium, fontSize: fontSizes.sm, color: a.detailDanger ? colors.dangerText : colors.ink3 }}>
                      {a.detail}
                    </Text>
                  ) : null}
                  {isSwitch ? (
                    <View pointerEvents="none" accessible={false} importantForAccessibility="no-hide-descendants">
                      <Toggle on={!!a.value} label={a.label} disabled={!!a.disabled} />
                    </View>
                  ) : null}
                </Pressable>
              );
            })}
          </ScrollView>
          <View style={{ paddingBottom: twoPane ? 0 : insets.bottom }} />
        </Animated.View>
      </Animated.View>
    </Modal>
  );
}
