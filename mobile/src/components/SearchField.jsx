import { TextInput, View } from 'react-native';
import { radii, space , fontSizes} from '../theme/tokens';

import { Icon } from './Icon';
import { useTheme } from '../theme/ThemeContext';

export function SearchField({
  value,
  onChangeText,
  placeholder = 'Search',
  autoCapitalize = 'none',
  autoCorrect = false,
}) {
  const { colors, fonts, fontSizes } = useTheme();
  const fs = fontSizes.msg;
  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        gap: space.s4,
        backgroundColor: colors.bgInput,
        borderWidth: 0.5,
        borderColor: colors.line2,
        borderRadius: radii.lg,
        paddingHorizontal: space.s6,
        paddingVertical: 0,
        minHeight: 44,
      }}
    >
      <Icon name="search" size={18} color={colors.ink3} />
      <TextInput
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={colors.ink3}
        autoCapitalize={autoCapitalize}
        autoCorrect={autoCorrect}
        includeFontPadding={false}
        style={{
          flex: 1,
          paddingTop: 0,
          paddingBottom: 0,
          fontFamily: fonts.sans.regular,
          fontSize: fs,
          lineHeight: fs * 1.4,
          color: colors.ink,
          textAlignVertical: 'center',
        }}
      />
    </View>
  );
}
