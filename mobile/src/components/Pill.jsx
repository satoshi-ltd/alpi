import { Text, View } from 'react-native';
import { lineHeights, radii, space } from '../theme/tokens';

import { useTheme } from '../theme/ThemeContext';

const TONES = {
  on: 'success',
  err: 'danger',
  warn: 'warning',
};

function mixHex(hex, pct, base) {
  const fromHex = (h) => {
    const v = h.replace('#', '');
    return [parseInt(v.slice(0, 2), 16), parseInt(v.slice(2, 4), 16), parseInt(v.slice(4, 6), 16)];
  };
  const [r1, g1, b1] = fromHex(hex);
  const [r2, g2, b2] = fromHex(base);
  const r = Math.round(r1 * pct + r2 * (1 - pct));
  const g = Math.round(g1 * pct + g2 * (1 - pct));
  const b = Math.round(b1 * pct + b2 * (1 - pct));
  return `rgb(${r},${g},${b})`;
}

export function Pill({ tone, children, off = false }) {
  const { colors, fonts , fontSizes} = useTheme();
  const accentKey = TONES[tone];
  const tint = accentKey ? colors[accentKey] : null;
  let bg = colors.hover;
  let fg = colors.ink2;
  if (tone === 'on' && tint) {
    bg = mixHex(tint, 0.16, colors.bgPane);
    fg = mixHex(tint, 0.7, colors.ink);
  } else if (tone === 'warn' && tint) {
    bg = mixHex(tint, 0.18, colors.bgPane);
    fg = '#a98113';
  } else if (tone === 'err' && tint) {
    bg = mixHex(tint, 0.16, colors.bgPane);
    fg = mixHex(tint, 0.7, colors.ink);
  }

  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        gap: space.s2,
        minHeight: 22,
        paddingHorizontal: space.s3,
        borderRadius: radii.pill,
        backgroundColor: bg,
        opacity: off ? 0.55 : 1,
      }}
    >
      <Text
        style={{
          fontFamily: fonts.monoMedium,
          fontSize: fontSizes.sm,
          lineHeight: fontSizes.sm * lineHeights.cozy,
          color: fg,
        }}
      >
        {children}
      </Text>
    </View>
  );
}
