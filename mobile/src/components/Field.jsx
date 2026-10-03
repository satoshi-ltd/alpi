import { Text, TextInput, View } from 'react-native';
import { radii, space, lineHeights } from '../theme/tokens';

import { Eyebrow } from './Eyebrow';
import { useTheme } from '../theme/ThemeContext';
import { useWell } from './well';

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
  error,
}) {
  const { colors, fonts, fontSizes, mobile } = useTheme();
  const [well, focus] = useWell(colors, !!error);
  return (
    <View style={{ gap: space.s2 }}>
      {label ? <FieldLabel>{label}</FieldLabel> : null}
      <View
        style={{
          ...well,
          ...(editable ? null : { backgroundColor: colors.bgPane }),
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
          {...focus}
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
            lineHeight: (mono ? fontSizes.sm : fontSizes.lg) * lineHeights.normal,
            color: editable ? colors.ink : colors.ink2,
            textAlignVertical: multiline ? 'top' : 'center',
          }}
        />
        {rightSlot}
      </View>
      {error ? (
        <Text accessibilityRole="alert" style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.dangerText }}>
          {error}
        </Text>
      ) : helper ? (
        <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>
          {helper}
        </Text>
      ) : null}
    </View>
  );
}
