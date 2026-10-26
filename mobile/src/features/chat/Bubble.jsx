import { mixHex } from "../../../../common/color.mjs";
import { formatCostLine } from "../../../../common/format.mjs";
import { useMemo } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import Animated, { useAnimatedStyle, useSharedValue, withSequence, withTiming } from 'react-native-reanimated';
import { mobile, radii, space, typography } from '../../theme/tokens';

import { Fold } from '../../components/Fold';
import { Icon } from '../../components/Icon';
import { RichText } from '../../components/RichText';
import { BUBBLE_MAX_PANE } from '../../lib/panes';
import { usePane } from '../../nav/PaneContext';
import { useTheme } from '../../theme/ThemeContext';
import { AttachmentCards } from './AttachmentCards';
import { useReduceMotion } from '../../lib/reduceMotion';
import { stripProducedImageMarkdown } from '../../../../common/producedAttachments.mjs';
import { longPressHaptic } from './chatHaptics';

export const LONG_PRESS_MS = 350;
export const PULSE_FROM = 0.985;
export const PULSE_MS = 160;

const AnimatedPressable = Animated.createAnimatedComponent(Pressable);

function useLongPressPulse(onLongPress) {
  const reduceMotion = useReduceMotion();
  const scale = useSharedValue(1);
  const pulse = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));
  const handle = onLongPress
    ? (e) => {
      longPressHaptic();
      if (!reduceMotion) scale.value = withSequence(withTiming(PULSE_FROM, { duration: 0 }), withTiming(1, { duration: PULSE_MS }));
      onLongPress(e);
    }
    : undefined;
  return { onLongPress: handle, pulse: reduceMotion ? null : pulse };
}

export const MESSAGE_ACTIONS_NAME = 'message-actions';
const ACCESSIBILITY_ACTIONS = [{ name: MESSAGE_ACTIONS_NAME, label: 'Message actions' }];

function MessagePress({ onLongPress, style, children }) {
  const press = useLongPressPulse(onLongPress);
  return (
    <AnimatedPressable
      onLongPress={press.onLongPress}
      delayLongPress={LONG_PRESS_MS}
      accessibilityActions={onLongPress ? ACCESSIBILITY_ACTIONS : undefined}
      onAccessibilityAction={onLongPress ? (e) => { if (e.nativeEvent.actionName === MESSAGE_ACTIONS_NAME) onLongPress(e); } : undefined}
      style={[style, press.pulse]}
    >
      {children}
    </AnimatedPressable>
  );
}

function MoreButton({ onPress }) {
  const { colors } = useTheme();
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel="Message actions"
      style={{ minWidth: mobile.tap, minHeight: mobile.tap, alignItems: 'center', justifyContent: 'center' }}
    >
      <Icon name="more" size="lg" color={colors.ink3} />
    </Pressable>
  );
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
    borderTopLeftRadius: radii.xs,
    borderTopRightRadius: radii.xs,
    borderBottomRightRadius: radii.xs,
    borderBottomLeftRadius: radii.xs,
  },
  wgBubble: {
    maxWidth: '90%',
    paddingHorizontal: space.s7,
    paddingVertical: space.s6,
  },
  stampRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  speakerRow: { flexDirection: 'row', alignItems: 'center', gap: space.s2 },
  wgRowLeft: { alignItems: 'flex-start', paddingHorizontal: space.s7, gap: space.s1 },
  wgRowRight: { alignItems: 'flex-end', paddingHorizontal: space.s7, gap: space.s1 },
  paneCap: { maxWidth: BUBBLE_MAX_PANE },
});

export function ProfileUserMessage({ text, ts, attachments, onLongPress, profile }) {
  const { colors, fontSizes } = useTheme();
  const { twoPane } = usePane();
  const bubbleStyle = useMemo(
    () => [
      S.bubble,
      twoPane ? S.paneCap : null,
      { backgroundColor: colors.selected },
    ],
    [colors.selected, twoPane],
  );
  return (
    <View style={S.userWrap}>
      {attachments?.length ? (
        <AttachmentCards items={attachments} variant="message" profile={profile} />
      ) : null}
      {text ? (
        <MessagePress onLongPress={onLongPress} style={bubbleStyle}>
          <RichText
            size={fontSizes[typography.chat.size]}
            color={colors.ink}
            imageProfile={profile}
          >
            {text}
          </RichText>
        </MessagePress>
      ) : null}
      <Stamp ts={ts} />
    </View>
  );
}

export function ProfileAssistantMessage({ text, ts, attachments, onLongPress, onMore, profile, accent = null }) {
  const { colors, fontSizes } = useTheme();
  const body = stripProducedImageMarkdown(text, attachments);
  return (
    <MessagePress onLongPress={onLongPress} style={S.agentWrap}>
      {body ? (
        <RichText size={fontSizes[typography.chat.size]} color={colors.ink} imageProfile={profile} accent={accent}>
          {body}
        </RichText>
      ) : null}
      {attachments?.length ? (
        <AttachmentCards items={attachments} variant="message" profile={profile} />
      ) : null}
      {onMore ? (
        <View style={S.stampRow}>
          <Stamp ts={ts} />
          <MoreButton onPress={onMore} />
        </View>
      ) : (
        <Stamp ts={ts} />
      )}
    </MessagePress>
  );
}

export function WorkgroupMessage({ body, speakerName, speakerAccent, speakerFold, isFromHub, seq, cost, onLongPress, profile }) {
  const { colors, fonts, fontSizes } = useTheme();
  const { twoPane } = usePane();
  const bg = mixHex(speakerAccent ?? colors.ink3, 0.11, colors.bgPane);
  const right = isFromHub;

  const seqStr = seq != null ? `#${seq}` : null;
  const costStr = cost ? formatCostLine(cost) : null;

  const metaStyle = { fontFamily: fonts.monoMedium, fontSize: fontSizes.sm, lineHeight: fontSizes.sm, color: colors.ink3 };
  const SpeakerEl = (
    <View style={S.speakerRow}>
      {!isFromHub ? <Fold fold={speakerFold} color={speakerAccent} /> : null}
      <Text style={metaStyle}>{speakerName}</Text>
      {isFromHub ? <Fold fold={speakerFold} color={speakerAccent} /> : null}
    </View>
  );
  const SeqEl = seqStr ? <Text style={metaStyle}>{seqStr}</Text> : null;
  const CostEl = costStr ? <Text style={metaStyle}>{costStr}</Text> : null;

  const bubbleStyle = useMemo(
    () => [
      S.wgBubble,
      twoPane ? S.paneCap : null,
      { borderRadius: radii.xs },
      { backgroundColor: bg },
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
      <MessagePress onLongPress={onLongPress} style={bubbleStyle}>
        <RichText size={fontSizes[typography.chat.size]} color={colors.ink} imageProfile={profile} accent={speakerAccent}>
          {body}
        </RichText>
      </MessagePress>
    </View>
  );
}
