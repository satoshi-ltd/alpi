import { useState } from 'react';

import { modelLabel } from '../../lib/modelLabel';
import { ModelSheet, ReasoningEffortSheet } from '../sheets/ProfileFieldSheets';
import { useModalHandoff } from './useModalHandoff';

export function ModelEffortSheets({ open, onClose, profile, accent, onSave }) {
  const [modelOpen, setModelOpen] = useState(false);
  const [armed, setArmed] = useState(false);
  const handoff = useModalHandoff();
  const showModel = () => {
    onClose();
    handoff(() => {
      setArmed(true);
      setModelOpen(true);
    });
  };
  const closeModel = () => {
    setModelOpen(false);
    handoff(() => setArmed(false));
  };
  const effort = profile?.model_reasoning_effort ?? '';
  return (
    <>
      <ReasoningEffortSheet
        open={open}
        onClose={onClose}
        initialValue={effort}
        modelRow={{ label: modelLabel(profile?.model) || 'default', onPress: showModel }}
        onSave={(value) => onSave('model_reasoning.effort', value)}
      />
      {armed ? (
        <ModelSheet
          open={modelOpen}
          onClose={closeModel}
          profileName={profile?.name}
          accent={accent}
          initialValue={profile?.model}
          profileModels={profile?.models ?? []}
          providerKeys={profile?.provider_keys ?? []}
          openrouterModels={profile?.providers?.openrouter?.models ?? []}
          ollamaNames={(profile?.provider_ollama ?? []).map((o) => o.name)}
          onSave={(value) => onSave('model', value)}
        />
      ) : null}
    </>
  );
}
