import { useState } from 'react';
import { Pressable, Text, View, Platform } from 'react-native';
import { iconSizes, radii, space } from '../theme/tokens';

import { Eyebrow } from './Eyebrow';
import { GroupToneContext, groupTone } from './groupTone';
import { Icon } from './Icon';
import { stacksRow } from '../lib/panes';
import { useTheme } from '../theme/ThemeContext';

export { groupTone };

export function RowGroup({ children, style }) {
  const { colors } = useTheme();
  const tone = groupTone(colors);
  return (
    <GroupToneContext.Provider value={tone}>
      <View style={[{ marginHorizontal: space.s7, borderRadius: radii.xs, overflow: 'hidden', backgroundColor: tone }, style]}>
        {children}
      </View>
    </GroupToneContext.Provider>
  );
}

export function SectionHeader({ children, kicker, first = false, onLayout }) {
  return (
    <View onLayout={onLayout} style={{ paddingHorizontal: space.s7, paddingTop: space.s9, paddingBottom: space.s3 }}>
      <Eyebrow>{children}{kicker ? ` · ${kicker}` : ''}</Eyebrow>
    </View>
  );
}

export function rowLabel(label, value, helper) {
  return [label, value, helper].filter((part) => typeof part === 'string' && part).join(', ') || undefined;
}

function pressable(body, { onPress, onLongPress, disabled, colors, spoken }) {
  if (disabled || (!onPress && !onLongPress)) return body;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={spoken}
      onPress={onPress}
      onLongPress={onLongPress}
      android_ripple={{ color: colors.selected }}
      style={({ pressed }) => ({ backgroundColor: pressed && Platform.OS !== 'android' ? colors.selected : 'transparent' })}
    >
      {body}
    </Pressable>
  );
}

export function Row({ label, helper, value, leading, trailing, onPress, onLongPress, danger, disabled = false, chevron = true, labelLines = 1, helperLines, helperDanger = false, spokenValue, below }) {
  const { colors, fonts, fontSizes } = useTheme();
  const [width, setWidth] = useState(0);
  const stacked = stacksRow(width);
  const chevronNode = (
    <View testID="row-lane" style={{ width: iconSizes.md, alignItems: 'flex-end' }}>
      {chevron && onPress && !disabled && !danger ? <Icon name="chevron-right" size="md" color={colors.ink4} /> : null}
    </View>
  );
  const valueNode = value ? (
    typeof value === 'string' ? (
      <Text
        style={{
          fontFamily: stacked ? fonts.mono : fonts.sans.regular,
          fontSize: stacked ? fontSizes.sm : fontSizes.md,
          color: stacked ? colors.ink2 : colors.ink3,
          flexShrink: 1,
          textAlign: stacked ? 'left' : 'right',
          maxWidth: stacked ? '100%' : '55%',
        }}
        numberOfLines={1}
        ellipsizeMode={stacked ? 'tail' : 'middle'}
      >
        {value}
      </Text>
    ) : (
      <View style={{ flexShrink: 0, maxWidth: stacked ? '100%' : '55%' }}>{value}</View>
    )
  ) : null;

  const labelNode = (
    <Text
      numberOfLines={labelLines}
      ellipsizeMode="tail"
      style={{
        fontFamily: fonts.sans.regular,
        fontSize: fontSizes.lg,
        color: danger ? colors.dangerText : disabled ? colors.ink3 : colors.ink,
        lineHeight: fontSizes.lg * 1.3,
      }}
    >
      {label}
    </Text>
  );
  const helperNode = helper ? (
    <Text
      numberOfLines={helperLines ?? 2}
      style={{
        fontFamily: fonts.monoMedium,
        fontSize: fontSizes.xs,
        color: helperDanger ? colors.dangerText : colors.ink3,
      }}
    >
      {helper}
    </Text>
  ) : null;

  if (below) {
    return (
      <View style={{ paddingHorizontal: space.s7, paddingVertical: space.s6, gap: space.s5 }}>
        <View style={{ gap: space.s1 }}>
          {labelNode}
          {helperNode}
        </View>
        {below}
      </View>
    );
  }

  const body = (
    <View
      onLayout={(e) => setWidth(e.nativeEvent.layout.width)}
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        paddingHorizontal: space.s7,
        paddingVertical: space.s6,
        gap: space.s5,
      }}
    >
      {leading ? <View>{leading}</View> : null}
      {stacked ? (
        <View style={{ flex: 1, minWidth: 0, gap: space.s1 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s3 }}>
            <View style={{ flex: 1, minWidth: 0 }}>{labelNode}</View>
            {trailing}
            {chevronNode}
          </View>
          {helperNode}
          {valueNode ? <View style={{ marginTop: space.s1 }}>{valueNode}</View> : null}
        </View>
      ) : (
        <>
          <View style={{ flex: 1, minWidth: 0, gap: space.s1 }}>
            {labelNode}
            {helperNode}
          </View>
          {valueNode}
          {trailing}
          {chevronNode}
        </>
      )}
    </View>
  );

  return pressable(body, { onPress, onLongPress, disabled, colors, spoken: rowLabel(label, spokenValue ?? value, helper) });
}

export function RowSeparator({ indent = space.s7 }) {
  const { colors } = useTheme();
  return <View style={{ height: 0.5, backgroundColor: colors.line, marginLeft: indent }} />;
}

export function SettingsBand({ children }) {
  return (
    <View style={{ paddingHorizontal: space.s7, paddingVertical: space.s7 }}>
      {children}
    </View>
  );
}
