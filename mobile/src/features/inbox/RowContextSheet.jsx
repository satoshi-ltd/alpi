import { useRouter } from 'expo-router';

import { ActionSheet } from '../../components/ActionSheet';
import { Icon } from '../../components/Icon';
import { useToast } from '../../components/Toast';
import { useCanAdminEarly } from '../../hooks/useActiveRole';
import { seedCache } from '../../hooks/useDaemonData';
import { useEndpoint } from '../../lib/EndpointContext';
import { useTheme } from '../../theme/ThemeContext';

export function RowContextSheet({ target, onClose, onPin, onOpenSettings }) {
  const { colors } = useTheme();
  const router = useRouter();
  const toast = useToast();
  const { call, endpoint } = useEndpoint();
  const canAdmin = useCanAdminEarly();
  const open = !!target;
  const title = target
    ? (target.kind === 'profile'
        ? `@${target.id}`
        : `#${target.name || target.label || target.id}`)
    : '';
  const subtitle = target ? (target.kind === 'profile' ? 'PROFILE' : 'WORKGROUP') : '';

  const togglePause = async (row) => {
    try {
      await call('host.config.set_field', {
        profile: row.id,
        key: 'paused',
        value: row.paused ? 'false' : 'true',
      });
      toast({ title: row.paused ? 'Resumed' : 'Paused', message: `@${row.id}` });
      const fresh = await call('host.profile.summaries', {});
      seedCache(endpoint?.id, 'host.profile.summaries', {}, fresh);
    } catch (e) {
      toast({ title: row.paused ? 'Resume failed' : 'Pause failed', message: String(e) });
    }
  };

  const settingsPath = (row, intent) =>
    `${row.kind === 'workgroup' ? `/wg/${row.id}` : `/profile/${row.id}`}/settings${intent ? `?intent=${intent}` : ''}`;

  const actions = target
    ? [
        {
          id: 'pin',
          label: target.pinned ? 'Unpin' : 'Pin',
          icon: <Icon name="pin" size={20} color={colors.ink2} />,
          onPress: () => onPin?.(target),
        },
        ...(canAdmin ? [{ id: 'sep-actions', divider: true }] : []),
        ...(canAdmin && target.kind === 'profile'
          ? [
              {
                id: 'pause',
                label: target.paused ? 'Resume profile' : 'Pause profile',
                icon: (
                  <Icon name={target.paused ? 'power' : 'pause'} size={20} color={colors.ink2} />
                ),
                onPress: () => togglePause(target),
              },
            ]
          : []),
        ...(onOpenSettings
          ? [
              {
                id: 'settings',
                label: 'Open settings',
                icon: <Icon name="gear" size={20} color={colors.ink2} />,
                onPress: () => onOpenSettings(target),
              },
            ]
          : []),
        ...(canAdmin
          ? [
              { id: 'sep-danger', divider: true },
              {
                id: 'delete',
                label: target.kind === 'workgroup' ? 'Delete workgroup…' : 'Delete profile…',
                danger: true,
                icon: <Icon name="trash" size={20} color={colors.danger} />,
                onPress: () => router.push(settingsPath(target, 'delete')),
              },
            ]
          : []),
      ]
    : [];

  return <ActionSheet open={open} onClose={onClose} title={title} subtitle={subtitle} actions={actions} />;
}
