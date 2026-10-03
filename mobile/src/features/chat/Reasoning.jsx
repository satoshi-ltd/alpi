import { useEffect, useRef, useState } from 'react';
import { Pressable, ScrollView, Text, useWindowDimensions, View } from 'react-native';

import { Expand } from '../../components/Expand';
import { Icon } from '../../components/Icon';
import { Fold } from '../../components/Fold';
import { mixHex } from '../../../../common/color.mjs';
import { useTheme } from '../../theme/ThemeContext';
import { lineHeights, space } from '../../theme/tokens';
import { thoughtLabel } from '../../../../common/reasoningLabel.mjs';
import { PROCESS_GAP, PROCESS_INDENT, PROCESS_LEAD_W, processRowStyle, processSlop, processText } from './processRow';

function toLines(text) {
  return String(text || '')
    .split('\n')
    .map((s) => s.replace(/\s+$/, ''))
    .filter((s) => s.trim());
}

export function Reasoning({ text, seconds, timeline, streaming = false, answered = false, edges, accent, fold }) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (answered) setOpen(false);
  }, [answered]);
  if (!streaming && !String(text || '').trim() && !(seconds >= 1)) return null;
  const lines = toLines(text);
  const items = timeline?.length ? timeline : lines.length ? [{ kind: 'text', text }] : [];
  if (!streaming && !items.length) {
    return (
      <View style={processRowStyle} accessibilityLabel={thoughtLabel(seconds)}>
        <Mark fold={fold} accent={accent} />
        <Thought seconds={seconds} accent={accent} />
      </View>
    );
  }
  return (
    <View>
      <Pressable
        onPress={() => setOpen((v) => !v)}
        hitSlop={processSlop({ top: edges?.top, bottom: edges?.bottom && !(open && items.length) })}
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        accessibilityLiveRegion={streaming ? 'polite' : 'none'}
        style={processRowStyle}
      >
        <Mark fold={fold} accent={accent} working={streaming} />
        {streaming ? <Thinking hint={open ? '' : lines[lines.length - 1]} accent={accent} /> : <Thought seconds={seconds} accent={accent} />}
        <Chevron open={open} />
      </Pressable>
      <Expand open={open && items.length > 0}>
        <Body items={items} follow={streaming} />
      </Expand>
    </View>
  );
}

function Mark({ fold, accent, working = false }) {
  return (
    <View style={{ width: PROCESS_LEAD_W, alignItems: 'center' }}>
      <Fold fold={fold} color={accent} size={PROCESS_LEAD_W} pulse={working} />
    </View>
  );
}

function Chevron({ open }) {
  const { colors } = useTheme();
  return (
    <View style={{ marginLeft: 'auto', paddingLeft: space.s2, transform: [{ rotate: open ? '90deg' : '0deg' }] }}>
      <Icon name="chevron-right" size="xs" color={colors.ink3} />
    </View>
  );
}

function labelColor(colors, accent) {
  return /^#[0-9a-f]{6}$/i.test(accent ?? '') && /^#[0-9a-f]{6}$/i.test(colors.ink ?? '') ? mixHex(accent, 0.5, colors.ink) : colors.ink3;
}

function Thinking({ hint, accent }) {
  const theme = useTheme();
  return (
    <>
      <Text style={{ ...processText(theme, labelColor(theme.colors, accent)), fontFamily: theme.fonts.sans.medium }}>Thinking…</Text>
      {hint ? (
        <Text numberOfLines={1} style={{ ...processText(theme, theme.colors.ink3), fontFamily: theme.fonts.sans.regular, flex: 1, fontStyle: 'italic' }}>
          {hint}
        </Text>
      ) : null}
    </>
  );
}

function Thought({ seconds, accent }) {
  const theme = useTheme();
  return <Text style={{ ...processText(theme, labelColor(theme.colors, accent)), fontFamily: theme.fonts.sans.medium }}>{thoughtLabel(seconds)}</Text>;
}

function Body({ items, follow }) {
  const theme = useTheme();
  const { colors, fontSizes } = theme;
  const { height } = useWindowDimensions();
  const scrollRef = useRef(null);
  const lineHeight = fontSizes.sm * lineHeights.relaxed;
  const prose = { ...processText(theme, colors.ink2), lineHeight };
  const marker = { ...processText(theme, colors.ink3), lineHeight };
  return (
    <ScrollView
      ref={scrollRef}
      style={{
        maxHeight: height * 0.45,
        marginTop: PROCESS_GAP,
        marginLeft: PROCESS_LEAD_W / 2,
        borderLeftWidth: 1,
        borderLeftColor: colors.line,
      }}
      contentContainerStyle={{ paddingLeft: PROCESS_INDENT - PROCESS_LEAD_W / 2 - 1, paddingBottom: space.s1 }}
      nestedScrollEnabled
      onContentSizeChange={follow ? () => scrollRef.current?.scrollToEnd?.({ animated: false }) : undefined}
    >
      {items.flatMap((item, i) => (item.kind === 'tools'
        ? [<Text key={`t${i}`} selectable style={{ ...marker, marginTop: space.s1 }}>{`→ ${item.names.join(', ')}`}</Text>]
        : toLines(item.text).map((line, j) => (
          <Text key={`p${i}-${j}`} selectable style={{ ...prose, marginTop: i === 0 && j === 0 ? 0 : space.s1 }}>
            {line}
          </Text>
        ))))}
    </ScrollView>
  );
}
