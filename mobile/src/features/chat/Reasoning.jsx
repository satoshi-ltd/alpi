import { useEffect, useRef, useState } from 'react';
import { Pressable, ScrollView, Text, useWindowDimensions, View } from 'react-native';

import { Icon } from '../../components/Icon';
import { useTheme } from '../../theme/ThemeContext';
import { lineHeights, space } from '../../theme/tokens';
import { thoughtLabel } from './reasoningLabel';
import { ThinkingDots } from './ThinkingDots';

const STREAM_WINDOW_H = 116;

function toLines(text) {
  return String(text || '')
    .split('\n')
    .map((s) => s.replace(/\s+$/, ''))
    .filter((s) => s.trim());
}

export function Reasoning({ text, seconds, streaming = false }) {
  if (!String(text || '').trim()) return null;
  return streaming ? <Thinking text={text} /> : <Finished text={text} seconds={seconds} />;
}

function Trace({ children }) {
  const { colors } = useTheme();
  return (
    <View style={{ borderLeftWidth: 2, borderLeftColor: colors.line2, paddingLeft: space.s6 }}>
      {children}
    </View>
  );
}

function Lines({ text }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <>
      {toLines(text).map((line, i) => (
        <Text
          key={i}
          style={{
            color: colors.ink3,
            fontFamily: fonts.mono,
            fontSize: fontSizes.base,
            lineHeight: fontSizes.base * lineHeights.normal,
            marginTop: i === 0 ? 0 : space.s2,
          }}
        >
          {line}
        </Text>
      ))}
    </>
  );
}

function Thinking({ text }) {
  const { colors, fonts, fontSizes } = useTheme();
  const scrollRef = useRef(null);
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, []);
  return (
    <Trace>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s2, marginBottom: space.s3 }}>
        <ThinkingDots color={colors.ink3} padded={false} />
        <Text style={{ color: colors.ink4, fontFamily: fonts.mono, fontSize: fontSizes.xs }}>
          {`thinking · ${elapsed}s`}
        </Text>
      </View>
      <ScrollView
        ref={scrollRef}
        style={{ maxHeight: STREAM_WINDOW_H }}
        scrollEnabled={false}
        showsVerticalScrollIndicator={false}
        onContentSizeChange={() => scrollRef.current?.scrollToEnd?.({ animated: false })}
      >
        <Lines text={text} />
      </ScrollView>
    </Trace>
  );
}

function Finished({ text, seconds }) {
  const { colors, fonts, fontSizes } = useTheme();
  const { height } = useWindowDimensions();
  const [open, setOpen] = useState(false);
  return (
    <Trace>
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
          {thoughtLabel(seconds)}
        </Text>
      </Pressable>
      {open ? (
        <ScrollView
          style={{ marginTop: space.s3, maxHeight: height * 0.5 }}
          nestedScrollEnabled
        >
          <Lines text={text} />
        </ScrollView>
      ) : null}
    </Trace>
  );
}
