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
        borderTopWidth: 0.5,
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
          flexDirection: 'row',
          alignItems: 'flex-end',
          paddingHorizontal: PANE_PAD_X,
          paddingTop: COMPOSER_PAD_Y,
          paddingBottom: COMPOSER_PAD_Y + (keyboardUp ? 0 : insets.bottom),
          gap: space.s3,
          opacity: disabled ? 0.55 : 1,
        }}
      >
        {onPickAttachment ? (
          <Pressable
            onPress={disabled ? undefined : onPickAttachment}
            hitSlop={{
              top: tapSlop(COMPOSER_CTRL),
              bottom: tapSlop(COMPOSER_CTRL),
              left: tapSlop(CHROME_BTN),
              right: tapSlop(CHROME_BTN),
            }}
            accessibilityLabel="Attach file"
            style={({ pressed }) => ({
              width: CHROME_BTN,
              height: COMPOSER_CTRL,
              alignItems: 'center',
              justifyContent: 'center',
              opacity: pressed ? 0.5 : 1,
            })}
          >
            <Icon name="paperclip" size="md" color={colors.ink3} />
          </Pressable>
        ) : null}
        <View
          style={{
            flex: 1,
            minHeight: COMPOSER_CTRL,
            backgroundColor: colors.bgInput,
            borderRadius: radii["2xl"],
            flexDirection: 'row',
            alignItems: 'center',
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
            style={{
              flex: 1,
              fontFamily: fonts.sans.regular,
              fontSize: fontSizes.lg,
              lineHeight: fontSizes.lg * lineHeights.normal,
              color: colors.ink,
              maxHeight: 120,
              paddingHorizontal: space.s5,
              // iOS multiline TextInput adds ~2px top textContainerInset that ignores includeFontPadding.
              paddingTop: Platform.OS === 'ios' ? space.s1 : space.s2,
              paddingBottom: space.s2,
            }}
          />
        </View>
        <Pressable
          onPress={stoppable ? onStop : submit}
          disabled={!stoppable && !canSend}
          hitSlop={tapSlop(COMPOSER_CTRL)}
          style={({ pressed }) => ({
            width: COMPOSER_CTRL,
            height: COMPOSER_CTRL,
            borderRadius: radii['2xl'],
            backgroundColor: !stoppable && !canSend ? colors.ink3 : pressed ? colors.ink2 : actionBg,
            alignItems: 'center',
            justifyContent: 'center',
            opacity: stoppable || canSend ? 1 : 0.6,
          })}
          accessibilityLabel={stoppable ? 'Stop' : 'Send'}
        >
          <Icon name={stoppable ? 'square' : 'send'} size="lg" color="#ffffff" />
        </Pressable>
      </View>
    </View>
  );
}
