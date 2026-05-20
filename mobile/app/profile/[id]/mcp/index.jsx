import { useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { space , fontSizes} from '../../../../src/theme/tokens';

import { ActionSheet } from '../../../../src/components/ActionSheet';
import { Button } from '../../../../src/components/Button';
import { Icon } from '../../../../src/components/Icon';
import { Pill } from '../../../../src/components/Pill';
import { Row, RowSeparator } from '../../../../src/components/Row';
import { ScreenHeader } from '../../../../src/components/ScreenHeader';
import { useToast } from '../../../../src/components/Toast';
import { Bold, Code, TypedConfirm } from '../../../../src/components/TypedConfirm';
import { useProfile } from '../../../../src/hooks/useSubject';
import { useEndpoint } from '../../../../src/lib/EndpointContext';
import { useTheme } from '../../../../src/theme/ThemeContext';

export default function McpList() {
  const { id } = useLocalSearchParams();
  const router = useRouter();
  const toast = useToast();
  const { call } = useEndpoint();
  const { colors, fonts, fontSizes } = useTheme();
  const { profile, loading, refresh } = useProfile(id);
  const [target, setTarget] = useState(null);
  const [confirmRemove, setConfirmRemove] = useState(null);

  // Daemon profile summary uses `mcps` (alpi/host/device_state.py::_mcp_servers). Each entry: {name, command, args[], env_keys[]}.
  const servers = profile?.mcps ?? [];

  const remove = async (name) => {
    try {
      await call('host.mcp.remove', { profile: id, name });
      toast({ title: 'Removed', message: name });
      refresh();
    } catch (e) {
      toast({ title: 'Remove failed', message: String(e) });
    }
  };

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader
        title="MCP servers"
        subtitle={`@${id} · ${servers.length} REGISTERED`}
        onBack={() => router.back()}
        right={<Button title="+ Add" size="md" variant="ghost" onPress={() => router.push(`/profile/${id}/mcp/new`)} />}
      />
      <ScrollView>
        {loading && servers.length === 0 ? (
          <View style={{ padding: space.s10, alignItems: 'center' }}>
            <ActivityIndicator color={colors.ink3} />
          </View>
        ) : servers.length === 0 ? (
          <Row label="No MCP servers configured" helper="tap + Add to connect one" chevron={false} />
        ) : (
          servers.map((s, i) => {
            const argLine = (s.args ?? []).join(' ');
            return (
              <View key={s.name}>
                {i > 0 ? <RowSeparator /> : null}
                <Pressable
                  onPress={() => setTarget(s)}
                  android_ripple={{ color: colors.selected }}
                  style={({ pressed }) => ({
                    paddingHorizontal: space.s8,
                    paddingVertical: space.s6,
                    gap: space.s1,
                    backgroundColor: pressed ? colors.selected : 'transparent',
                  })}
                >
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s3 }}>
                    <Text style={{ flex: 1, fontFamily: fonts.sans.semibold, fontSize: fontSizes.lg, color: colors.ink }}>
                      {s.name}
                    </Text>
                    {(s.env_keys ?? []).length > 0 ? (
                      <Pill tone="on">{s.env_keys.length} env</Pill>
                    ) : null}
                  </View>
                  <Text
                    numberOfLines={1}
                    ellipsizeMode="tail"
                    style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}
                  >
                    {s.command} {argLine}
                  </Text>
                </Pressable>
              </View>
            );
          })
        )}
      </ScrollView>
      <ActionSheet
        open={!!target}
        onClose={() => setTarget(null)}
        title={target?.name ?? ''}
        subtitle={target ? `${target.command} ${(target.args ?? []).join(' ')}` : ''}
        actions={
          target
            ? [
                {
                  id: 'remove',
                  label: 'Remove',
                  danger: true,
                  icon: <Icon name="x" size={20} color={colors.danger} />,
                  onPress: () => {
                    const name = target.name;
                    setTarget(null);
                    setConfirmRemove(name);
                  },
                },
              ]
            : []
        }
      />
      <TypedConfirm
        open={!!confirmRemove}
        onClose={() => setConfirmRemove(null)}
        title={`Remove MCP ${confirmRemove ?? ''}`}
        body={
          <>
            Detaches <Code>{confirmRemove}</Code> from this profile. The daemon stops launching it as a subprocess and the tools it exposed disappear. <Bold>Re-add manually to bring it back.</Bold>
          </>
        }
        expected={confirmRemove ?? ''}
        confirmLabel="Remove server"
        onConfirm={() => {
          const name = confirmRemove;
          setConfirmRemove(null);
          remove(name);
        }}
      />
    </SafeAreaView>
  );
}
