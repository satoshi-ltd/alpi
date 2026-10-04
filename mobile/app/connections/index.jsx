import { useFocusEffect, useRouter } from 'expo-router';
import { useCallback, useState } from 'react';
import { ActivityIndicator, RefreshControl, ScrollView, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { space } from '../../src/theme/tokens';

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
import { usePane } from '../../src/nav/PaneContext';
import { SettingsSurface } from '../../src/nav/SettingsSurface';
import { useTheme } from '../../src/theme/ThemeContext';
import { LoadFailed } from '../../src/components/LoadFailed';
import { EMPTY } from '../../../common/emptyCopy.mjs';

const WIDE_BODY_MAX_W = 968;

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

  const rows = summary.data?.connections ?? [];
  const host = rows.find((r) => r.id === 'host');
  const paired = rows.filter((r) => r.id !== 'host');

  const contentStyle = twoPane
    ? { paddingHorizontal: space.s9, paddingTop: space.s9, paddingBottom: space.s11, maxWidth: WIDE_BODY_MAX_W, width: '100%', alignSelf: 'center' }
    : { paddingBottom: space.s10 };

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader
        title="Connections"
        subtitle="DAEMON · PAIRED APPS"
        onBack={goBack}
        right={<Button title="New" size="md" onPress={() => setCreating(true)} />}
      />
      <SyncBar syncing={summary.loading} />
      {!summary.data && summary.loading ? (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <ActivityIndicator color={colors.ink3} />
        </View>
      ) : !summary.data && summary.error ? (
        <LoadFailed label="connections" error={summary.error} onRetry={() => summary.refresh?.()} />
      ) : (
        <SettingsSurface>
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
        </SettingsSurface>
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
