import * as Clipboard from 'expo-clipboard';

import { ActionSheet } from '../../components/ActionSheet';
import { Icon } from '../../components/Icon';
import { useTheme } from '../../theme/ThemeContext';
import { buildMessageActions } from './messageActions';

const ICONS = {
  copy: 'forward',
  edit: 'plus',
  retry: 'back',
  'retry-agent': 'back',
};

export function MessageActionsSheet({ target, onClose, onRetry, onEdit }) {
  const { colors } = useTheme();
  const open = !!target;
  const isAgent = target?.kind === 'agent';

  const onCopy = async (t) => {
    if (t?.text) await Clipboard.setStringAsync(t.text);
  };

  const actions = buildMessageActions(target, { onCopy, onEdit, onRetry }).map((a) => ({
    ...a,
    icon: <Icon name={ICONS[a.id] || 'forward'} size={20} color={colors.ink2} />,
  }));

  return <ActionSheet open={open} onClose={onClose} title={isAgent ? 'Agent message' : 'Your message'} actions={actions} />;
}
