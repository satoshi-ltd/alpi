import { Text, View } from 'react-native';

import { mixHex } from '../../../../common/color.mjs';
import { severityTag } from '../../lib/outputsFormat';
import { useTheme } from '../../theme/ThemeContext';
import { radii, space, tracking } from '../../theme/tokens';

export function SeverityTag({ row }) {
  const { colors, fonts, fontSizes } = useTheme();
  const word = severityTag(row);
  if (!word) return null;
  const tone = word === 'ERROR' ? colors.dangerText : colors.warningText;
  return (
    <View style={{ paddingHorizontal: space.s1, borderRadius: radii.tag, backgroundColor: mixHex(tone, 0.12, colors.bgPane) }}>
      <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, letterSpacing: fontSizes.xs * tracking.wide, color: tone }}>
        {word}
      </Text>
    </View>
  );
}
