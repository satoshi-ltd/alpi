import { useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { radii, space } from '../../src/theme/tokens';

import { formatUsd } from '../../../common/format.mjs';
import { toUsageDays } from '../../../common/usage.mjs';
import { ActionSheet } from '../../src/components/ActionSheet';
import { AdminGuard } from '../../src/components/AdminGuard';
import { Icon } from '../../src/components/Icon';
import { Toggle } from '../../src/components/Toggle';
import { Pill } from '../../src/components/Pill';
import { Row, RowSeparator, SectionHeader, SettingsBand } from '../../src/components/Row';
import { ScreenHeader } from '../../src/components/ScreenHeader';
import { SyncBar } from '../../src/components/SyncBar';
import { TextPrompt } from '../../src/components/TextPrompt';
import { useToast } from '../../src/components/Toast';
import { Bold, Code, TypedConfirm } from '../../src/components/TypedConfirm';
import { UsageChart } from '../../src/components/UsageChart';
import { PairingSheet } from '../../src/features/connections/PairingSheet';
import { ProfilesScopeSheet } from '../../src/features/connections/ProfilesScopeSheet';
import { deviceMeta, deviceTitle, relativeSeen, scopeLabel, sessionScopeLabel } from '../../src/features/connections/format';
import { useBack } from '../../src/hooks/useBack';
import { usePullRefresh } from '../../src/hooks/usePullRefresh';
import { useConnectionsSummary } from '../../src/hooks/useDaemonData';
import { useEndpoint } from '../../src/lib/EndpointContext';
import { usePane } from '../../src/nav/PaneContext';
import { SettingsSurface } from '../../src/nav/SettingsSurface';
import { useTheme } from '../../src/theme/ThemeContext';
import { EMPTY } from '../../../common/emptyCopy.mjs';

const WIDE_BODY_MAX_W = 968;

function RevokeButton({ label, onPress }) {
  const { colors } = useTheme();
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      hitSlop={space.s2}
      style={({ pressed }) => ({
        width: 40,
        height: 40,
        borderRadius: radii.md,
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: pressed ? colors.selected : 'transparent',
      })}
    >
      <Icon name="x" size="md" color={colors.ink2} />
    </Pressable>
  );
}

export default function ConnectionRoute() {
  return (
    <AdminGuard>
      <ConnectionDetail />
    </AdminGuard>
  );
}

