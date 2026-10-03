import { WORKGROUP_FOLD } from '../../../common/folds.mjs';
import { useTheme } from '../theme/ThemeContext';
import { Fold } from './Fold';

export function Glyph({ kind, color, fold, needsProvider = false, working = false, paused = false, offline = false }) {
  const { colors } = useTheme();
  const tint = typeof color === 'string' && color.startsWith('#') ? color : colors.ink3;
  return kind === 'workgroup' ? (
    <Fold fold={WORKGROUP_FOLD} color={tint} pulse={working && !paused} unfolded={offline || paused} />
  ) : (
    <Fold fold={fold} color={tint} pulse={working && !needsProvider && !paused} outlined={needsProvider} unfolded={offline || paused} />
  );
}
