import { contrastText } from "../../../../common/color.mjs";
import { useEffect, useRef, useState } from 'react';
import { Pressable, Text, TextInput, View } from 'react-native';
import Animated, { useAnimatedKeyboard, useAnimatedStyle } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { lineHeights, radii, space, typography } from '../../theme/tokens';

import { Icon } from '../../components/Icon';
import { CHROME_BTN, COMPOSER_CTRL, COMPOSER_PAD_Y, PANE_PAD_X, tapSlop } from '../../lib/panes';
import { useTheme } from '../../theme/ThemeContext';
import { AttachmentCards } from './AttachmentCards';
import { sendHaptic } from './chatHaptics';
import { canComposerSend } from './composerSend';
import { MentionPopover } from './MentionPopover';
import { validateTaskShape } from './parseMarkers';
import { wellStyle } from '../../components/well';

const HAIRLINE = 0.5;
const SEND_D = 30;
const CHIP_H = 32;

function ModelChip({ label, onPress, disabled }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <Pressable
      onPress={disabled ? undefined : onPress}
      hitSlop={tapSlop(CHIP_H)}
      accessibilityRole="button"
      accessibilityLabel={`Model and effort: ${label}`}
      style={({ pressed }) => ({
        flexShrink: 1,
        minWidth: 0,
        flexDirection: 'row',
        alignItems: 'center',
        gap: space.s2,
        height: CHIP_H,
        paddingHorizontal: space.s5,
        borderRadius: radii.tag,
        backgroundColor: pressed ? colors.line2 : colors.selected,
      })}
    >
      <Icon name="sparkle" size="xs" color={colors.ink3} />
      <Text numberOfLines={1} style={{ flexShrink: 1, fontFamily: fonts.sans.regular, fontSize: fontSizes.md, color: colors.ink2 }}>
        {label}
      </Text>
      <Icon name="chevron-down" size="xs" color={colors.ink3} />
    </Pressable>
  );
}

export function composerPlaceholder({ offline = false, disabled = false, placeholder }) {
  if (offline) return 'Daemon unreachable — sending paused';
  if (disabled) return 'Paused — resume to chat';
  return placeholder;
}

