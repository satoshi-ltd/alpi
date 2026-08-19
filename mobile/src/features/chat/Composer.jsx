import { useEffect, useRef, useState } from 'react';
import { Platform, Pressable, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { lineHeights, radii, space } from '../../theme/tokens';

import { Icon } from '../../components/Icon';
import { CHROME_BTN, COMPOSER_CTRL, COMPOSER_PAD_Y, PANE_PAD_X, tapSlop } from '../../lib/panes';
import { useKeyboardVisible } from '../../lib/useKeyboardVisible';
import { useTheme } from '../../theme/ThemeContext';
import { AttachmentCards } from './AttachmentCards';
import { canComposerSend } from './composerSend';
import { MentionPopover } from './MentionPopover';
import { validateTaskShape } from './parseMarkers';

const HAIRLINE = 0.5;
const SEND_D = 30;

export function Composer({
  placeholder = 'Message…',
  accent,
  onSend,
  mentionSource,
  seedText,
  seedKey,
  attachments = [],
  onPickAttachment,
  onRemoveAttachment,
  disabled = false,
  busy = false,
  onStop,
}) {
  const { colors, fonts , fontSizes} = useTheme();
  const insets = useSafeAreaInsets();
  const keyboardUp = useKeyboardVisible();
  const [text, setText] = useState('');
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
    setText('');
    onSend?.(trimmed, attachments);
  };

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
              fontSize: fontSizes.xs,
              color: colors.warning,
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
      <View
        style={{
          paddingHorizontal: PANE_PAD_X,
          paddingTop: COMPOSER_PAD_Y,
          paddingBottom: keyboardUp ? COMPOSER_PAD_Y : Math.max(COMPOSER_PAD_Y, insets.bottom),
          opacity: disabled ? 0.55 : 1,
        }}
      >
        <View
          style={{
            backgroundColor: colors.bgElev,
            borderWidth: HAIRLINE,
            borderColor: focused ? colors.ink3 : colors.line2,
            borderRadius: radii['3xl'],
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
            placeholder={disabled ? 'Paused — resume to chat' : placeholder}
            placeholderTextColor={colors.ink3}
            multiline
            autoCapitalize="sentences"
            autoCorrect
            includeFontPadding={false}
            returnKeyType="send"
            submitBehavior="submit"
            onSubmitEditing={submit}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            style={{
              fontFamily: fonts.sans.regular,
              fontSize: fontSizes.lg,
              lineHeight: fontSizes.lg * lineHeights.normal,
              color: colors.ink,
              maxHeight: 120,
              padding: 0,
            }}
          />
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s3 }}>
            {mentionSource ? (
              <Pressable
                onPress={disabled ? undefined : () => setText((cur) => (cur.endsWith('@') ? cur : `${cur}${cur && !cur.endsWith(' ') ? ' ' : ''}@`))}
                hitSlop={space.s3}
                accessibilityLabel="Mention a peer"
                style={({ pressed }) => ({ flexDirection: 'row', alignItems: 'center', gap: space.s1, opacity: pressed ? 0.5 : 1 })}
              >
                <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>@</Text>
                <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.xs, color: colors.ink3 }}>mention</Text>
              </Pressable>
            ) : null}
            <View style={{ flex: 1 }} />
            {onPickAttachment ? (
              <Pressable
                onPress={disabled ? undefined : onPickAttachment}
                hitSlop={tapSlop(CHROME_BTN)}
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
              onPress={stoppable ? onStop : submit}
              disabled={!stoppable && !canSend}
              hitSlop={tapSlop(SEND_D)}
              style={({ pressed }) => ({
                width: SEND_D,
                height: SEND_D,
                borderRadius: radii.lg,
                backgroundColor: !stoppable && !canSend ? colors.line : pressed ? colors.ink2 : actionBg,
                alignItems: 'center',
                justifyContent: 'center',
              })}
              accessibilityLabel={stoppable ? 'Stop' : 'Send'}
            >
              <Icon
                name={stoppable ? 'square' : 'send'}
                size="sm"
                color={!stoppable && !canSend ? colors.ink3 : '#ffffff'}
              />
            </Pressable>
          </View>
        </View>
      </View>
    </View>
  );
}
