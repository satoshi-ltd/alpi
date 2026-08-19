import { Text, TextInput, View } from 'react-native';
import { radii, space } from '../theme/tokens';

import { Eyebrow } from './Eyebrow';
import { useTheme } from '../theme/ThemeContext';

export function FieldLabel({ children }) {
  return <Eyebrow>{children}</Eyebrow>;
}

export function Field({
  label,
  helper,
  value,
  onChangeText,
  placeholder,
  multiline = false,
  mono = false,
  keyboardType = 'default',
  autoCapitalize = 'sentences',
  autoCorrect = true,
  editable = true,
  rows = 3,
  rightSlot,
}) {
  const { colors, fonts, fontSizes, mobile } = useTheme();
  return (
    <View style={{ gap: space.s2 }}>
      {label ? <FieldLabel>{label}</FieldLabel> : null}
      <View
        style={{
          backgroundColor: editable ? colors.bgInput : colors.bgPane,
          borderRadius: radii.xl,
          borderWidth: 0.5,
          borderColor: colors.line2,
          paddingHorizontal: space.s5,
          paddingVertical: multiline ? 12 : 0,
          minHeight: multiline ? rows * 22 + 24 : mobile.inputH,
          flexDirection: 'row',
          alignItems: multiline ? 'flex-start' : 'center',
          gap: space.s3,
        }}
      >
        <TextInput
          value={value}
          onChangeText={onChangeText}
          placeholder={placeholder}
          placeholderTextColor={colors.ink3}
          multiline={multiline}
          editable={editable}
          keyboardType={keyboardType}
          autoCapitalize={autoCapitalize}
          autoCorrect={autoCorrect}
          includeFontPadding={false}
          style={{
            flex: 1,
            paddingTop: 0,
            paddingBottom: 0,
            fontFamily: mono ? fonts.mono : fonts.sans.regular,
            fontSize: mono ? fontSizes.sm : fontSizes.lg,
            lineHeight: (mono ? fontSizes.sm : fontSizes.lg) * 1.4,
            color: editable ? colors.ink : colors.ink2,
            textAlignVertical: multiline ? 'top' : 'center',
          }}
        />
        {rightSlot}
      </View>
      {helper ? (
        <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink4 }}>
          {helper}
        </Text>
      ) : null}
    </View>
  );
}
