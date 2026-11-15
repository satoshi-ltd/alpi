import { MARK_SIZES } from '../../../../common/agentMarks.mjs';
import { EmptyState } from '../../components/EmptyState';
import { Fold } from '../../components/Fold';
import { CONTENT_MAX_W } from '../../lib/panes';
import { useTheme } from '../../theme/ThemeContext';

export function EmptyThread({ heading, detail, accent, shape, state }) {
  const { colors } = useTheme();
  return (
    <EmptyState
      hero
      monoDetail
      maxWidth={CONTENT_MAX_W}
      mark={<Fold shape={shape} color={accent ?? colors.ink3} size={MARK_SIZES.hero} state={state} />}
      title={heading}
      detail={detail}
    />
  );
}
