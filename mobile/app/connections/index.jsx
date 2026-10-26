import { useFocusEffect, useRouter } from 'expo-router';
import { useCallback, useState } from 'react';
import { RefreshControl, ScrollView, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { formatUsd } from '../../../common/format.mjs';
import { AdminGuard } from '../../src/components/AdminGuard';
import { Button } from '../../src/components/Button';
import { Pill } from '../../src/components/Pill';
import { Row, RowGroup, RowSeparator, SectionHeader } from '../../src/components/Row';
import { ScreenHeader } from '../../src/components/ScreenHeader';
import { SyncBar } from '../../src/components/SyncBar';
import { NewConnectionSheet } from '../../src/features/connections/NewConnectionSheet';
import { PairingSheet } from '../../src/features/connections/PairingSheet';
import { connectionMeta, relativeSeen } from '../../src/features/connections/format';
import { useBack } from '../../src/hooks/useBack';
import { usePullRefresh } from '../../src/hooks/usePullRefresh';
import { useConnectionsSummary } from '../../src/hooks/useDaemonData';
import { settingsContentStyle } from '../../src/lib/panes';
import { usePane } from '../../src/nav/PaneContext';
import { useTheme } from '../../src/theme/ThemeContext';
import { LoadFailed } from '../../src/components/LoadFailed';
import { EMPTY } from '../../../common/emptyCopy.mjs';
import { Busy } from '../../src/components/Busy';
import { useBusyVisible } from '../../src/hooks/useBusyVisible';

export default function ConnectionsRoute() {
  return (
    <AdminGuard>
      <ConnectionsScreen />
    </AdminGuard>
  );
}

function ConnectionsScreen() {
  const router = useRouter();
  const goBack = useBack();
  const { colors } = useTheme();
  const { twoPane } = usePane();
  const summary = useConnectionsSummary();
  const [creating, setCreating] = useState(false);
  const [pairing, setPairing] = useState(null);

  useFocusEffect(useCallback(() => { summary.refresh(); }, [summary.refresh]));
  const pull = usePullRefresh(summary.refresh);
  const reaching = !summary.data && summary.loading;
  const holding = useBusyVisible(reaching);

  const rows = summary.data?.connections ?? [];
  const host = rows.find((r) => r.id === 'host');
  const paired = rows.filter((r) => r.id !== 'host');

  const contentStyle = settingsContentStyle(twoPane);

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader
        title="Connections"
        subtitle="DAEMON · PAIRED APPS"
        onBack={goBack}
        right={<Button title="New" size="md" onPress={() => setCreating(true)} />}
      />
      <SyncBar syncing={summary.loading} />
      {reaching || holding ? (
        <Busy fill visible={holding} label="Reaching the daemon" />
      ) : !summary.data && summary.error ? (
        <LoadFailed label="connections" error={summary.error} onRetry={() => summary.refresh?.()} />
      ) : (
        <ScrollView
          contentContainerStyle={contentStyle}
          refreshControl={<RefreshControl refreshing={pull.refreshing} onRefresh={pull.onRefresh} tintColor={colors.ink3} />}
        >
          {host ? (
            <>
              <SectionHeader first kicker="local socket · setup, TUI, CLI">Host</SectionHeader>
              <RowGroup>
                <Row
                  label="Local host"
                  item
                  helper={`${host.sessions ?? 0} sessions · seen ${relativeSeen(host.last_seen)}`}
                  value={formatUsd(host.cost_14d)}
                  onPress={() => router.push('/connections/host')}
                />
              </RowGroup>
            </>
          ) : null}
          <SectionHeader first={!host} kicker={`${paired.length} paired`}>Connections</SectionHeader>
          <RowGroup>
            {paired.length === 0 ? (
              <Row
                label={EMPTY.connections.title}
                helper={EMPTY.connections.hint}
                chevron={false}
              />
            ) : (
              paired.map((row, i) => (
                <View key={row.id}>
                  {i > 0 ? <RowSeparator /> : null}
                  <Row
                    label={row.label || row.id}
                    item
                    helper={connectionMeta(row)}
                    value={
                      row.status === 'disabled'
                        ? <Pill tone="warn">disabled</Pill>
                        : formatUsd(row.cost_14d)
                    }
                    onPress={() => router.push(`/connections/${row.id}`)}
                  />
                </View>
              ))
            )}
          </RowGroup>
        </ScrollView>
      )}

      <NewConnectionSheet
        open={creating}
        onClose={() => setCreating(false)}
        onCreated={(payload) => {
          summary.refresh();
          setPairing(payload);
        }}
      />
      <PairingSheet
        open={!!pairing}
        payload={pairing}
        onClose={() => setPairing(null)}
        onSettled={() => summary.refresh()}
      />
    </SafeAreaView>
  );
}
