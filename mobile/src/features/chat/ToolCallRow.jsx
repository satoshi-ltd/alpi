import { useEffect, useRef, useState } from 'react';
import { Animated, Pressable, Text, View } from 'react-native';
import { fontSizes, radii, space } from '../../theme/tokens';

import { Diamond } from '../../components/Diamond';
import { useTheme } from '../../theme/ThemeContext';

function mixHex(hex, pct, base) {
  const fromHex = (h) => {
    const v = h.replace('#', '');
    return [parseInt(v.slice(0, 2), 16), parseInt(v.slice(2, 4), 16), parseInt(v.slice(4, 6), 16)];
  };
  const [r1, g1, b1] = fromHex(hex);
  const [r2, g2, b2] = fromHex(base);
  const r = Math.round(r1 * pct + r2 * (1 - pct));
  const g = Math.round(g1 * pct + g2 * (1 - pct));
  const b = Math.round(b1 * pct + b2 * (1 - pct));
  return `rgb(${r},${g},${b})`;
}

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

// 1:1 with desktop .tool styling: base = mix(ink 3%, bgPane) + line border; running = accent 5% bg + accent 55% border + pulse; fail = danger 5% bg + danger 55% border + danger diamond.
function toolColors(colors, accent, status) {
  if (status === 'running') {
    return {
      bg: accent ? mixHex(accent, 0.05, colors.bgPane) : mixHex(colors.ink, 0.03, colors.bgPane),
      border: accent ? mixHex(accent, 0.55, colors.bgPane) : colors.line,
      diamond: accent ?? colors.ink3,
    };
  }
  // Error keeps neutral bg/border per design — only diamond goes danger.
  return {
    bg: mixHex(colors.ink, 0.03, colors.bgPane),
    border: colors.line,
    diamond: status === 'error' ? colors.danger : (accent ?? colors.ink3),
  };
}

export function ToolCallRow({ name, status = 'success', args, accent }) {
  const { colors, fonts } = useTheme();
  const isRunning = status === 'running';
  const tone = toolColors(colors, accent, status);

  const pulse = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    if (!isRunning) return undefined;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 700, useNativeDriver: false }),
        Animated.timing(pulse, { toValue: 0, duration: 700, useNativeDriver: false }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [isRunning, pulse]);
  const shadowOpacity = pulse.interpolate({ inputRange: [0, 1], outputRange: [0, 0.35] });

  const argsStr = formatArgs(args);

  return (
    <View style={{ paddingHorizontal: space.s7 }}>
      <Animated.View
        style={{
          alignSelf: 'flex-start',
          flexDirection: 'row',
          alignItems: 'center',
          gap: space.s3,
          paddingHorizontal: space.s5,
          paddingVertical: space.s2,
          borderRadius: radii.sm,
          backgroundColor: tone.bg,
          borderWidth: 0.5,
          borderColor: tone.border,
          maxWidth: '100%',
          shadowColor: accent ?? colors.ink,
          shadowOpacity: isRunning ? shadowOpacity : 0,
          shadowRadius: 6,
          shadowOffset: { width: 0, height: 0 },
        }}
      >
        <Diamond color={tone.diamond} />
        <Text
          style={{
            fontFamily: fonts.monoMedium,
            fontSize: fontSizes.sm,
            lineHeight: 14,
            color: colors.ink,
            includeFontPadding: false,
          }}
        >
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
              lineHeight: 14,
              color: colors.ink3,
              includeFontPadding: false,
            }}
          >
            {argsStr}
          </Text>
        ) : null}
      </Animated.View>
    </View>
  );
}

// Adjacent same-name tools collapse into one row with ×N badge + per-call dots; tap to expand.
export function groupConsecutiveTools(tools) {
  const groups = [];
  for (const t of tools) {
    const last = groups[groups.length - 1];
    if (last && last.name === t.name) {
      last.tools.push(t);
    } else {
      groups.push({ name: t.name, tools: [t] });
    }
  }
  return groups;
}

function toolStatus(t) {
  if (t.ok === null || t.ok === undefined) return 'running';
  return t.ok ? 'success' : 'error';
}

export function ToolCallGroup({ group, accent }) {
  const { colors, fonts } = useTheme();
  const [expanded, setExpanded] = useState(false);

  if (group.tools.length === 1) {
    const t = group.tools[0];
    return <ToolCallRow name={t.name} status={toolStatus(t)} args={t.args} accent={accent} />;
  }

  // Group derives status from worst child: any error → error; any running → running; else success.
  const groupStatus = group.tools.some((t) => toolStatus(t) === 'error') ? 'error'
    : group.tools.some((t) => toolStatus(t) === 'running') ? 'running'
    : 'success';
  const isRunning = groupStatus === 'running';
  const tone = toolColors(colors, accent, groupStatus);
  const last = group.tools[group.tools.length - 1];
  const argsStr = (last.args !== null && last.args !== undefined)
    ? (typeof last.args === 'string' ? last.args : Object.entries(last.args).map(([k, v]) => `${k}=${v}`).join(' '))
    : '';

  return (
    <View style={{ gap: space.s1 }}>
      <View style={{ paddingHorizontal: space.s7 }}>
        <Pressable
          onPress={() => setExpanded((v) => !v)}
          style={({ pressed }) => ({
            alignSelf: 'flex-start',
            flexDirection: 'row',
            alignItems: 'center',
            gap: space.s3,
            paddingHorizontal: space.s5,
            paddingVertical: space.s2,
            borderRadius: radii.sm,
            backgroundColor: pressed ? colors.selected : tone.bg,
            borderWidth: 0.5,
            borderColor: tone.border,
            maxWidth: '100%',
          })}
        >
          <Diamond color={tone.diamond} />
          <Text style={{ fontFamily: fonts.monoMedium, fontSize: fontSizes.sm, color: colors.ink }}>
            {group.name}
          </Text>
          <View style={{
            paddingHorizontal: space.s2,
            height: 15,
            borderRadius: radii.sm,
            backgroundColor: colors.hover,
            justifyContent: 'center',
          }}>
            <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3, lineHeight: 15 }}>
              ×{group.tools.length}
            </Text>
          </View>
          <View style={{ flexDirection: 'row', gap: space.s1 }}>
            {group.tools.map((t, i) => {
              const st = toolStatus(t);
              const bg = st === 'error' ? colors.danger
                : st === 'running' ? (accent ?? colors.ink2)
                : colors.ink4;
              return <View key={t.tool_id ?? i} style={{ width: 4, height: 4, borderRadius: 2, backgroundColor: bg }} />;
            })}
          </View>
          {argsStr ? (
            <Text
              numberOfLines={1}
              style={{
                flex: 1,
                minWidth: 0,
                fontFamily: fonts.mono,
                fontSize: fontSizes.sm,
                color: colors.ink4,
              }}
            >
              {argsStr}
            </Text>
          ) : null}
        </Pressable>
      </View>
      {expanded && group.tools.map((t, i) => (
        <View key={t.tool_id ?? `${t.name}:${i}`} style={{ paddingLeft: space.s7 }}>
          <ToolCallRow
            name={t.name}
            status={toolStatus(t)}
            args={t.args}
            accent={accent}
          />
        </View>
      ))}
    </View>
  );
}
