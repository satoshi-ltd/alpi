import { useEffect, useRef, useState } from 'react';
import { Platform, Pressable, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { radii, space } from '../../theme/tokens';

import { Icon } from '../../components/Icon';
import { useTheme } from '../../theme/ThemeContext';
import { AttachmentCards } from './AttachmentCards';
import { MentionPopover } from './MentionPopover';
import { validateTaskShape } from './parseMarkers';

export function Composer({
  placeholder = 'Message…',
  accent,
  onSend,
  onMicPress,
  onMicLongPress,
  mentionSource,
  seedText,
  seedKey,
  attachments = [],
  onPickAttachment,
  onRemoveAttachment,
}) {
  const { colors, fonts , fontSizes} = useTheme();
  const insets = useSafeAreaInsets();
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
  const canSend = (hasText || hasAttachments) && taskShape.ok;

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
            paddingHorizontal: space.s7,
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
        <View style={{ paddingHorizontal: space.s7, paddingTop: space.s3 }}>
          <AttachmentCards items={attachments} onRemove={onRemoveAttachment} variant="composer" />
        </View>
      ) : null}
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'flex-end',
          paddingHorizontal: space.s5,
          paddingTop: space.s3,
          paddingBottom: Math.max(10, insets.bottom),
          gap: space.s3,
        }}
      >
        {onPickAttachment ? (
          <Pressable
            onPress={onPickAttachment}
            hitSlop={8}
            accessibilityLabel="Attach file"
            style={({ pressed }) => ({ width: 36, height: 44, alignItems: 'center', justifyContent: 'center', opacity: pressed ? 0.5 : 1 })}
          >
            <Icon name="paperclip" size={20} color={colors.ink3} />
          </Pressable>
        ) : null}
        <View
          style={{
            flex: 1,
            minHeight: 44,
            backgroundColor: colors.bgInput,
            borderRadius: radii["2xl"],
            flexDirection: 'row',
            alignItems: 'center',
          }}
        >
          <TextInput
            value={text}
            onChangeText={setText}
            placeholder={placeholder}
            placeholderTextColor={colors.ink3}
            multiline
            autoCapitalize="sentences"
            autoCorrect
            includeFontPadding={false}
            style={{
              flex: 1,
              fontFamily: fonts.sans.regular,
              fontSize: fontSizes.lg,
              lineHeight: 21,
              color: colors.ink,
              maxHeight: 120,
              paddingHorizontal: space.s7,
              // iOS multiline TextInput adds ~2px top textContainerInset that ignores includeFontPadding.
              paddingTop: Platform.OS === 'ios' ? 10 : 12,
              paddingBottom: space.s5,
            }}
          />
        </View>
        {hasText || hasAttachments ? (
          <Pressable
            onPress={submit}
            disabled={!canSend}
            style={({ pressed }) => ({
              width: 44,
              height: 44,
              borderRadius: radii["2xl"],
              backgroundColor: !canSend ? colors.ink3 : pressed ? colors.ink2 : actionBg,
              alignItems: 'center',
              justifyContent: 'center',
              opacity: canSend ? 1 : 0.6,
            })}
            accessibilityLabel="Send"
          >
            <Icon name="send" size={18} color="#ffffff" strokeWidth={2.2} />
          </Pressable>
        ) : (
          <Pressable
            onPress={onMicPress}
            onLongPress={onMicLongPress}
            delayLongPress={250}
            style={({ pressed }) => ({
              width: 44,
              height: 44,
              borderRadius: radii["2xl"],
              backgroundColor: pressed ? `${actionBg}cc` : actionBg,
              alignItems: 'center',
              justifyContent: 'center',
            })}
            accessibilityLabel="Voice message"
          >
            <Icon name="mic" size={18} color="#ffffff" strokeWidth={2.2} />
          </Pressable>
        )}
      </View>
    </View>
  );
}
