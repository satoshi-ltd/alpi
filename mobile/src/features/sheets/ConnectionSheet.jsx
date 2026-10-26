import { useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { ScrollView, Text, View } from 'react-native';
import { radii, space } from '../../theme/tokens';

import { ActionSheet } from '../../components/ActionSheet';
import { Dot } from '../../components/Dot';
import { Icon } from '../../components/Icon';
import { Row, RowSeparator } from '../../components/Row';
import { Sheet } from '../../components/Sheet';
import { Pill } from '../../components/Pill';
import { TextPrompt } from '../../components/TextPrompt';
import { useToast } from '../../components/Toast';
import { Bold, Code, ConfirmDialog } from '../../components/ConfirmDialog';
import { canUpdateConnection } from '../../lib/connectionUpdate';
import { updateHint } from '../../../../common/updateHint.mjs';
import { useEndpoint } from '../../lib/EndpointContext';
import { sortConnectionsByRecency } from '../../lib/store';
import { call as rpc } from '../../lib/rpc';
import { useTheme } from '../../theme/ThemeContext';

function statusColor(status, colors) {
  if (status === 'online' || status === 'connected') return colors.success;
  if (status === 'offline' || status === 'auth-failed') return colors.danger;
  if (status === 'disabled') return colors.ink3;
  return colors.warning;
}

export function ConnectionSheet({ open, onClose }) {
  const { colors, fonts } = useTheme();
  const router = useRouter();
  const toast = useToast();
  const { connections, activeId, probeState, versionState, updateState, installState, roleState, setActive, rename, forget, probeAll } = useEndpoint();
  const [target, setTarget] = useState(null);
  const [confirmForget, setConfirmForget] = useState(null);
  const [renameTarget, setRenameTarget] = useState(null);

  useEffect(() => {
    if (!open) return;
    probeAll().catch(() => { /* */ });
  }, [open, probeAll]);

  const doUpdate = async (conn) => {
    setTarget(null);
    try {
      const res = await rpc(conn, 'host.daemon.update', {});
      if (res?.updated) {
        toast({ title: 'Updating', message: `${conn.name} → v${res.latest} · daemon restarting` });
      } else if (res?.reason === 'up-to-date') {
        toast({ title: 'Up to date', message: `${conn.name} is on v${res.current}` });
      } else if (res?.reason === 'manual') {
        toast({ title: "Can't self-update", message: updateHint(res.installer, res.latest) });
      } else {
        toast({ title: 'Update failed', message: String(res?.reason || 'unknown') });
      }
      probeAll().catch(() => {});
    } catch (e) {
      toast({ title: 'Update failed', message: String(e) });
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
      subtitle="where alpi runs"
      primaryAction={{ label: 'Pair this phone', onPress: handlePair }}
    >
      <ScrollView>
        {connections.length === 0 ? (
          <View style={{ padding: space.s9, alignItems: 'center' }}>
            <Text style={{ fontFamily: fonts.sans.regular, color: colors.ink3 }}>Not paired yet. Tap below to scan a QR.</Text>
          </View>
        ) : (
          sortConnectionsByRecency(connections).map((c, i) => {
            const status = probeState.get(c.id) ?? 'unknown';
            const version = versionState.get(c.id);
            return (
              <View key={c.id}>
                {i > 0 ? <RowSeparator indent={60} /> : null}
                <Row
                  leading={
                    <View
                      style={{
                        width: 40,
                        height: 40,
                        borderRadius: radii.xs,
                        backgroundColor: colors.bgSide,
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      <Icon name={c.kind === 'remote' ? 'server' : 'cpu'} size="md" color={colors.ink2} />
                      <View style={{ position: 'absolute', bottom: 2, right: 2 }}>
                        <Dot color={statusColor(status, colors)} />
                      </View>
                    </View>
                  }
                  label={c.name}
                  helper={version ? `${c.url} · v${version}` : c.url}
                  value={
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s2 }}>
                      {status === 'disabled' ? (
                        <Pill>disabled</Pill>
                      ) : c.id === activeId ? (
                        <Pill>current</Pill>
                      ) : status === 'offline' ? (
                        <Pill tone="err">offline</Pill>
                      ) : null}
                    </View>
                  }
                  chevron={false}
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
        subtitle={target?.url || ''}
        actions={
          target
            ? [
                ...(canUpdateConnection(roleState.get(target.id), updateState.get(target.id), installState.get(target.id)?.selfUpdate)
                  ? [{
                      id: 'update',
                      label: `Update to v${updateState.get(target.id)}`,
                      icon: <Icon name="download" size="md" color={colors.ink2} />,
                      onPress: () => doUpdate(target),
                    }]
                  : []),
                {
                  id: 'rename',
                  label: 'Rename',
                  icon: <Icon name="edit" size="md" color={colors.ink2} />,
                  onPress: () => {
                    const t = target;
                    setTarget(null);
                    setRenameTarget(t);
                  },
                },
                {
                  id: 'forget',
                  label: 'Forget',
                  danger: true,
                  icon: <Icon name="x" size="md" color={colors.danger} />,
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
      <ConfirmDialog
        open={!!confirmForget}
        onClose={() => setConfirmForget(null)}
        title={`Forget ${confirmForget?.name ?? ''}`}
        body={
          <>
            Removes the pairing token for <Code>{confirmForget?.name}</Code> (<Code>{confirmForget?.url}</Code>). <Bold>You'll need to scan a new QR to reconnect.</Bold>
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
      <TextPrompt
        open={!!renameTarget}
        onClose={() => setRenameTarget(null)}
        title="Rename connection"
        label="NAME ON THIS PHONE ONLY"
        initialValue={renameTarget?.name ?? ''}
        placeholder={renameTarget?.name ?? ''}
        onSubmit={async (name) => {
          const id = renameTarget?.id;
          setRenameTarget(null);
          if (!id) return;
          try {
            await rename(id, name);
          } catch (e) {
            toast({ title: "Couldn't rename", message: e?.message ?? String(e) });
          }
        }}
      />
    </Sheet>
  );
}
