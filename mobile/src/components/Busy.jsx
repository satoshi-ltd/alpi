import { Text, View } from 'react-native';

import { TWIN_SHAPE } from '../../../common/shapes.mjs';
import { BUSY_LABEL, BUSY_MIN_MARK_PX } from '../../../common/busy.mjs';
import { useBusyVisible } from '../hooks/useBusyVisible';
import { useTheme } from '../theme/ThemeContext';
import { space } from '../theme/tokens';
import { Fold } from './Fold';

const INLINE_MAX = 24;

export function Busy({ label, size = 40, active = true, visible, fill = false, style }) {
  const { colors, fonts, fontSizes } = useTheme();
  const delayed = useBusyVisible(visible === undefined && active);
  const shown = visible ?? delayed;
  const px = Math.max(size, BUSY_MIN_MARK_PX);

  if (!shown) return fill ? <View style={[{ flex: 1 }, style]} /> : null;

  const inline = px <= INLINE_MAX;
  return (
    <View
      accessible
      accessibilityRole="progressbar"
      accessibilityLabel={label || BUSY_LABEL}
      style={[
        inline
          ? { flexDirection: 'row', alignItems: 'center', gap: space.s3 }
          : { alignItems: 'center', justifyContent: 'center', gap: space.s5, padding: space.s8 },
        fill ? { flex: 1, alignItems: 'center', justifyContent: 'center' } : null,
        style,
      ]}
    >
      <Fold shape={TWIN_SHAPE} size={px} state="busy" seed="alpi-busy" />
      {label ? (
        <Text style={{ flexShrink: 1, textAlign: inline ? 'left' : 'center', fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink2 }}>
          {label}
        </Text>
      ) : null}
    </View>
  );
}
