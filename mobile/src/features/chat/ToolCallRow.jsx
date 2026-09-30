import { useEffect, useRef, useState } from 'react';
import { Animated, Pressable, Text, View } from 'react-native';
import { lineHeights, mobile, space } from '../../theme/tokens';

import { Icon } from '../../components/Icon';
import { useReduceMotion } from '../../lib/reduceMotion';
import { useTheme } from '../../theme/ThemeContext';
import { pluralize } from '../../../../common/pluralize.mjs';
import { ToolDetailSheet } from './ToolDetailSheet';
import { failureLine, toolFamily, toolSummary } from './toolDetail';

export function toolStatus(t) {
  if (t.ok === null || t.ok === undefined) return 'running';
  return t.ok ? 'success' : 'error';
}

export function ToolCallRow({ tool, status = 'success', accent, primary = false, onPress }) {
  const { colors, fonts, fontSizes } = useTheme();
  const reduceMotion = useReduceMotion();
  const isRunning = status === 'running';
  const failed = status === 'error';
  const iconColor = failed ? colors.danger
    : primary ? (accent ?? colors.ink2)
    : colors.ink3;

  const pulse = useRef(new Animated.Value(1)).current;
  useEffect(() => {
    if (!isRunning || reduceMotion) return undefined;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 0.35, duration: 700, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 1, duration: 700, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [isRunning, reduceMotion, pulse]);

  const summary = failed ? failureLine(tool) : toolSummary(tool?.args);
  const lh = fontSizes.md * lineHeights.cozy;

  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`${tool?.name ?? 'tool'}${failed ? ', failed' : ''}. Show details`}
      style={({ pressed }) => ({
        flexDirection: 'row',
        alignItems: 'center',
        gap: space.s5,
        minHeight: mobile.tap,
        opacity: pressed ? 0.6 : 1,
      })}
    >
      <Animated.View style={{ opacity: isRunning && !reduceMotion ? pulse : 1 }}>
        <Icon name={toolFamily(tool?.name)} size="md" color={iconColor} />
      </Animated.View>
      <View style={{ flex: 1, minWidth: 0 }}>
        <Text
          numberOfLines={1}
          style={{
            fontFamily: fonts.monoMedium,
            fontSize: fontSizes.md,
            lineHeight: lh,
            color: failed ? colors.dangerText : colors.ink,
            includeFontPadding: false,
          }}
        >
          {tool?.name}
        </Text>
        {summary ? (
          <Text
            numberOfLines={1}
            style={{
              fontFamily: fonts.sans.regular,
              fontSize: fontSizes.md,
              lineHeight: lh,
              color: failed ? colors.dangerText : colors.ink2,
              includeFontPadding: false,
            }}
          >
            {summary}
          </Text>
        ) : null}
      </View>
      <Icon name="chevron-right" size="sm" color={colors.ink3} />
    </Pressable>
  );
}

export function ToolModule({ tools, accent }) {
  const { colors, fonts, fontSizes } = useTheme();
  const [expandedPref, setExpanded] = useState(null);
  const [detail, setDetail] = useState(null);
  const [armed, setArmed] = useState(false);
  if (!tools.length) return null;
  const runningIdx = tools.findIndex((t) => t.ok == null);
  const active = runningIdx >= 0;
  const open = (t) => {
    setArmed(true);
    setDetail(tools.indexOf(t));
  };
  const shown = detail == null ? null : tools[detail] ?? null;
  const sheet = armed
    ? <ToolDetailSheet tool={shown} status={shown ? toolStatus(shown) : 'success'} onClose={() => setDetail(null)} />
    : null;

  if (tools.length === 1) {
    const t = tools[0];
    return (
      <View style={{ paddingHorizontal: space.s7 }}>
        <ToolCallRow tool={t} status={toolStatus(t)} accent={accent} primary onPress={() => open(t)} />
        {sheet}
      </View>
    );
  }

  const primary = active ? tools[runningIdx] : null;
  const bucket = active ? tools.filter((_, i) => i !== runningIdx) : tools;
  const n = bucket.length;
  const noun = pluralize(n, 'tool call');
  const failed = bucket.filter((t) => toolStatus(t) === 'error').length;
  const expanded = expandedPref ?? failed > 0;
  const collapsedLabel = active ? `+${n} previous ${noun}` : `${n} ${noun}`;
  const expandedLabel = active ? 'Hide previous tool calls' : 'Hide tool calls';

  return (
    <View>
      <View style={{ paddingHorizontal: space.s7 }}>
        <Pressable
          onPress={() => setExpanded(!expanded)}
          accessibilityRole="button"
          accessibilityState={{ expanded }}
          accessibilityLabel={expanded ? expandedLabel : `Show ${collapsedLabel.replace(/^\+/, '')}`}
          style={{ flexDirection: 'row', alignItems: 'center', gap: space.s2, alignSelf: 'flex-start', minHeight: mobile.tap }}
        >
          <View style={{ transform: [{ rotate: expanded ? '0deg' : '-90deg' }] }}>
            <Icon name="chevron-down" size="xs" color={colors.ink3} />
          </View>
          <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.ink3 }}>
            {expanded ? expandedLabel : collapsedLabel}
          </Text>
          {!expanded && failed > 0 ? (
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
              <Icon name="triangle-alert" size="xs" color={colors.danger} />
              <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.dangerText }}>
                {`${failed} failed`}
              </Text>
            </View>
          ) : null}
        </Pressable>
      </View>
      {expanded ? bucket.map((t, i) => (
        <View key={t.tool_id ?? `${t.name}:${i}`} style={{ paddingLeft: space.s7 + space.s5, paddingRight: space.s7 }}>
          <ToolCallRow tool={t} status={toolStatus(t)} accent={accent} onPress={() => open(t)} />
        </View>
      )) : null}
      {primary ? (
        <View style={{ paddingHorizontal: space.s7 }}>
          <ToolCallRow tool={primary} status={toolStatus(primary)} accent={accent} primary onPress={() => open(primary)} />
        </View>
      ) : null}
      {sheet}
    </View>
  );
}
