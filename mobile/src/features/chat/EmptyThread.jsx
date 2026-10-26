import { FOLD_SIZES } from '../../../../common/folds.mjs';
import { EmptyState } from '../../components/EmptyState';
import { Fold } from '../../components/Fold';
import { CONTENT_MAX_W } from '../../lib/panes';
import { useTheme } from '../../theme/ThemeContext';

export function EmptyThread({ heading, detail, accent, fold }) {
  const { colors } = useTheme();
  return (
    <EmptyState
      hero
      monoDetail
      maxWidth={CONTENT_MAX_W}
      mark={<Fold fold={fold} color={accent ?? colors.ink3} size={FOLD_SIZES.hero} />}
      title={heading}
      detail={detail}
    />
  );
}
