import { useEffect, useState } from 'react';
import { Keyboard, Modal, Pressable, Text, TextInput, View } from 'react-native';
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
  allowEmpty = false,
  keyboardType = 'default',
}) {
  const { colors, fonts, fontSizes } = useTheme();
  const [value, setValue] = useState(initialValue);
  const [kbHeight, setKbHeight] = useState(0);
  useEffect(() => {
    if (open) setValue(initialValue);
  }, [open, initialValue]);
  useEffect(() => {
    const showSub = Keyboard.addListener('keyboardDidShow', (e) => setKbHeight(e.endCoordinates.height));
    const hideSub = Keyboard.addListener('keyboardDidHide', () => setKbHeight(0));
    return () => { showSub.remove(); hideSub.remove(); };
  }, []);
  const clean = value.trim();
  const ready = (allowEmpty || clean.length > 0) && clean !== String(initialValue ?? '').trim();

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
        accessible={false}
        style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', alignItems: 'center', justifyContent: 'center', padding: space.s9, paddingBottom: space.s9 + kbHeight }}
      >
        <Pressable
          onPress={() => {}}
          accessible={false}
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
              keyboardType={keyboardType}
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
