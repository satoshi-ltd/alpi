import { Text, View } from 'react-native';

import { lineHeights, space } from '../../theme/tokens';
import { useTheme } from '../../theme/ThemeContext';
import { mixHex } from '../../../../common/color.mjs';

const DOT = 6;

export const STATE_TEXT = { 'needs-you': 'needs you', failed: 'failed', working: 'working' };

export function stateColor(state, colors, accent) {
  if (state === 'needs-you') return colors.warningText ?? colors.warning;
  if (state === 'failed') return colors.dangerText ?? colors.danger;
  return /^#[0-9a-f]{6}$/i.test(accent ?? '') && /^#[0-9a-f]{6}$/i.test(colors.ink ?? '') ? mixHex(accent, 0.5, colors.ink) : accent ?? colors.ink2;
}

function StateDot({ color }) {
  return <View testID="state-dot" style={{ width: DOT, height: DOT, borderRadius: DOT / 2, backgroundColor: color }} />;
}

export function RowState({ state, phases, color: accent }) {
  const { colors, fonts, fontSizes } = useTheme();
  if (!state) return null;
  const color = stateColor(state, colors, accent);
  const text = phases ?? STATE_TEXT[state];
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s2 }}>
      {state === 'working' ? null : <StateDot color={color} />}
      <Text
        numberOfLines={1}
        style={{
          fontFamily: phases ? fonts.monoMedium : fonts.sans.medium,
          fontSize: fontSizes.xs,
          lineHeight: fontSizes.xs * lineHeights.cozy,
          color,
        }}
      >
        {text}
      </Text>
    </View>
  );
}
