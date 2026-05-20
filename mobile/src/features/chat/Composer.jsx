import { useState } from 'react';
import { Platform, Pressable, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { radii, space , fontSizes} from '../../theme/tokens';

import { Icon } from '../../components/Icon';
import { useTheme } from '../../theme/ThemeContext';
import { MentionPopover } from './MentionPopover';

export function Composer({
  placeholder = 'Message…',
  accent,
  onSend,
  onMicPress,
  onMicLongPress,
  mentionSource,
}) {
  const { colors, fonts , fontSizes} = useTheme();
  const insets = useSafeAreaInsets();
  const [text, setText] = useState('');
  const hasText = text.trim().length > 0;

  const mentionMatch = mentionSource && text.length > 0
    ? /(^|\s)@([a-zA-Z0-9_-]*)$/.exec(text)
    : null;
  const candidates = mentionMatch ? mentionSource(mentionMatch[2]).slice(0, 4) : [];

  const completeMention = (id) => {
    const before = text.slice(0, mentionMatch.index + mentionMatch[1].length);
    setText(`${before}@${id} `);
  };

  const submit = () => {
    if (!hasText) return;
    const trimmed = text.trim();
    setText('');
    onSend?.(trimmed);
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
        {hasText ? (
          <Pressable
            onPress={submit}
            style={({ pressed }) => ({
              width: 44,
              height: 44,
              borderRadius: radii["2xl"],
              backgroundColor: pressed ? colors.ink2 : actionBg,
              alignItems: 'center',
              justifyContent: 'center',
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
