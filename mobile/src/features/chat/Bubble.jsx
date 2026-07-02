import { useCallback } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { fontSizes, radii, space } from '../../theme/tokens';

import { Diamond } from '../../components/Diamond';
import { RichText } from '../../components/RichText';
import { useTheme } from '../../theme/ThemeContext';
import { AttachmentCards } from './AttachmentCards';
import { stripProducedImageMarkdown } from '../../lib/producedAttachments';

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

const S = StyleSheet.create({
  userWrap: { alignItems: 'flex-end', paddingHorizontal: space.s7, gap: space.s1 },
  agentWrap: { paddingHorizontal: space.s7 },
  bubble: {
    maxWidth: '82%',
    paddingHorizontal: space.s6,
    paddingVertical: space.s5,
    borderTopLeftRadius: 18,
    borderTopRightRadius: radii.xs,
    borderBottomRightRadius: 18,
    borderBottomLeftRadius: 18,
  },
  bubbleText: { fontSize: fontSizes.lg, lineHeight: fontSizes.lg * 1.45 },
  wgBubble: {
    maxWidth: '90%',
    paddingHorizontal: space.s7,
    paddingVertical: space.s6,
  },
  meta: { fontSize: fontSizes.xs, lineHeight: fontSizes.xs },
  speakerRow: { flexDirection: 'row', alignItems: 'center', gap: space.s2 },
  wgRowLeft: { alignItems: 'flex-start', paddingHorizontal: space.s7, gap: space.s1 },
  wgRowRight: { alignItems: 'flex-end', paddingHorizontal: space.s7, gap: space.s1 },
});

export function ProfileUserMessage({ text, ts, accent, attachments, onLongPress, profile }) {
  const { colors, fonts } = useTheme();
  const bubbleStyle = useCallback(
    ({ pressed }) => [
      S.bubble,
      { backgroundColor: accent ?? colors.ink, opacity: pressed ? 0.85 : 1 },
    ],
    [accent, colors.ink],
  );
  return (
    <View style={S.userWrap}>
      {attachments?.length ? (
        <AttachmentCards items={attachments} variant="message" profile={profile} />
      ) : null}
      {text ? (
        <Pressable onLongPress={onLongPress} delayLongPress={350} style={bubbleStyle}>
          <Text style={[S.bubbleText, { fontFamily: fonts.sans.regular, color: '#ffffff' }]}>
            {text}
          </Text>
        </Pressable>
      ) : null}
      {ts ? (
        <Text style={[S.meta, { fontFamily: fonts.monoMedium, color: colors.ink3 }]}>{ts}</Text>
      ) : null}
    </View>
  );
}

export function ProfileAssistantMessage({ text, attachments, onLongPress, profile }) {
  const { colors } = useTheme();
  const wrapStyle = useCallback(
    ({ pressed }) => [S.agentWrap, pressed && { opacity: 0.85 }],
    [],
  );
  const body = stripProducedImageMarkdown(text, attachments);
  return (
    <Pressable onLongPress={onLongPress} delayLongPress={350} style={wrapStyle}>
      {body ? (
        <RichText size={16} color={colors.ink} imageProfile={profile}>
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
  const { colors, fonts } = useTheme();
  const bg = mixHex(speakerAccent ?? colors.ink3, 0.11, colors.bgPane);
  const right = isFromHub;

  const seqStr = seq != null ? `#${seq}` : null;
  let costStr = null;
  if (cost) {
    const tok = typeof cost.tokens === 'number' ? cost.tokens : 0;
    const usd = typeof cost.usd === 'number' ? cost.usd : 0;
    const tokFmt = tok >= 1000 ? `${(tok / 1000).toFixed(1)}K` : `${tok}`;
    const usdFmt = usd >= 0.01 ? `$${usd.toFixed(2)}` : `$${usd.toFixed(4)}`;
    costStr = `${tokFmt} · ${usdFmt}`;
  }

  const metaStyle = [S.meta, { fontFamily: fonts.monoMedium, color: colors.ink3 }];
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
      right
        ? { borderTopLeftRadius: 18, borderTopRightRadius: radii.xs, borderBottomRightRadius: 18, borderBottomLeftRadius: 18 }
        : { borderTopLeftRadius: radii.xs, borderTopRightRadius: 18, borderBottomRightRadius: 18, borderBottomLeftRadius: 18 },
      { backgroundColor: bg, opacity: pressed ? 0.85 : 1 },
    ],
    [bg, right],
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
        <RichText size={fontSizes.md} color={colors.ink} imageProfile={profile}>
          {body}
        </RichText>
      </Pressable>
    </View>
  );
}
