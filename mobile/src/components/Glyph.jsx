import { View } from 'react-native';

import { useTheme } from '../theme/ThemeContext';
import { Diamond } from './Diamond';
import { Hash } from './Hash';

function mix(hex, pct, base) {
  const fromHex = (h) => {
    if (typeof h !== 'string') return [0, 0, 0];
    const v = h.replace('#', '');
    if (v.length < 6) return [0, 0, 0];
    return [parseInt(v.slice(0, 2), 16), parseInt(v.slice(2, 4), 16), parseInt(v.slice(4, 6), 16)];
  };
  const [r1, g1, b1] = fromHex(hex);
  const [r2, g2, b2] = fromHex(base);
  const r = Math.round(r1 * pct + r2 * (1 - pct));
  const g = Math.round(g1 * pct + g2 * (1 - pct));
  const b = Math.round(b1 * pct + b2 * (1 - pct));
  return `rgb(${r},${g},${b})`;
}

function alpha(hex, a) {
  if (typeof hex !== 'string') return 'transparent';
  const v = hex.replace('#', '');
  if (v.length < 6) return 'transparent';
  const aHex = Math.round(a * 255).toString(16).padStart(2, '0');
  return `#${v}${aHex}`;
}

export function Glyph({ kind, color, size = 36, needsProvider = false }) {
  const { colors } = useTheme();
  const safeColor = typeof color === 'string' && color.startsWith('#') ? color : colors.ink3;
  const tint = needsProvider ? 'transparent' : mix(safeColor, 0.18, colors.bgPane);
  return (
    <View
      style={{
        width: size,
        height: size,
        borderRadius: size / 2,
        backgroundColor: tint,
        borderWidth: needsProvider ? 1.5 : 0,
        borderStyle: needsProvider ? 'dashed' : undefined,
        borderColor: needsProvider ? alpha(color, 0.5) : 'transparent',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      {kind === 'profile' ? (
        <Diamond color={color} size={needsProvider ? 13 : 14} outlined={needsProvider} />
      ) : (
        <Hash color={color} size={18} />
      )}
    </View>
  );
}