function ConnectionDetail() {
  const { id } = useLocalSearchParams();
  const router = useRouter();
  const goBack = useBack();
  const toast = useToast();
  const { call, endpoint } = useEndpoint();
  const { colors } = useTheme();
  const { twoPane } = usePane();
  const summary = useConnectionsSummary();
  const pull = usePullRefresh(summary.refresh);
  const [prompt, setPrompt] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [addOpen, setAddOpen] = useState(false);
  const [scopeOpen, setScopeOpen] = useState(false);
  const [pairing, setPairing] = useState(null);

  const row = (summary.data?.connections ?? []).find((r) => r.id === id) ?? null;
  const isHost = id === 'host';
  const devices = (row?.devices ?? []).filter((d) => d.status !== 'deleted');
  const usageDays = toUsageDays(row?.usage_days);
  const thisDevice = endpoint?.ownDeviceId ?? null;

  const act = async (method, params, title) => {
    try {
      const result = await call(method, { connection_id: id, ...params });
      await summary.refresh().catch(() => {});
      toast({ title, duration: 1600 });
      return result;
    } catch (e) {
      toast({ title: `${title} failed`, message: String(e?.data?.detail ?? e), duration: 3200 });
      return null;
    }
  };

  const addDevice = async (provisioner) => {
    setAddOpen(false);
    try {
      const payload = await call('host.connections.add_device', { connection_id: id, provisioner });
      setPairing(payload);
    } catch (e) {
      toast({ title: 'Add device failed', message: String(e?.data?.detail ?? e), duration: 3200 });
    }
  };

  const contentStyle = twoPane
    ? { paddingHorizontal: space.s9, paddingTop: space.s9, paddingBottom: space.s11, maxWidth: WIDE_BODY_MAX_W, width: '100%', alignSelf: 'center' }
    : { paddingBottom: space.s10 };

  if (!row) {
    return (
      <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
        <ScreenHeader title="Connection" subtitle={summary.loading ? 'LOADING' : 'NOT FOUND'} onBack={goBack} />
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          {summary.loading ? <ActivityIndicator color={colors.ink3} /> : null}
        </View>
      </SafeAreaView>
    );
  }

  const disabled = row.status === 'disabled';
  const perDevice = row.session_scope === 'device';
  const isSelf = (!!endpoint?.connectionId && endpoint.connectionId === row.id) || (!!thisDevice && devices.some((d) => d.id === thisDevice));

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader
        title={row.label || row.id}
        subtitle={`CONNECTION · ${String(row.role || 'member').toUpperCase()}`}
        onBack={goBack}
      />
      <SyncBar syncing={summary.loading} />
      <SettingsSurface>
      <ScrollView
        contentContainerStyle={contentStyle}
        refreshControl={<RefreshControl refreshing={pull.refreshing} onRefresh={pull.onRefresh} tintColor={colors.ink3} />}
      >
        <SectionHeader first>Overview</SectionHeader>
        {isHost ? (
          <Row label="Local host" helper="alpi setup, the TUI and the CLI on the daemon's machine" chevron={false} />
        ) : (
          <>
            <Row label="Label" value={row.label || row.id} onPress={() => setPrompt('label')} />
            <RowSeparator />
            <Row
              label="Role"
              helper={row.role === 'admin' ? 'manages profiles and connections' : 'chat + settings of scoped profiles'}
              value={<Pill tone={row.role === 'admin' ? 'warn' : undefined}>{row.role}</Pill>}
              onPress={() => setConfirm('role')}
              chevron={false}
            />
            {row.role !== 'admin' ? (
              <>
                <RowSeparator />
                <Row label="Profiles" helper="blank = all" value={scopeLabel(row)} onPress={() => setScopeOpen(true)} />
                <RowSeparator />
                <Row
                  label="Session scope"
                  helper={perDevice ? 'each device sees only the chats it started' : 'every device sees every chat'}
                  value={sessionScopeLabel(row)}
                  onPress={() => setConfirm('scope')}
                />
              </>
            ) : null}
            <RowSeparator />
            <Row
              label="Enabled"
              helper={
                disabled
                  ? 'devices reconnect with their existing tokens'
                  : isSelf
                    ? 'this phone goes offline with it · an admin elsewhere must re-enable it'
                    : 'every device goes offline · sessions and usage stay'
              }
              value={
                <Toggle
                  on={!disabled}
                  label="Enabled"
                  onChange={async (next) => {
                    if (!next && isSelf) {
                      setConfirm('disable');
                      return false;
                    }
                    const result = await act('host.connections.set_status', { status: next ? 'active' : 'disabled' }, next ? 'Connection enabled' : 'Connection disabled');
                    return result !== null;
                  }}
                />
              }
              chevron={false}
            />
          </>
        )}
        <RowSeparator />
        <Row label="Sessions" value={String(row.sessions ?? 0)} chevron={false} />
        <RowSeparator />
        <Row label="Last seen" value={relativeSeen(row.last_seen)} chevron={false} />

        <SectionHeader kicker="last 14 days">Usage</SectionHeader>
        {usageDays.length ? (
          <SettingsBand>
            <UsageChart days={usageDays} />
          </SettingsBand>
        ) : (
          <Row label={EMPTY.usage.title} value={formatUsd(row.cost_14d)} chevron={false} />
        )}

        {!isHost ? (
          <>
            <SectionHeader kicker={`${devices.length} paired`}>Devices</SectionHeader>
            {devices.length === 0 ? (
              <Row label={EMPTY.devices.title} helper={EMPTY.devices.hint} chevron={false} />
            ) : (
              devices.map((d, i) => (
                <View key={d.id}>
                  {i > 0 ? <RowSeparator /> : null}
                  <Row
                    label={deviceTitle(d)}
                    item
                    helper={deviceMeta(d)}
                    value={d.id === thisDevice ? <Pill tone="on">this phone</Pill> : d.expired ? <Pill tone="warn">expired</Pill> : undefined}
                    trailing={<RevokeButton label={`Revoke ${deviceTitle(d)}`} onPress={() => setConfirm({ revoke: d })} />}
                    chevron={false}
                  />
                </View>
              ))
            )}
            <RowSeparator />
            <Row label="+ Add device" helper="one-time pairing link" onPress={() => setAddOpen(true)} chevron={false} />

            <SectionHeader>Danger zone</SectionHeader>
            <Row
              label="Delete connection"
              helper={isSelf ? 'this phone is paired through it · you would be signed out' : 'revokes every device · sessions and usage stay attributed'}
              danger
              chevron={false}
              onPress={() => setConfirm('delete')}
            />
          </>
        ) : null}
      </ScrollView>
      </SettingsSurface>

      <TextPrompt
        open={prompt === 'label'}
        onClose={() => setPrompt(null)}
        title="Rename connection"
        label="label"
        initialValue={row.label ?? ''}
        maxLength={64}
        confirmLabel="Save"
        onSubmit={(value) => {
          if (!String(value ?? '').trim()) return;
          act('host.connections.update', { label: String(value).trim() }, 'Renamed');
        }}
      />
      <ProfilesScopeSheet
        open={scopeOpen}
        onClose={() => setScopeOpen(false)}
        connection={row}
        onSaved={() => summary.refresh()}
      />
      <ActionSheet
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title="Add device"
        subtitle={row.label || row.id}
        actions={[
          { id: 'device', label: 'Pairing link', icon: <Icon name="link" size="lg" />, onPress: () => addDevice(false) },
          {
            id: 'provisioner',
            label: 'Provisioning link',
            detail: 'can add and revoke sibling devices',
            icon: <Icon name="server" size="lg" />,
            onPress: () => addDevice(true),
          },
        ]}
      />
      <PairingSheet
        open={!!pairing}
        payload={pairing}
        onClose={() => setPairing(null)}
        onSettled={() => summary.refresh()}
      />

      <TypedConfirm
        open={confirm === 'role'}
        onClose={() => setConfirm(null)}
        title={row.role === 'admin' ? 'Demote to member' : 'Promote to admin'}
        body={
          row.role === 'admin' ? (
            <>
              Its devices lose profile management, connections and daemon controls.{' '}
              {isSelf ? <Bold>This phone is one of them and loses this screen.</Bold> : null}
            </>
          ) : (
            <>Its devices can manage every profile, connection and the daemon.</>
          )
        }
        tone="neutral"
        typed={false}
        confirmLabel={row.role === 'admin' ? 'Demote' : 'Promote'}
        onConfirm={() => {
          setConfirm(null);
          act('host.connections.update', { role: row.role === 'admin' ? 'member' : 'admin' }, 'Role changed');
        }}
      />
      <TypedConfirm
        open={confirm === 'scope'}
        onClose={() => setConfirm(null)}
        title={perDevice ? 'Share sessions across devices' : 'Keep sessions private per device'}
        body={
          perDevice ? (
            <>Every device of this connection sees every chat, including ones created while private.</>
          ) : (
            <>Devices stop seeing each other's chats; chats created before this change stay shared.</>
          )
        }
        tone="neutral"
        typed={false}
        confirmLabel={perDevice ? 'Share' : 'Make private'}
        onConfirm={() => {
          setConfirm(null);
          act('host.connections.update', { session_scope: perDevice ? 'connection' : 'device' }, 'Session scope changed');
        }}
      />
      <TypedConfirm
        open={confirm === 'disable'}
        onClose={() => setConfirm(null)}
        title="Disable this connection"
        body={
          <>
            This phone is paired through it: every device goes offline and this phone is signed out until an admin on
            another connection re-enables it. <Bold>Type disable to confirm.</Bold>
          </>
        }
        expected="disable"
        confirmLabel="Disable"
        onConfirm={() => {
          setConfirm(null);
          act('host.connections.set_status', { status: 'disabled' }, 'Connection disabled');
        }}
      />
      <TypedConfirm
        open={!!confirm?.revoke}
        onClose={() => setConfirm(null)}
        title={`Revoke ${deviceTitle(confirm?.revoke)}`}
        body={
          <>
            The device loses access immediately; other devices keep working.{' '}
            {confirm?.revoke?.id === thisDevice ? <Bold>That is this phone.</Bold> : null}
          </>
        }
        expected="revoke"
        confirmLabel="Revoke"
        onConfirm={() => {
          const target = confirm?.revoke;
          setConfirm(null);
          if (target) act('host.connections.revoke_device', { device_id: target.id }, 'Device revoked');
        }}
      />
      <TypedConfirm
        open={confirm === 'delete'}
        onClose={() => setConfirm(null)}
        title={`Delete ${row.label || row.id}`}
        body={
          <>
            Revokes every linked device. Sessions and usage remain attributed to <Code>{row.label || row.id}</Code>.{' '}
            <Bold>This action cannot be undone.</Bold>
          </>
        }
        expected={row.label || row.id}
        confirmLabel="Delete connection"
        onConfirm={async () => {
          setConfirm(null);
          const result = await act('host.connections.delete', {}, 'Connection deleted');
          if (result) router.replace('/connections');
        }}
      />
    </SafeAreaView>
  );
}
