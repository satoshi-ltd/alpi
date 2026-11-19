import { contrastText } from "../../../../common/color.mjs";
import { useEffect, useRef, useState } from 'react';
import { Modal, Pressable, Text, TextInput, useWindowDimensions, View } from 'react-native';
import Animated, { useAnimatedStyle } from 'react-native-reanimated';
import { useKeyboardInset } from '../../hooks/useKeyboardInset';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { alpha, iconSizes, mobile, radii, space, typeLeading, typography } from '../../theme/tokens';

import { Icon } from '../../components/Icon';
import { COMPOSER_PAD_Y, PANE_PAD_X, tapSlop } from '../../lib/panes';
import { useTheme } from '../../theme/ThemeContext';
import { AttachmentCards } from './AttachmentCards';
import { sendHaptic } from './chatHaptics';
import { canComposerSend } from './composerSend';
import { MentionPopover } from './MentionPopover';
import { validateTaskShape } from './parseMarkers';
import { EdgeFade } from '../../components/EdgeFade';
import { focusRingStyle, useFocusRing } from '../../components/focusRing';

export const COMPOSER_H = 56;
export const COMPOSER_BTN = 40;
export const STREAM_FADE = 28;
const DIMMED = alpha.disabled;

function RoundButton({ label, onPress, disabled, dimmed = disabled, fill, children }) {
  const { colors } = useTheme();
  const [focused, focusHandlers] = useFocusRing();
  return (
    <Pressable
      onPress={disabled ? undefined : onPress}
      disabled={!!disabled && !onPress}
      hitSlop={tapSlop(COMPOSER_BTN)}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: !!disabled }}
      {...focusHandlers}
      style={({ pressed }) => ({
        width: COMPOSER_BTN,
        height: COMPOSER_BTN,
        borderRadius: radii.pill,
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: fill ?? (pressed ? colors.pressed : 'transparent'),
        opacity: dimmed ? DIMMED : 1,
        ...focusRingStyle(colors, focused),
      })}
    >
      {children}
    </Pressable>
  );
}

function ComposerMenu({ actions, onClose, anchor }) {
  const { colors, fonts, fontSizes, shadow } = useTheme();
  const { height } = useWindowDimensions();
  const top = anchor?.y ?? height - COMPOSER_H;
  return (
    <Modal visible transparent animationType="none" onRequestClose={onClose} supportedOrientations={['portrait', 'landscape-left', 'landscape-right']}>
    <Pressable testID="composer-menu-backdrop" accessible={false} onPress={onClose} style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }} />
    <View
      testID="composer-menu"
      accessibilityRole="menu"
      style={{
        position: 'absolute',
        left: (anchor?.x ?? 0) + PANE_PAD_X,
        bottom: height - top + space.s2,
        minWidth: 240,
        padding: space.s3,
        borderRadius: radii.surface,
        backgroundColor: colors.raised,
        ...shadow?.popover,
      }}
    >
      {actions.map((a) => (
        <Pressable
          key={a.id}
          accessibilityRole="menuitem"
          accessibilityLabel={a.detail ? `${a.label}: ${a.detail}` : a.label}
          onPress={() => {
            onClose();
            a.onPress?.();
          }}
          style={({ pressed }) => ({
            flexDirection: 'row',
            alignItems: 'center',
            gap: space.s4,
            minHeight: mobile.btnH,
            paddingHorizontal: space.s4,
            borderRadius: radii.control,
            backgroundColor: pressed ? colors.pressed : 'transparent',
          })}
        >
          {a.icon ?? <View style={{ width: iconSizes.md }} />}
          <Text style={{ flex: 1, fontFamily: fonts.sans.regular, fontSize: fontSizes.md, color: colors.ink }}>{a.label}</Text>
          {a.detail ? <Text numberOfLines={1} style={{ flexShrink: 1, fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink3 }}>{a.detail}</Text> : null}
        </Pressable>
      ))}
    </View>
    </Modal>
  );
}

