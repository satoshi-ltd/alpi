import { useEffect, useState } from 'react';
import { Modal, Pressable, Text, TextInput, View } from 'react-native';
import { radii, space, tracking, typography } from '../theme/tokens';

import { useTheme } from '../theme/ThemeContext';
import { Button } from './Button';

export function TextPrompt({
  open,
  onClose,
  title,
  label,
  initialValue = '',
  placeholder = '',
  maxLength = 64,
  confirmLabel = 'Save',
  onSubmit,
}) {
  const { colors, fonts, fontSizes } = useTheme();
  const [value, setValue] = useState(initialValue);
  useEffect(() => {
    if (open) setValue(initialValue);
  }, [open, initialValue]);
  const clean = value.trim();
  const ready = clean.length > 0 && clean !== String(initialValue ?? '').trim();

  return (
    <Modal
      visible={open}
      transparent
      animationType="fade"
      statusBarTranslucent
      supportedOrientations={['portrait', 'landscape-left', 'landscape-right']}
      onRequestClose={onClose}
    >
      <Pressable
        onPress={onClose}
        style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', alignItems: 'center', justifyContent: 'center', padding: space.s9 }}
      >
        <Pressable
          onPress={() => {}}
          style={{
            width: '100%',
            maxWidth: 420,
            backgroundColor: colors.bgPane,
            borderRadius: radii.sheet,
            padding: space.s9,
            gap: space.s7,
          }}
        >
          <Text
            style={{
              fontFamily: fonts.sans.semibold,
              fontSize: fontSizes[typography.dialogTitle.size],
              color: colors.ink,
              letterSpacing: fontSizes[typography.dialogTitle.size] * tracking.snug,
            }}
          >
            {title}
          </Text>
          <View style={{ gap: space.s3 }}>
            {label ? (
              <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3, letterSpacing: 0.6 }}>
                {label}
              </Text>
            ) : null}
            <TextInput
              value={value}
              onChangeText={setValue}
              placeholder={placeholder}
              placeholderTextColor={colors.ink4}
              maxLength={maxLength}
              autoFocus
              autoCapitalize="none"
              autoCorrect={false}
              spellCheck={false}
              returnKeyType="done"
              onSubmitEditing={() => { if (ready) onSubmit?.(clean); }}
              style={{
                backgroundColor: colors.bgInput,
                borderRadius: radii.xl,
                borderWidth: 0.5,
                borderColor: colors.line2,
                paddingHorizontal: space.s5,
                height: 44,
                fontFamily: fonts.mono,
                fontSize: fontSizes.md,
                color: colors.ink,
              }}
            />
          </View>
          <View style={{ gap: space.s3, marginTop: space.s1 }}>
            <Button title={confirmLabel} onPress={() => onSubmit?.(clean)} disabled={!ready} fullWidth />
            <Button title="Cancel" variant="ghost" onPress={onClose} fullWidth />
          </View>
        </Pressable>
      </Pressable>
    </Modal>
  );
}
