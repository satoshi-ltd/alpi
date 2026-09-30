import { Platform, ScrollView, Text, TextInput } from 'react-native';

import { Sheet } from '../../components/Sheet';
import { useTheme } from '../../theme/ThemeContext';
import { lineHeights, space, typography } from '../../theme/tokens';

export function SelectTextSheet({ text, onClose }) {
  const { colors, fonts, fontSizes } = useTheme();
  const size = fontSizes[typography.chat.size];
  const style = {
    fontFamily: fonts.sans.regular,
    fontSize: size,
    lineHeight: size * lineHeights.relaxed,
    color: colors.ink,
    padding: 0,
  };
  return (
    <Sheet open={!!text} onClose={onClose} title="Select text" maxHeight="92%">
      <ScrollView contentContainerStyle={{ paddingHorizontal: space.s8, paddingBottom: space.s8 }}>
        {Platform.OS === 'ios' ? (
          // iOS Text only copies whole; a read-only UITextView keeps range selection.
          <TextInput value={text ?? ''} editable={false} multiline scrollEnabled={false} style={style} />
        ) : (
          <Text selectable style={style}>{text}</Text>
        )}
      </ScrollView>
    </Sheet>
  );
}
