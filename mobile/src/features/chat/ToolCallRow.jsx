import { useEffect, useRef, useState } from 'react';
import { Animated, Pressable, Text, View } from 'react-native';
import { space } from '../../theme/tokens';

import { Expand } from '../../components/Expand';
import { Icon } from '../../components/Icon';
import { useReduceMotion } from '../../lib/reduceMotion';
import { useTheme } from '../../theme/ThemeContext';
import { pluralize } from '../../../../common/pluralize.mjs';
import { ToolDetailSheet } from './ToolDetailSheet';
import { failureLine, toolFamily, toolSummary } from './toolDetail';
import { PROCESS_GAP, PROCESS_INDENT, PROCESS_LEAD_W, processRowStyle, processSlop, processText } from './processRow';

export function toolStatus(t) {
  if (t.ok === null || t.ok === undefined) return 'running';
  return t.ok ? 'success' : 'error';
}

export function ToolCallRow({ tool, status = 'success', accent, primary = false, onPress, edges }) {
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

  const theme = { colors, fonts, fontSizes };
  const summary = failed ? failureLine(tool) : toolSummary(tool?.args);

  return (
    <Pressable
      onPress={onPress}
      hitSlop={processSlop(edges)}
      accessibilityRole="button"
      accessibilityLabel={`${tool?.name ?? 'tool'}${failed ? ', failed' : ''}. Show details`}
      style={({ pressed }) => ({ ...processRowStyle, opacity: pressed ? 0.6 : 1 })}
    >
      <Animated.View style={{ width: PROCESS_LEAD_W, alignItems: 'center', opacity: isRunning && !reduceMotion ? pulse : 1 }}>
        <Icon name={toolFamily(tool?.name)} size="xs" color={iconColor} />
      </Animated.View>
      <Text numberOfLines={1} style={{ ...processText(theme, failed ? colors.dangerText : colors.ink2), flexShrink: 0, maxWidth: '55%' }}>
        {tool?.name}
      </Text>
      {summary ? (
        <Text numberOfLines={1} style={{ ...processText(theme, failed ? colors.dangerText : colors.ink3), flex: 1, minWidth: 0 }}>
          {summary}
        </Text>
      ) : <View style={{ flex: 1 }} />}
      <Icon name="chevron-right" size="xs" color={colors.ink4} />
    </Pressable>
  );
}

export function ToolModule({ tools, accent, edges }) {
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

  const theme = { colors, fonts, fontSizes };
  if (tools.length === 1) {
    const t = tools[0];
    return (
      <View>
        <ToolCallRow tool={t} status={toolStatus(t)} accent={accent} primary edges={edges} onPress={() => open(t)} />
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
  const shownBelow = (expanded ? bucket.length : 0) + (primary ? 1 : 0);
  const rowEdges = (i) => ({ top: i === 0 && edges?.top, bottom: i === shownBelow && edges?.bottom });

  return (
    <View style={{ gap: PROCESS_GAP }}>
      <Pressable
        onPress={() => setExpanded(!expanded)}
        hitSlop={processSlop(rowEdges(0))}
        accessibilityRole="button"
        accessibilityState={{ expanded }}
        accessibilityLabel={expanded ? expandedLabel : `Show ${collapsedLabel.replace(/^\+/, '')}`}
        style={processRowStyle}
      >
        <View style={{ width: PROCESS_LEAD_W, alignItems: 'center', transform: [{ rotate: expanded ? '90deg' : '0deg' }] }}>
          <Icon name="chevron-right" size="xs" color={colors.ink3} />
        </View>
        <Text style={processText(theme, colors.ink3)}>
          {expanded ? expandedLabel : collapsedLabel}
        </Text>
        {!expanded && failed > 0 ? (
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s1 }}>
            <Icon name="triangle-alert" size="xs" color={colors.danger} />
            <Text style={processText(theme, colors.dangerText)}>{`${failed} failed`}</Text>
          </View>
        ) : null}
      </Pressable>
      <Expand open={expanded} contentStyle={{ gap: PROCESS_GAP }}>
        {bucket.map((t, i) => (
          <View key={t.tool_id ?? `${t.name}:${i}`} style={{ paddingLeft: PROCESS_INDENT }}>
            <ToolCallRow tool={t} status={toolStatus(t)} accent={accent} edges={rowEdges(i + 1)} onPress={() => open(t)} />
          </View>
        ))}
      </Expand>
      {primary ? (
        <ToolCallRow tool={primary} status={toolStatus(primary)} accent={accent} primary edges={rowEdges(shownBelow)} onPress={() => open(primary)} />
      ) : null}
      {sheet}
    </View>
  );
}
