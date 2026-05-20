import * as Clipboard from 'expo-clipboard';

import { ActionSheet } from '../../components/ActionSheet';
import { Icon } from '../../components/Icon';
import { useTheme } from '../../theme/ThemeContext';

export function MessageActionsSheet({ target, onClose, onRetry, onEdit }) {
  const { colors } = useTheme();
  const open = !!target;
  const isAgent = target?.kind === 'agent';

  const copy = async () => {
    if (target?.text) await Clipboard.setStringAsync(target.text);
  };

  const actions = target
    ? [
        {
          id: 'copy',
          label: 'Copy',
          icon: <Icon name="forward" size={20} color={colors.ink2} />,
          onPress: copy,
        },
        !isAgent && {
          id: 'edit',
          label: 'Edit',
          icon: <Icon name="plus" size={20} color={colors.ink2} />,
          onPress: () => onEdit?.(target),
        },
        !isAgent && {
          id: 'retry',
          label: 'Retry',
          icon: <Icon name="back" size={20} color={colors.ink2} />,
          onPress: () => onRetry?.(target),
        },
        isAgent && {
          id: 'retry-agent',
          label: 'Ask again',
          icon: <Icon name="back" size={20} color={colors.ink2} />,
          onPress: () => onRetry?.(target),
        },
      ].filter(Boolean)
    : [];

  return <ActionSheet open={open} onClose={onClose} title={isAgent ? 'Agent message' : 'Your message'} actions={actions} />;
}
