import { mixHex } from "../../../../common/color.mjs";
import { formatCostLine } from "../../../../common/format.mjs";
import { useCallback } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { radii, space, typography } from '../../theme/tokens';

import { Diamond } from '../../components/Diamond';
import { RichText } from '../../components/RichText';
import { BUBBLE_MAX_PANE } from '../../lib/panes';
import { usePane } from '../../nav/PaneContext';
import { useTheme } from '../../theme/ThemeContext';
import { AttachmentCards } from './AttachmentCards';
import { useReduceMotion } from '../../lib/reduceMotion';
import { stripProducedImageMarkdown } from '../../../../common/producedAttachments.mjs';
import { longPressHaptic } from './chatHaptics';

const PRESS_SCALE = 0.98;

export function pressFeedback(pressed, reduceMotion) {
  if (!pressed) return null;
  return reduceMotion ? { opacity: 0.85 } : { transform: [{ scale: PRESS_SCALE }] };
}

function withTick(onLongPress) {
  if (!onLongPress) return undefined;
  return (e) => {
    longPressHaptic();
    onLongPress(e);
  };
}

function Stamp({ ts }) {
  const { colors, fonts, fontSizes } = useTheme();
  if (!ts) return null;
  return (
    <Text style={{ fontFamily: fonts.monoMedium, fontSize: fontSizes.sm, lineHeight: fontSizes.sm, color: colors.ink3 }}>{ts}</Text>
  );
}


const S = StyleSheet.create({
  userWrap: { alignItems: 'flex-end', paddingHorizontal: space.s7, gap: space.s1 },
  agentWrap: { paddingHorizontal: space.s7, gap: space.s1 },
  bubble: {
    maxWidth: '82%',
    paddingHorizontal: space.s7,
    paddingVertical: space.s5,
    borderTopLeftRadius: radii.bubble,
    borderTopRightRadius: radii.xs,
    borderBottomRightRadius: radii.bubble,
    borderBottomLeftRadius: radii.bubble,
  },
  wgBubble: {
    maxWidth: '90%',
    paddingHorizontal: space.s7,
    paddingVertical: space.s6,
  },
  speakerRow: { flexDirection: 'row', alignItems: 'center', gap: space.s2 },
  wgRowLeft: { alignItems: 'flex-start', paddingHorizontal: space.s7, gap: space.s1 },
  wgRowRight: { alignItems: 'flex-end', paddingHorizontal: space.s7, gap: space.s1 },
  paneCap: { maxWidth: BUBBLE_MAX_PANE },
});

export function ProfileUserMessage({ text, ts, accent, attachments, onLongPress, profile }) {
  const { colors, fontSizes } = useTheme();
  const { twoPane } = usePane();
  const reduceMotion = useReduceMotion();
  const bubbleStyle = useCallback(
    ({ pressed }) => [
      S.bubble,
      twoPane ? S.paneCap : null,
      { backgroundColor: mixHex(accent ?? colors.accent, 0.12, colors.bgPane) },
      pressFeedback(pressed, reduceMotion),
    ],
    [accent, colors.accent, colors.bgPane, twoPane, reduceMotion],
  );
  return (
    <View style={S.userWrap}>
      {attachments?.length ? (
        <AttachmentCards items={attachments} variant="message" profile={profile} />
      ) : null}
      {text ? (
        <Pressable onLongPress={withTick(onLongPress)} delayLongPress={350} style={bubbleStyle}>
          <RichText
            size={fontSizes[typography.chat.size]}
            color={colors.ink}
            imageProfile={profile}
          >
            {text}
          </RichText>
        </Pressable>
      ) : null}
      <Stamp ts={ts} />
    </View>
  );
}

export function ProfileAssistantMessage({ text, ts, attachments, onLongPress, profile }) {
  const { colors, fontSizes } = useTheme();
  const reduceMotion = useReduceMotion();
  const wrapStyle = useCallback(
    ({ pressed }) => [S.agentWrap, pressFeedback(pressed, reduceMotion)],
    [reduceMotion],
  );
  const body = stripProducedImageMarkdown(text, attachments);
  return (
    <Pressable onLongPress={withTick(onLongPress)} delayLongPress={350} style={wrapStyle}>
      {body ? (
        <RichText size={fontSizes[typography.chat.size]} color={colors.ink} imageProfile={profile}>
          {body}
        </RichText>
      ) : null}
      {attachments?.length ? (
        <AttachmentCards items={attachments} variant="message" profile={profile} />
      ) : null}
      <Stamp ts={ts} />
    </Pressable>
  );
}

export function WorkgroupMessage({ body, speakerName, speakerAccent, isFromHub, seq, cost, onLongPress, profile }) {
  const { colors, fonts, fontSizes } = useTheme();
  const { twoPane } = usePane();
  const bg = mixHex(speakerAccent ?? colors.ink3, 0.11, colors.bgPane);
  const right = isFromHub;

  const seqStr = seq != null ? `#${seq}` : null;
  const costStr = cost ? formatCostLine(cost) : null;

  const reduceMotion = useReduceMotion();
  const metaStyle = { fontFamily: fonts.monoMedium, fontSize: fontSizes.sm, lineHeight: fontSizes.sm, color: colors.ink3 };
  const SpeakerEl = (
    <View style={S.speakerRow}>
      {!isFromHub ? <Diamond color={speakerAccent} /> : null}
      <Text style={metaStyle}>{speakerName}</Text>
      {isFromHub ? <Diamond color={speakerAccent} /> : null}
    </View>
  );
  const SeqEl = seqStr ? <Text style={metaStyle}>{seqStr}</Text> : null;
  const CostEl = costStr ? <Text style={metaStyle}>{costStr}</Text> : null;

  const bubbleStyle = useCallback(
    ({ pressed }) => [
      S.wgBubble,
      twoPane ? S.paneCap : null,
      right
        ? { borderTopLeftRadius: radii.bubble, borderTopRightRadius: radii.xs, borderBottomRightRadius: radii.bubble, borderBottomLeftRadius: radii.bubble }
        : { borderTopLeftRadius: radii.xs, borderTopRightRadius: radii.bubble, borderBottomRightRadius: radii.bubble, borderBottomLeftRadius: radii.bubble },
      { backgroundColor: bg },
      pressFeedback(pressed, reduceMotion),
    ],
    [bg, right, twoPane, reduceMotion],
  );

  return (
    <View style={right ? S.wgRowRight : S.wgRowLeft}>
      <View style={S.speakerRow}>
        {right ? (
          <>
            {CostEl}
            {SeqEl}
            {SpeakerEl}
          </>
        ) : (
          <>
            {SpeakerEl}
            {SeqEl}
            {CostEl}
          </>
        )}
      </View>
      <Pressable onLongPress={withTick(onLongPress)} delayLongPress={350} style={bubbleStyle}>
        <RichText size={fontSizes[typography.chat.size]} color={colors.ink} imageProfile={profile}>
          {body}
        </RichText>
      </Pressable>
    </View>
  );
}
