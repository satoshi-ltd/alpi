import { contrastText } from "../../../../common/color.mjs";
import { useEffect, useRef, useState } from 'react';
import { Pressable, Text, TextInput, View } from 'react-native';
import Animated, { useAnimatedKeyboard, useAnimatedStyle } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { lineHeights, radii, space, typography } from '../../theme/tokens';

import { Button } from '../../components/Button';
import { Icon } from '../../components/Icon';
import { COMPOSER_PAD_Y, PANE_PAD_X, tapSlop } from '../../lib/panes';
import { useTheme } from '../../theme/ThemeContext';
import { AttachmentCards } from './AttachmentCards';
import { sendHaptic } from './chatHaptics';
import { canComposerSend } from './composerSend';
import { MentionPopover } from './MentionPopover';
import { validateTaskShape } from './parseMarkers';
import { wellStyle } from '../../components/well';

const HAIRLINE = 0.5;
const CTRL_H = 36;
const DIMMED = 0.45;

function ComposerChip({ onPress, disabled, accessibilityLabel, grow = false, children }) {
  const { colors } = useTheme();
  return (
    <Pressable
      onPress={disabled ? undefined : onPress}
      hitSlop={tapSlop(CTRL_H)}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      accessibilityState={{ disabled: !!disabled }}
      style={({ pressed }) => ({
        flexShrink: grow ? 1 : 0,
        minWidth: 0,
        flexDirection: 'row',
        alignItems: 'center',
        gap: space.s2,
        minHeight: CTRL_H,
        paddingHorizontal: space.s5,
        borderRadius: radii.xs,
        backgroundColor: pressed ? colors.line2 : colors.selected,
        opacity: disabled ? DIMMED : 1,
      })}
    >
      {children}
    </Pressable>
  );
}

function ModelChip({ label, model, effort, onPress, disabled }) {
  const { colors, fonts, fontSizes } = useTheme();
  const text = { fontFamily: fonts.sans.regular, fontSize: fontSizes.md, color: colors.ink2 };
  const split = model != null;
  return (
    <ComposerChip grow onPress={onPress} disabled={disabled} accessibilityLabel={`Model and effort: ${label}`}>
      <Icon name="sparkle" size="xs" color={colors.ink3} />
      {split ? (
        <>
          <Text numberOfLines={1} style={{ ...text, flexShrink: 1 }}>{model}</Text>
          {effort ? <Text numberOfLines={1} style={{ ...text, flexShrink: 0 }}>{` · ${effort}`}</Text> : null}
        </>
      ) : (
        <Text numberOfLines={1} style={{ ...text, flexShrink: 1 }}>{label}</Text>
      )}
      <Icon name="chevron-down" size="xs" color={colors.ink3} />
    </ComposerChip>
  );
}

function MentionChip({ onPress, disabled }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <ComposerChip onPress={onPress} disabled={disabled} accessibilityLabel="Mention a peer">
      <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.md, color: colors.ink3 }}>@</Text>
      <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.md, color: colors.ink2 }}>mention</Text>
    </ComposerChip>
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
  onResume = null,
  resumeLabel = 'Resume profile',
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
  const candidates = mentionMatch ? mentionSource(mentionMatch[2]) : [];

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
      {mentionMatch ? <MentionPopover candidates={candidates} token={mentionMatch[2]} onPick={(c) => completeMention(c.id)} /> : null}
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
          },
          rideKeyboard,
        ]}
      >
        <View
          style={{
            ...wellStyle(colors, { focused }),
            ...(disabled ? { borderColor: colors.edge } : null),
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
            placeholderTextColor={disabled ? colors.ink2 : colors.ink3}
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
              <MentionChip
                disabled={disabled}
                onPress={() => setText((cur) => (cur.endsWith('@') ? cur : `${cur}${cur && !cur.endsWith(' ') ? ' ' : ''}@`))}
              />
            ) : null}
            {modelChip ? <ModelChip label={modelChip.label} model={modelChip.model} effort={modelChip.effort} onPress={modelChip.onPress} disabled={disabled} /> : null}
            <View style={{ flex: 1 }} />
            {onPickAttachment ? (
              <Pressable
                onPress={disabled ? undefined : onPickAttachment}
                hitSlop={tapSlop(CTRL_H)}
                accessibilityRole="button"
                accessibilityLabel="Attach file"
                accessibilityState={{ disabled }}
                style={({ pressed }) => ({
                  minWidth: CTRL_H,
                  minHeight: CTRL_H,
                  alignItems: 'center',
                  justifyContent: 'center',
                  opacity: disabled ? DIMMED : pressed ? 0.5 : 1,
                })}
              >
                <Icon name="paperclip" size="lg" color={colors.ink3} />
              </Pressable>
            ) : null}
            <Pressable
              onPress={stoppable ? stop : submit}
              disabled={!stoppable && !canSend}
              hitSlop={tapSlop(CTRL_H)}
              style={({ pressed }) => ({
                minWidth: CTRL_H,
                minHeight: CTRL_H,
                borderRadius: radii.xs,
                backgroundColor: !stoppable && !canSend ? colors.line : actionBg,
                opacity: disabled ? DIMMED : pressed ? 0.85 : 1,
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
        {disabled && !offline && onResume ? (
          <View style={{ alignItems: 'flex-end', paddingTop: space.s3 }}>
            <Button title={resumeLabel} variant="secondary" onPress={onResume} />
          </View>
        ) : null}
      </Animated.View>
    </View>
  );
}
