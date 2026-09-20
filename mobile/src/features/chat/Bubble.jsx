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
import { stripProducedImageMarkdown } from '../../../../common/producedAttachments.mjs';


const S = StyleSheet.create({
  userWrap: { alignItems: 'flex-end', paddingHorizontal: space.s7, gap: space.s1 },
  agentWrap: { paddingHorizontal: space.s7 },
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
  const { colors, fonts, fontSizes } = useTheme();
  const { twoPane } = usePane();
  const bubbleStyle = useCallback(
    ({ pressed }) => [
      S.bubble,
      twoPane ? S.paneCap : null,
      { backgroundColor: mixHex(accent ?? colors.accent, 0.12, colors.bgPane), opacity: pressed ? 0.85 : 1 },
    ],
    [accent, colors.accent, colors.bgPane, twoPane],
  );
  return (
    <View style={S.userWrap}>
      {attachments?.length ? (
        <AttachmentCards items={attachments} variant="message" profile={profile} />
      ) : null}
      {text ? (
        <Pressable onLongPress={onLongPress} delayLongPress={350} style={bubbleStyle}>
          <RichText
            size={fontSizes[typography.chat.size]}
            color={colors.ink}
            imageProfile={profile}
          >
            {text}
          </RichText>
        </Pressable>
      ) : null}
      {ts ? (
        <Text style={[S.meta, { fontFamily: fonts.monoMedium, fontSize: fontSizes.xs, lineHeight: fontSizes.xs, color: colors.ink3 }]}>{ts}</Text>
      ) : null}
    </View>
  );
}

export function ProfileAssistantMessage({ text, attachments, onLongPress, profile }) {
  const { colors, fontSizes } = useTheme();
  const wrapStyle = useCallback(
    ({ pressed }) => [S.agentWrap, pressed && { opacity: 0.85 }],
    [],
  );
  const body = stripProducedImageMarkdown(text, attachments);
  return (
    <Pressable onLongPress={onLongPress} delayLongPress={350} style={wrapStyle}>
      {body ? (
        <RichText size={fontSizes[typography.chat.size]} color={colors.ink} imageProfile={profile}>
          {body}
        </RichText>
      ) : null}
      {attachments?.length ? (
        <AttachmentCards items={attachments} variant="message" profile={profile} />
      ) : null}
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

  const metaStyle = [S.meta, { fontFamily: fonts.monoMedium, fontSize: fontSizes.xs, lineHeight: fontSizes.xs, color: colors.ink3 }];
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
      { backgroundColor: bg, opacity: pressed ? 0.85 : 1 },
    ],
    [bg, right, twoPane],
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
      <Pressable onLongPress={onLongPress} delayLongPress={350} style={bubbleStyle}>
        <RichText size={fontSizes[typography.chat.size]} color={colors.ink} imageProfile={profile}>
          {body}
        </RichText>
      </Pressable>
    </View>
  );
}
