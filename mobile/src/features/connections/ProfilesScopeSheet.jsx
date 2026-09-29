import { useEffect, useMemo, useState } from 'react';
import { ScrollView, Text, View } from 'react-native';
import { space } from '../../theme/tokens';

import { Sheet } from '../../components/Sheet';
import { useToast } from '../../components/Toast';
import { useProfileSummaries } from '../../hooks/useDaemonData';
import { useEndpoint } from '../../lib/EndpointContext';
import { useTheme } from '../../theme/ThemeContext';
import { ProfilePicker } from './NewConnectionSheet';

export function ProfilesScopeSheet({ open, onClose, connection, onSaved }) {
  const toast = useToast();
  const { call } = useEndpoint();
  const { colors, fonts, fontSizes } = useTheme();
  const summaries = useProfileSummaries();
  const [scope, setScope] = useState([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) setScope(connection?.profile_scope ?? []);
  }, [open, connection?.id, connection?.profile_scope]);

  const profiles = useMemo(
    () => (summaries.data?.profiles ?? []).map((p) => p.name).filter(Boolean),
    [summaries.data],
  );

  const save = async () => {
    if (!connection || busy) return;
    setBusy(true);
    try {
      await call('host.connections.update', { connection_id: connection.id, profiles: scope });
      toast({ title: 'Profiles saved', duration: 1400 });
      onSaved?.();
      onClose?.();
    } catch (e) {
      toast({ title: 'Save failed', message: String(e?.data?.detail ?? e), duration: 3200 });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Profiles"
      subtitle={connection?.label}
      primaryAction={{ label: busy ? 'Saving…' : 'Save', onPress: save, disabled: busy }}
    >
      <ScrollView contentContainerStyle={{ paddingHorizontal: space.s8, paddingVertical: space.s5, gap: space.s5 }}>
        <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>
          none selected = every profile
        </Text>
        <ProfilePicker
          profiles={profiles}
          selected={scope}
          onToggle={(name) => setScope((cur) => (cur.includes(name) ? cur.filter((n) => n !== name) : [...cur, name]))}
        />
        <View style={{ height: space.s3 }} />
      </ScrollView>
    </Sheet>
  );
}
