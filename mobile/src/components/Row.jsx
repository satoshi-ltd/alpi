import { useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { iconSizes, lineHeights, mobile, space, tracking } from '../theme/tokens';

import { Eyebrow } from './Eyebrow';
import { Icon } from './Icon';
import { stacksRow } from '../lib/panes';
import { useWideSettings } from '../nav/SettingsSurface';
import { useTheme } from '../theme/ThemeContext';

const WIDE_LABEL_W = 148;
const WIDE_SECTION_GAP = 36;

export function SectionHeader({ children, kicker, first = false }) {
  const { colors, fonts, fontSizes } = useTheme();
  const wide = useWideSettings();
  if (wide) {
    return (
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'baseline',
          gap: space.s4,
          marginTop: first ? 0 : WIDE_SECTION_GAP,
          marginBottom: space.s5,
        }}
      >
        <Eyebrow
          color={colors.ink2}
          style={{ fontFamily: fonts.monoSemibold, letterSpacing: fontSizes.xs * tracking.wider }}
        >
          {children}
        </Eyebrow>
        {kicker ? (
          <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.xs, color: colors.ink4 }}>
            {kicker}
          </Text>
        ) : null}
      </View>
    );
  }
  return (
    <View style={{ paddingHorizontal: space.s8, paddingTop: space.s9, paddingBottom: space.s3 }}>
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
      style={({ pressed }) => ({ backgroundColor: pressed ? colors.selected : 'transparent' })}
    >
      {body}
    </Pressable>
  );
}

function WideRow({ label, helper, value, leading, trailing, onPress, onLongPress, danger, disabled, chevron, labelLines, item }) {
  const { colors, fonts, fontSizes } = useTheme();
  const control =
    typeof value === 'string' ? (
      <Text
        numberOfLines={1}
        ellipsizeMode="middle"
        style={{
          fontFamily: fonts.mono,
          fontSize: fontSizes.sm,
          color: colors.ink2,
          flexShrink: 1,
          textAlign: 'right',
        }}
      >
        {value}
      </Text>
    ) : (
      value
    );
  const body = (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        gap: space.s9,
        minHeight: mobile.tap,
        paddingVertical: space.s3,
        opacity: disabled ? 0.45 : 1,
      }}
    >
      {leading ? <View>{leading}</View> : null}
      <View style={{ flexBasis: WIDE_LABEL_W, flexGrow: 1, flexShrink: 1, minWidth: 0 }}>
        {item ? (
          <Text
            numberOfLines={Math.max(labelLines, 1)}
            style={{
              fontFamily: fonts.sans.semibold,
              fontSize: fontSizes.md,
              lineHeight: fontSizes.md * lineHeights.cozy,
              color: danger ? colors.dangerText : colors.ink,
            }}
          >
            {label}
          </Text>
        ) : (
          <Eyebrow
            numberOfLines={Math.max(labelLines, 2)}
            color={danger ? colors.dangerText : colors.ink3}
            style={{ lineHeight: fontSizes.xs * lineHeights.cozy }}
          >
            {label}
          </Eyebrow>
        )}
        {helper ? (
          <Text
            numberOfLines={2}
            style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: item ? colors.ink3 : colors.ink4, marginTop: space.s1 }}
          >
            {helper}
          </Text>
        ) : null}
      </View>
      <View style={{ flexShrink: 1, minWidth: 0, maxWidth: '60%', flexDirection: 'row', alignItems: 'center', justifyContent: 'flex-end', gap: space.s4 }}>
        {control}
        {trailing}
        {danger || trailing ? null : (
          <View style={{ width: iconSizes.sm, alignItems: 'flex-end' }}>
            {chevron && onPress && !disabled ? <Icon name="chevron-right" size="sm" color={colors.ink4} /> : null}
          </View>
        )}
      </View>
    </View>
  );
  return pressable(body, { onPress, onLongPress, disabled, colors, spoken: rowLabel(label, value, helper) });
}

export function Row({ label, helper, value, leading, trailing, onPress, onLongPress, danger, disabled = false, chevron = true, labelLines = 1, item = false }) {
  const { colors, fonts, fontSizes } = useTheme();
  const wide = useWideSettings();
  const [width, setWidth] = useState(0);
  if (wide) {
    return (
      <WideRow
        label={label}
        helper={helper}
        value={value}
        leading={leading}
        trailing={trailing}
        onPress={onPress}
        onLongPress={onLongPress}
        danger={danger}
        disabled={disabled}
        chevron={chevron}
        labelLines={labelLines}
        item={item}
      />
    );
  }
  const stacked = stacksRow(width);
  const chevronNode =
    chevron && onPress && !disabled && !danger ? (
      <Icon name="chevron-right" size="md" color={colors.ink4} />
    ) : null;
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
        color: danger ? colors.dangerText : colors.ink,
        lineHeight: fontSizes.lg * 1.3,
      }}
    >
      {label}
    </Text>
  );
  const helperNode = helper ? (
    <Text
      numberOfLines={1}
      style={{
        fontFamily: fonts.monoMedium,
        fontSize: fontSizes.xs,
        color: colors.ink3,
      }}
    >
      {helper}
    </Text>
  ) : null;

  const body = (
    <View
      onLayout={(e) => setWidth(e.nativeEvent.layout.width)}
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        paddingHorizontal: space.s8,
        paddingVertical: space.s6,
        gap: space.s5,
        backgroundColor: colors.bgPane,
        opacity: disabled ? 0.45 : 1,
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
          {/* Label container shrinks but always renders its label (min-width: 0 + flexShrink: 1 lets the value truncate before the label disappears). */}
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

  return pressable(body, { onPress, onLongPress, disabled, colors, spoken: rowLabel(label, value, helper) });
}

export function RowSeparator({ indent = 20 }) {
  const { colors } = useTheme();
  const wide = useWideSettings();
  if (wide) return null;
  return <View style={{ height: 0.5, backgroundColor: colors.line, marginLeft: indent }} />;
}

export function SettingsBand({ children }) {
  const { colors } = useTheme();
  const wide = useWideSettings();
  if (wide) return <View>{children}</View>;
  return (
    <View style={{ backgroundColor: colors.bgPane, paddingHorizontal: space.s8, paddingVertical: space.s7 }}>
      {children}
    </View>
  );
}