export function Composer({
  placeholder = 'Message…',
  accent,
  onSend,
  mentionSource,
  seedText,
  seedKey,
  initialText = '',
  attachments = [],
  onPickAttachment,
  onRemoveAttachment,
  disabled = false,
  busy = false,
  onStop,
  offline = false,
  modelChip = null,
}) {
  const { colors, fonts , fontSizes} = useTheme();
  const insets = useSafeAreaInsets();
  const keyboard = useAnimatedKeyboard();
  const bottomInset = insets.bottom;
  const rideKeyboard = useAnimatedStyle(() => ({
    paddingBottom: Math.max(COMPOSER_PAD_Y, bottomInset - keyboard.height.value),
  }));
  const [text, setText] = useState(initialText);
  const [focused, setFocused] = useState(false);
  const lastSeedKeyRef = useRef(seedKey);
  useEffect(() => {
    if (seedKey != null && seedKey !== lastSeedKeyRef.current) {
      setText(seedText ?? '');
      lastSeedKeyRef.current = seedKey;
    }
  }, [seedKey, seedText]);
  const hasText = text.trim().length > 0;
  const taskShape = validateTaskShape(text);
  const hasAttachments = attachments.length > 0;
  const canSend = canComposerSend({ hasText, hasAttachments, taskOk: taskShape.ok, disabled, busy });
  const stoppable = busy && !!onStop;

  const mentionMatch = mentionSource && text.length > 0
    ? /(^|\s)@([a-zA-Z0-9_-]*)$/.exec(text)
    : null;
  const candidates = mentionMatch ? mentionSource(mentionMatch[2]).slice(0, 4) : [];

  const completeMention = (id) => {
    const before = text.slice(0, mentionMatch.index + mentionMatch[1].length);
    setText(`${before}@${id} `);
  };

  const submit = () => {
    if (!canSend) return;
    const trimmed = text.trim();
    sendHaptic();
    setText('');
    onSend?.(trimmed, attachments);
  };
  const stop = () => {
    sendHaptic();
    onStop?.();
  };
  const chatSize = fontSizes[typography.chat.size];

  const actionBg = accent ?? colors.ink;

  return (
    <View
      style={{
        backgroundColor: colors.bgPane,
        borderTopWidth: HAIRLINE,
        borderTopColor: colors.line,
      }}
    >
      {candidates.length ? <MentionPopover candidates={candidates} onPick={(c) => completeMention(c.id)} /> : null}
      {hasText && !taskShape.ok ? (
        <View
          style={{
            paddingHorizontal: PANE_PAD_X,
            paddingTop: space.s2,
            paddingBottom: space.s2,
          }}
        >
          <Text
            style={{
              fontFamily: fonts.sans.regular,
              fontSize: fontSizes.sm,
              color: colors.warningText,
            }}
          >
            {taskShape.error}
          </Text>
        </View>
      ) : null}
      {hasAttachments ? (
        <View style={{ paddingHorizontal: PANE_PAD_X, paddingTop: space.s3 }}>
          <AttachmentCards items={attachments} onRemove={onRemoveAttachment} variant="composer" />
        </View>
      ) : null}
      <Animated.View
        style={[
          {
            paddingHorizontal: PANE_PAD_X,
            paddingTop: COMPOSER_PAD_Y,
            paddingBottom: Math.max(COMPOSER_PAD_Y, insets.bottom),
            opacity: disabled ? 0.55 : 1,
          },
          rideKeyboard,
        ]}
      >
        <View
          style={{
            ...wellStyle(colors, { focused }),
            paddingTop: space.s6,
            paddingHorizontal: space.s7,
            paddingBottom: space.s4,
            gap: space.s3,
          }}
        >
          <TextInput
            value={text}
            onChangeText={setText}
            editable={!disabled}
            placeholder={composerPlaceholder({ offline, disabled, placeholder })}
            placeholderTextColor={colors.ink3}
            multiline
            autoCapitalize="sentences"
            autoCorrect
            includeFontPadding={false}
            submitBehavior="newline"
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            style={{
              fontFamily: fonts.sans.regular,
              fontSize: chatSize,
              lineHeight: chatSize * lineHeights.normal,
              color: colors.ink,
              maxHeight: 120,
              padding: 0,
            }}
          />
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s3 }}>
            {mentionSource ? (
              <Pressable
                onPress={disabled ? undefined : () => setText((cur) => (cur.endsWith('@') ? cur : `${cur}${cur && !cur.endsWith(' ') ? ' ' : ''}@`))}
                hitSlop={{ top: 13, bottom: 13, left: space.s3, right: space.s3 }}
                accessibilityRole="button"
                accessibilityLabel="Mention a peer"
                style={({ pressed }) => ({ flexDirection: 'row', alignItems: 'center', gap: space.s1, opacity: pressed ? 0.5 : 1 })}
              >
                <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.ink3 }}>@</Text>
                <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink3 }}>mention</Text>
              </Pressable>
            ) : null}
            {modelChip ? <ModelChip label={modelChip.label} onPress={modelChip.onPress} disabled={disabled} /> : null}
            <View style={{ flex: 1 }} />
            {onPickAttachment ? (
              <Pressable
                onPress={disabled ? undefined : onPickAttachment}
                hitSlop={{ left: tapSlop(CHROME_BTN), right: tapSlop(CHROME_BTN), top: tapSlop(SEND_D), bottom: tapSlop(SEND_D) }}
                accessibilityRole="button"
                accessibilityLabel="Attach file"
                style={({ pressed }) => ({
                  width: CHROME_BTN,
                  height: SEND_D,
                  alignItems: 'center',
                  justifyContent: 'center',
                  opacity: pressed ? 0.5 : 1,
                })}
              >
                <Icon name="paperclip" size="lg" color={colors.ink3} />
              </Pressable>
            ) : null}
            <Pressable
              onPress={stoppable ? stop : submit}
              disabled={!stoppable && !canSend}
              hitSlop={tapSlop(SEND_D)}
              style={({ pressed }) => ({
                width: SEND_D,
                height: SEND_D,
                borderRadius: radii.xs,
                backgroundColor: !stoppable && !canSend ? colors.line : actionBg,
                opacity: pressed ? 0.85 : 1,
                alignItems: 'center',
                justifyContent: 'center',
              })}
              accessibilityRole="button"
              accessibilityLabel={stoppable ? 'Stop' : 'Send'}
            >
              <Icon
                name={stoppable ? 'square' : 'send'}
                size="sm"
                color={!stoppable && !canSend ? colors.ink3 : contrastText(actionBg)}
              />
            </Pressable>
          </View>
        </View>
      </Animated.View>
    </View>
  );
}
