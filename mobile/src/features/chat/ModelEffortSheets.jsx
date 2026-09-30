import { useState } from 'react';

import { ActionSheet } from '../../components/ActionSheet';
import { Icon } from '../../components/Icon';
import { modelLabel } from '../../lib/modelLabel';
import { profileLabel } from '../../lib/profileName';
import { ModelSheet, ReasoningEffortSheet } from '../sheets/ProfileFieldSheets';
import { useModalHandoff } from './useModalHandoff';

export function ModelEffortSheets({ open, onClose, profile, accent, onSave }) {
  const [sheet, setSheet] = useState(null);
  const [armed, setArmed] = useState(false);
  const handoff = useModalHandoff();
  const show = (next) => handoff(() => {
    setArmed(true);
    setSheet(next);
  });
  const close = () => {
    setSheet(null);
    handoff(() => setArmed(false));
  };
  const effort = profile?.model_reasoning_effort ?? '';
  const actions = [
    { id: 'model', label: 'Model', icon: <Icon name="sparkle" size="lg" />, detail: modelLabel(profile?.model), onPress: () => show('model') },
    { id: 'effort', label: 'Reasoning effort', icon: <Icon name="brain" size="lg" />, detail: effort || 'default', onPress: () => show('effort') },
  ];
  return (
    <>
      <ActionSheet open={open} onClose={onClose} title={`@${profileLabel(profile?.name ?? '')}`} subtitle="MODEL AND EFFORT" actions={actions} />
      {armed ? (
        <>
          <ModelSheet
            open={sheet === 'model'}
            onClose={close}
            profileName={profile?.name}
            accent={accent}
            initialValue={profile?.model}
            profileModels={profile?.models ?? []}
            providerKeys={profile?.provider_keys ?? []}
            openrouterModels={profile?.providers?.openrouter?.models ?? []}
            ollamaNames={(profile?.provider_ollama ?? []).map((o) => o.name)}
            onSave={(value) => onSave('model', value)}
          />
          <ReasoningEffortSheet
            open={sheet === 'effort'}
            onClose={close}
            initialValue={effort}
            onSave={(value) => onSave('model_reasoning.effort', value)}
          />
        </>
      ) : null}
    </>
  );
}
