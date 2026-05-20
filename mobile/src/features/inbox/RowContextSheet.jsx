import { ActionSheet } from '../../components/ActionSheet';
import { Icon } from '../../components/Icon';
import { useTheme } from '../../theme/ThemeContext';

export function RowContextSheet({ target, onClose, onPin, onOpenSettings }) {
  const { colors } = useTheme();
  const open = !!target;
  const title = target
    ? (target.kind === 'profile'
        ? `@${target.id}`
        : `#${target.name || target.label || target.id}`)
    : '';
  const subtitle = target ? (target.kind === 'profile' ? 'PROFILE' : 'WORKGROUP') : '';

  const actions = target
    ? [
        {
          id: 'pin',
          label: target.pinned ? 'Unpin' : 'Pin',
          icon: <Icon name="plus" size={20} color={colors.ink2} />,
          onPress: () => onPin?.(target),
        },
        {
          id: 'settings',
          label: 'Settings',
          icon: <Icon name="gear" size={20} color={colors.ink2} />,
          onPress: () => onOpenSettings?.(target),
        },
      ]
    : [];

  return <ActionSheet open={open} onClose={onClose} title={title} subtitle={subtitle} actions={actions} />;
}
