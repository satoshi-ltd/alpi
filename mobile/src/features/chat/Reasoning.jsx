import { useEffect, useRef, useState } from 'react';
import { Pressable, ScrollView, Text, useWindowDimensions, View } from 'react-native';

import Svg, { Defs, LinearGradient, Rect, Stop } from 'react-native-svg';

import { Icon } from '../../components/Icon';
import { useTheme } from '../../theme/ThemeContext';
import { lineHeights, space } from '../../theme/tokens';
import { fmtDuration, thoughtLabel } from './reasoningLabel';

const STREAM_WINDOW_H = 116;
const STREAM_FADE_H = 28;

function toLines(text) {
  return String(text || '')
    .split('\n')
    .map((s) => s.replace(/\s+$/, ''))
    .filter((s) => s.trim());
}

export function Reasoning({ text, seconds, streaming = false, flat = false }) {
  if (!streaming && !String(text || '').trim()) return null;
  return streaming
    ? <Thinking text={text} flat={flat} />
    : <Finished text={text} seconds={seconds} flat={flat} />;
}

function Trace({ flat, children }) {
  const { colors } = useTheme();
  if (flat) return <View>{children}</View>;
  return (
    <View style={{ borderLeftWidth: 2, borderLeftColor: colors.line2, paddingLeft: space.s6 }}>
      {children}
    </View>
  );
}

function Lines({ text, size }) {
  const { colors, fonts, fontSizes } = useTheme();
  const fs = size ?? fontSizes.sm;
  return (
    <>
      {toLines(text).map((line, i) => (
        <Text
          key={i}
          style={{
            color: colors.ink3,
            fontFamily: fonts.mono,
            fontSize: fs,
            lineHeight: fs * lineHeights.relaxed,
            marginTop: i === 0 ? 0 : space.s2,
          }}
        >
          {line}
        </Text>
      ))}
    </>
  );
}

function Thinking({ text, flat }) {
  const { colors, fonts, fontSizes } = useTheme();
  const scrollRef = useRef(null);
  const [open, setOpen] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, []);
  const lines = toLines(text);
  const lastLine = lines[lines.length - 1] ?? '';
  return (
    <Trace flat={flat}>
      <Pressable
        onPress={() => setOpen((v) => !v)}
        hitSlop={8}
        style={{ flexDirection: 'row', alignItems: 'center', gap: space.s2 }}
        accessibilityLabel={open ? 'Collapse reasoning' : 'Expand reasoning'}
      >
        <View style={{ transform: [{ rotate: open ? '0deg' : '-90deg' }] }}>
          <Icon name="chevron-down" size={12} color={colors.ink3} />
        </View>
        <Text style={{ color: flat ? colors.ink3 : colors.ink4, fontFamily: fonts.mono, fontSize: flat ? fontSizes.sm : fontSizes.xs }}>
          {`thinking · ${elapsed}s`}
        </Text>
        {!open && lastLine ? (
          <Text
            numberOfLines={1}
            style={{ flex: 1, color: colors.ink4, fontFamily: fonts.mono, fontSize: flat ? fontSizes.sm : fontSizes.xs, opacity: 0.7 }}
          >
            {lastLine}
          </Text>
        ) : null}
      </Pressable>
      {open ? (
        <View style={{ marginTop: space.s3 }}>
          <ScrollView
            ref={scrollRef}
            style={{ maxHeight: STREAM_WINDOW_H }}
            scrollEnabled={false}
            showsVerticalScrollIndicator={false}
            onContentSizeChange={() => scrollRef.current?.scrollToEnd?.({ animated: false })}
          >
            <Lines text={text} size={fontSizes.xs} />
          </ScrollView>
          <Svg
            pointerEvents="none"
            height={STREAM_FADE_H}
            width="100%"
            style={{ position: 'absolute', top: 0, left: 0, right: 0 }}
          >
            <Defs>
              <LinearGradient id="thinkingFade" x1="0" y1="0" x2="0" y2="1">
                <Stop offset="0" stopColor={colors.bg} stopOpacity={1} />
                <Stop offset="1" stopColor={colors.bg} stopOpacity={0} />
              </LinearGradient>
            </Defs>
            <Rect x="0" y="0" width="100%" height="100%" fill="url(#thinkingFade)" />
          </Svg>
        </View>
      ) : null}
    </Trace>
  );
}

function Finished({ text, seconds, flat }) {
  const { colors, fonts, fontSizes } = useTheme();
  const { height } = useWindowDimensions();
  const [open, setOpen] = useState(false);
  const lines = toLines(text);
  const lastLine = lines[lines.length - 1] ?? '';
  const label = flat
    ? (seconds >= 1 ? `thinking · ${fmtDuration(seconds)}` : 'thinking')
    : thoughtLabel(seconds);
  return (
    <Trace flat={flat}>
      <Pressable
        onPress={() => setOpen((v) => !v)}
        hitSlop={8}
        style={{ flexDirection: 'row', alignItems: 'center', gap: space.s2 }}
        accessibilityLabel={open ? 'Collapse reasoning' : 'Expand reasoning'}
      >
        <View style={{ transform: [{ rotate: open ? '0deg' : '-90deg' }] }}>
          <Icon name="chevron-down" size={12} color={colors.ink3} />
        </View>
        <Text style={{ color: colors.ink3, fontFamily: fonts.mono, fontSize: fontSizes.sm }}>
          {label}
        </Text>
        {flat && !open && lastLine ? (
          <Text
            numberOfLines={1}
            style={{ flex: 1, color: colors.ink4, fontFamily: fonts.mono, fontSize: fontSizes.sm, opacity: 0.7 }}
          >
            {lastLine}
          </Text>
        ) : null}
      </Pressable>
      {open ? (
        <ScrollView
          style={{ marginTop: space.s3, maxHeight: height * 0.5 }}
          nestedScrollEnabled
        >
          <Lines text={text} size={fontSizes.sm} />
        </ScrollView>
      ) : null}
    </Trace>
  );
}
