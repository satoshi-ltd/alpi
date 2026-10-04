import { Fold } from '../../components/Fold';
import { ScreenHeader } from '../../components/ScreenHeader';
import { useProfile } from '../../hooks/useSubject';

export function PanelHeader({ profile, section, count = null, onBack, right }) {
  const summary = useProfile(profile ?? null, { skipDetail: true })?.profile;
  const accent = typeof summary?.accent === 'string' ? summary.accent : undefined;
  return (
    <ScreenHeader
      title={String(profile ?? '')}
      subtitle={count != null ? `${section} · ${count}` : section}
      onBack={onBack}
      accent={accent}
      leadingGlyph={<Fold fold={summary?.fold} color={accent} size="md" />}
      right={right}
    />
  );
}
