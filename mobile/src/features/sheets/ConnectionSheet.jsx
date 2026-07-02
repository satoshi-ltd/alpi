import { useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { ScrollView, Text, View } from 'react-native';
import { radii, space , fontSizes} from '../../theme/tokens';

import { ActionSheet } from '../../components/ActionSheet';
import { Dot } from '../../components/Dot';
import { Icon } from '../../components/Icon';
import { Row, RowSeparator } from '../../components/Row';
import { Sheet } from '../../components/Sheet';
import { useToast } from '../../components/Toast';
import { Bold, Code, TypedConfirm } from '../../components/TypedConfirm';
import { canUpdateConnection } from '../../lib/connectionUpdate';
import { useEndpoint } from '../../lib/EndpointContext';
import { sortConnectionsByRecency } from '../../lib/store';
import { call as rpc } from '../../lib/rpc';
import { useTheme } from '../../theme/ThemeContext';

function statusColor(status, colors) {
  if (status === 'online' || status === 'connected') return colors.success;
  if (status === 'offline' || status === 'auth-failed') return colors.danger;
  return colors.warning;
}

function Tag({ label, tone }) {
  const { colors, fonts, fontSizes } = useTheme();
  const bg = tone === 'danger' ? `${colors.danger}22` : tone === 'warn' ? `${colors.warning}22` : colors.hover;
  const fg = tone === 'danger' ? colors.danger : tone === 'warn' ? colors.warning : colors.ink2;
  return (
    <View style={{ paddingHorizontal: space.s3, paddingVertical: space.s1, borderRadius: radii.sm, backgroundColor: bg }}>
      <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: fg }}>{label}</Text>
    </View>
  );
}

export function ConnectionSheet({ open, onClose }) {
  const { colors } = useTheme();
  const router = useRouter();
  const toast = useToast();
  const { connections, activeId, probeState, versionState, updateState, roleState, setActive, forget, probeAll } = useEndpoint();
  const [target, setTarget] = useState(null);
  const [confirmForget, setConfirmForget] = useState(null);

  useEffect(() => {
    if (!open) return;
    probeAll().catch(() => { /* */ });
  }, [open, probeAll]);

  const doUpdate = async (conn) => {
    setTarget(null);
    try {
      const res = await rpc(conn, 'host.daemon.update', {});
      if (res?.updated) {
        toast({ title: 'Updating', message: `${conn.name} → v${res.latest} · daemon restarting`, duration: 3000 });
      } else if (res?.reason === 'up-to-date') {
        toast({ title: 'Up to date', message: `${conn.name} is on v${res.current}`, duration: 2000 });
      } else if (res?.reason === 'manual') {
        toast({ title: "Can't self-update", message: 'Image-pinned (Docker) — repull the image to update.', duration: 4000 });
      } else {
        toast({ title: 'Update failed', message: String(res?.reason || 'unknown'), duration: 4000 });
      }
      probeAll().catch(() => {});
    } catch (e) {
      toast({ title: 'Update failed', message: String(e), duration: 4000 });
    }
  };

  const handlePair = () => {
    onClose?.();
    router.push('/pair');
  };

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Connection"
      subtitle="WHERE ALPI RUNS"
      primaryAction={{ label: 'Pair this phone', onPress: handlePair }}
    >
      <ScrollView>
        {connections.length === 0 ? (
          <View style={{ padding: space.s9, alignItems: 'center' }}>
            <Text style={{ color: colors.ink3 }}>Not paired yet — tap below to scan a QR.</Text>
          </View>
        ) : (
          sortConnectionsByRecency(connections).map((c, i) => {
            const status = probeState.get(c.id) ?? 'unknown';
            const version = versionState.get(c.id);
            const upd = updateState.get(c.id);
            return (
              <View key={c.id}>
                {i > 0 ? <RowSeparator indent={60} /> : null}
                <Row
                  leading={
                    <View
                      style={{
                        width: 40,
                        height: 40,
                        borderRadius: 20,
                        backgroundColor: colors.bgSide,
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      <Icon name={c.kind === 'remote' ? 'server' : 'cpu'} size={20} color={colors.ink2} />
                      <View style={{ position: 'absolute', bottom: 2, right: 2 }}>
                        <Dot color={statusColor(status, colors)} />
                      </View>
                    </View>
                  }
                  label={c.name}
                  helper={version ? `${c.ip}:${c.port} · v${version}` : `${c.ip}:${c.port}`}
                  value={
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s2 }}>
                      {upd ? <Tag label="update" tone="warn" /> : null}
                      {c.id === activeId ? (
                        <Tag label="current" />
                      ) : status === 'offline' ? (
                        <Tag label="offline" tone="danger" />
                      ) : null}
                    </View>
                  }
                  chevron={false}
                  // Tap = switch to this daemon. Long-press = open actions (only "Forget" lives there now, but that pattern leaves room for more later — same affordance schedule uses).
                  onPress={() => {
                    setActive(c.id);
                    onClose?.();
                  }}
                  onLongPress={() => setTarget(c)}
                />
              </View>
            );
          })
        )}
      </ScrollView>
      <ActionSheet
        open={!!target}
        onClose={() => setTarget(null)}
        title={target?.name ?? ''}
        subtitle={target ? `${target.ip}:${target.port}` : ''}
        actions={
          target
            ? [
                ...(canUpdateConnection(roleState.get(target.id), updateState.get(target.id))
                  ? [{
                      id: 'update',
                      label: `Update to v${updateState.get(target.id)}`,
                      icon: <Icon name="download" size={20} color={colors.ink2} />,
                      onPress: () => doUpdate(target),
                    }]
                  : []),
                {
                  id: 'forget',
                  label: 'Forget',
                  danger: true,
                  icon: <Icon name="x" size={20} color={colors.danger} />,
                  onPress: () => {
                    const t = target;
                    setTarget(null);
                    setConfirmForget(t);
                  },
                },
              ]
            : []
        }
      />
      <TypedConfirm
        open={!!confirmForget}
        onClose={() => setConfirmForget(null)}
        title={`Forget ${confirmForget?.name ?? ''}`}
        body={
          <>
            Removes the pairing token for <Code>{confirmForget?.name}</Code> (<Code>{confirmForget?.ip}:{confirmForget?.port}</Code>). <Bold>You'll need to scan a new QR to reconnect.</Bold>
          </>
        }
        expected={confirmForget?.name ?? ''}
        confirmLabel="Forget daemon"
        onConfirm={() => {
          const id = confirmForget?.id;
          setConfirmForget(null);
          if (id) forget(id);
        }}
      />
    </Sheet>
  );
}
