import * as Clipboard from 'expo-clipboard';
import { useState } from 'react';

import { ActionSheet } from '../../components/ActionSheet';
import { Icon } from '../../components/Icon';
import { useTheme } from '../../theme/ThemeContext';
import { buildMessageActions } from './messageActions';
import { SelectTextSheet } from './SelectTextSheet';
import { useModalHandoff } from './useModalHandoff';

const ICONS = {
  copy: 'copy',
  select: 'file-text',
  edit: 'pencil',
  retry: 'refresh-cw',
  'retry-agent': 'refresh-cw',
};

export function MessageActionsSheet({ target, onClose, onRetry, onEdit }) {
  const { colors } = useTheme();
  const [selecting, setSelecting] = useState(null);
  const [armed, setArmed] = useState(false);
  const handoff = useModalHandoff();
  const selectText = (t) => handoff(() => {
    setArmed(true);
    setSelecting(t.text);
  });
  const closeSelect = () => {
    setSelecting(null);
    handoff(() => setArmed(false));
  };
  const open = !!target;
  const isAgent = target?.kind === 'agent';

  const onCopy = async (t) => {
    if (t?.text) await Clipboard.setStringAsync(t.text);
  };

  const actions = buildMessageActions(target, { onCopy, onSelectText: selectText, onEdit, onRetry }).map((a) => ({
    ...a,
    icon: <Icon name={ICONS[a.id] || 'forward'} size={20} color={colors.ink2} />,
  }));

  return (
    <>
      <ActionSheet open={open} onClose={onClose} title={isAgent ? 'Agent message' : 'Your message'} actions={actions} />
      {armed ? <SelectTextSheet text={selecting} onClose={closeSelect} /> : null}
    </>
  );
}
