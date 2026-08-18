import { useTheme } from '../theme/ThemeContext';
import { Diamond } from './Diamond';
import { DiamondStack } from './DiamondStack';

export function Glyph({ kind, color, needsProvider = false }) {
  const { colors } = useTheme();
  const tint = typeof color === 'string' && color.startsWith('#') ? color : colors.ink3;
  return kind === 'workgroup' ? (
    <DiamondStack color={tint} size="md" />
  ) : (
    <Diamond color={tint} size="md" outlined={needsProvider} />
  );
}
