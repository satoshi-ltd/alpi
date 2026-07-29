import { useEffect, useRef, useState } from 'react';
import { Animated, Pressable, Text, View } from 'react-native';
import { fontSizes, space } from '../../theme/tokens';

import { Icon } from '../../components/Icon';
import { useTheme } from '../../theme/ThemeContext';

function formatArgs(value) {
  if (value == null) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) return value.map(formatArgs).join(' ');
  if (typeof value === 'object') {
    return Object.entries(value)
      .filter(([, v]) => v !== undefined && v !== null && v !== '')
      .map(([k, v]) => `${k}=${typeof v === 'object' ? JSON.stringify(v) : v}`)
      .join(' ');
  }
  return String(value);
}

export function toolStatus(t) {
  if (t.ok === null || t.ok === undefined) return 'running';
  return t.ok ? 'success' : 'error';
}

export function ToolCallRow({ name, status = 'success', args, accent, primary = false }) {
  const { colors, fonts } = useTheme();
  const isRunning = status === 'running';
  const iconColor = status === 'error' ? colors.danger
    : primary ? (accent ?? colors.ink2)
    : colors.ink3;

  const pulse = useRef(new Animated.Value(1)).current;
  useEffect(() => {
    if (!isRunning) return undefined;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 0.35, duration: 700, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 1, duration: 700, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [isRunning, pulse]);

  const argsStr = formatArgs(args);

  return (
    <View style={{
      flexDirection: 'row',
      alignItems: 'center',
      gap: space.s3,
      alignSelf: 'flex-start',
      maxWidth: '100%',
      paddingVertical: 2,
    }}>
      <Animated.View style={{ opacity: isRunning ? pulse : 1 }}>
        <Icon name="cpu" size={14} color={iconColor} />
      </Animated.View>
      <Text style={{
        fontFamily: fonts.monoMedium,
        fontSize: fontSizes.sm,
        lineHeight: 16,
        color: status === 'error' ? colors.danger : colors.ink,
        includeFontPadding: false,
      }}>
        {name}
      </Text>
      {argsStr ? (
        <Text
          numberOfLines={1}
          style={{
            flex: 1,
            minWidth: 0,
            fontFamily: fonts.mono,
            fontSize: fontSizes.sm,
            lineHeight: 16,
            color: colors.ink3,
            includeFontPadding: false,
          }}
        >
          {argsStr}
        </Text>
      ) : null}
    </View>
  );
}

export function ToolModule({ tools, accent }) {
  const { colors, fonts } = useTheme();
  const [expanded, setExpanded] = useState(false);
  if (!tools.length) return null;
  const runningIdx = tools.findIndex((t) => t.ok == null);
  const active = runningIdx >= 0;

  if (tools.length === 1) {
    const t = tools[0];
    return (
      <View style={{ paddingHorizontal: space.s7 }}>
        <ToolCallRow name={t.name} status={toolStatus(t)} args={t.args} accent={accent} primary />
      </View>
    );
  }

  const primary = active ? tools[runningIdx] : null;
  const bucket = active ? tools.filter((_, i) => i !== runningIdx) : tools;
  const n = bucket.length;
  const noun = n === 1 ? 'tool call' : 'tool calls';
  const failed = bucket.filter((t) => toolStatus(t) === 'error').length;
  const collapsedLabel = active ? `+${n} previous ${noun}` : `${n} ${noun}`;
  const expandedLabel = active ? 'Hide previous tool calls' : 'Hide tool calls';

  return (
    <View style={{ gap: space.s2 }}>
      <View style={{ paddingHorizontal: space.s7 }}>
        <Pressable
          onPress={() => setExpanded((v) => !v)}
          hitSlop={8}
          accessibilityRole="button"
          accessibilityState={{ expanded }}
          accessibilityLabel={expanded ? expandedLabel : `Show ${collapsedLabel.replace(/^\+/, '')}`}
          style={{ flexDirection: 'row', alignItems: 'center', gap: space.s2, alignSelf: 'flex-start', minHeight: 44 }}
        >
          <View style={{ transform: [{ rotate: expanded ? '0deg' : '-90deg' }] }}>
            <Icon name="chevron-down" size={12} color={colors.ink3} />
          </View>
          <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.ink3 }}>
            {expanded ? expandedLabel : collapsedLabel}
          </Text>
          {!expanded && failed > 0 ? (
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
              <Icon name="triangle-alert" size={13} color={colors.danger} />
              <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.danger }}>
                {`${failed} failed`}
              </Text>
            </View>
          ) : null}
        </Pressable>
      </View>
      {expanded ? bucket.map((t, i) => (
        <View key={t.tool_id ?? `${t.name}:${i}`} style={{ paddingLeft: space.s7 + space.s5, paddingRight: space.s7 }}>
          <ToolCallRow name={t.name} status={toolStatus(t)} args={t.args} accent={accent} />
        </View>
      )) : null}
      {primary ? (
        <View style={{ paddingHorizontal: space.s7 }}>
          <ToolCallRow name={primary.name} status={toolStatus(primary)} args={primary.args} accent={accent} primary />
        </View>
      ) : null}
    </View>
  );
}