export function composerMenuActions({ onPickAttachment, onMention, modelChip }) {
  const out = [];
  if (onPickAttachment) out.push({ id: 'attach', label: 'Attach file', icon: <Icon name="paperclip" size="md" />, onPress: onPickAttachment });
  if (onMention) out.push({ id: 'mention', label: 'Mention a peer', onPress: onMention });
  if (modelChip) out.push({ id: 'model', label: 'Model and effort', detail: modelChip.label, icon: <Icon name="sparkle" size="md" />, onPress: modelChip.onPress });
  return out;
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
  const keyboard = useKeyboardInset();
  const bottomInset = insets.bottom;
  const rideKeyboard = useAnimatedStyle(() => ({
    paddingBottom: Math.max(COMPOSER_PAD_Y, bottomInset - keyboard.value),
  }));
  const [text, setText] = useState(initialText);
  const [menuOpen, setMenuOpen] = useState(false);
  const [menuAnchor, setMenuAnchor] = useState(null);
  const rootRef = useRef(null);
  const toggleMenu = () => {
    if (menuOpen) {
      setMenuOpen(false);
      return;
    }
    const node = rootRef.current;
    if (!node?.measureInWindow) {
      setMenuAnchor(null);
      setMenuOpen(true);
      return;
    }
    node.measureInWindow((x, y) => {
      setMenuAnchor({ x, y });
      setMenuOpen(true);
    });
  };
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
  const onMention = mentionSource
    ? () => setText((cur) => (cur.endsWith('@') ? cur : `${cur}${cur && !cur.endsWith(' ') ? ' ' : ''}@`))
    : null;
  const menu = composerMenuActions({ onPickAttachment, onMention, modelChip });
  const plus = menu.length === 0 ? null : menu.length === 1 && onPickAttachment ? onPickAttachment : toggleMenu;

  const actionBg = accent ?? colors.accent;

  return (
    <View
      ref={rootRef}
      style={{
        backgroundColor: colors.bg,
      }}
    >
      <View pointerEvents="none" style={{ position: 'absolute', left: 0, right: 0, top: -STREAM_FADE, height: STREAM_FADE }}>
        <EdgeFade side="bottom" color={colors.bg} size={STREAM_FADE} />
      </View>
      {menuOpen ? <ComposerMenu actions={menu} anchor={menuAnchor} onClose={() => setMenuOpen(false)} /> : null}
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
          testID="composer-pill"
          style={{
            flexDirection: 'row',
            alignItems: 'flex-end',
            gap: space.s2,
            minHeight: COMPOSER_H,
            padding: space.s3,
            borderRadius: radii.sheet,
            backgroundColor: colors.fill,
          }}
        >
          {plus ? (
            <RoundButton label={menu.length === 1 && onPickAttachment ? 'Attach file' : 'Add'} onPress={plus} disabled={disabled}>
              <Icon name="plus" size="md" color={colors.ink2} />
            </RoundButton>
          ) : null}
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
            style={{
              flex: 1,
              minWidth: 0,
              alignSelf: 'center',
              fontFamily: fonts.sans.regular,
              fontSize: chatSize,
              lineHeight: Math.round(chatSize * typeLeading.read),
              color: colors.ink,
              maxHeight: 120,
              paddingHorizontal: plus ? 0 : space.s3,
              paddingVertical: 0,
            }}
          />
          <RoundButton
            label={stoppable ? 'Stop' : 'Send'}
            onPress={stoppable ? stop : canSend ? submit : undefined}
            disabled={!stoppable && !canSend}
            dimmed={!!disabled || (!stoppable && !canSend)}
            fill={!stoppable && !canSend ? colors.pressed : actionBg}
          >
            <Icon
              name={stoppable ? 'square' : 'arrow-up'}
              size="md"
              color={!stoppable && !canSend ? colors.ink3 : contrastText(actionBg)}
            />
          </RoundButton>
        </View>
      </Animated.View>
    </View>
  );
}
