import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { space } from '../../../../src/theme/tokens';

import { Button } from '../../../../src/components/Button';
import { Pill } from '../../../../src/components/Pill';
import { Row, RowSeparator, SectionHeader } from '../../../../src/components/Row';
import { Sheet } from '../../../../src/components/Sheet';
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
  const [tools, setTools] = useState(null);
  const [toolsError, setToolsError] = useState(null);

  // Daemon profile summary uses `mcps` (alpi/host/device_state.py::_mcp_servers). Each entry: {name, command, args[], env_keys[]}.
  const servers = profile?.mcps ?? [];

  useEffect(() => {
    if (!target) return undefined;
    const name = target.name;
    let cancelled = false;
    setTools(null);
    setToolsError(null);
    call('host.mcp.tools', { profile: id, name })
      .then((res) => { if (!cancelled) setTools(res?.tools ?? []); })
      .catch((e) => { if (!cancelled) { setToolsError(String(e)); setTools([]); } });
    return () => { cancelled = true; };
  }, [target?.name, id, call]);

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
      <Sheet
        open={!!target}
        onClose={() => setTarget(null)}
        title={target?.name ?? ''}
        subtitle={target ? `${target.command} ${(target.args ?? []).join(' ')}` : ''}
        primaryAction={
          target
            ? {
                label: 'Remove server',
                variant: 'danger',
                onPress: () => {
                  const name = target.name;
                  setTarget(null);
                  setConfirmRemove(name);
                },
              }
            : undefined
        }
      >
        <ScrollView contentContainerStyle={{ paddingBottom: space.s6 }}>
          {(target?.env_keys ?? []).length > 0 ? (
            <View
              style={{
                flexDirection: 'row',
                flexWrap: 'wrap',
                gap: space.s2,
                paddingHorizontal: space.s8,
                paddingBottom: space.s5,
              }}
            >
              {target.env_keys.map((k) => (
                <Pill key={k} tone="on">{k}</Pill>
              ))}
            </View>
          ) : null}
          <SectionHeader>
            {`tools${Array.isArray(tools) && tools.length ? ` · ${tools.length}` : ''}`}
          </SectionHeader>
          {tools === null ? (
            <View
              style={{
                flexDirection: 'row',
                alignItems: 'center',
                gap: space.s3,
                paddingHorizontal: space.s8,
                paddingVertical: space.s4,
              }}
            >
              <ActivityIndicator color={colors.ink3} />
              <Text style={{ fontFamily: fonts.sans.regular, color: colors.ink3, fontSize: fontSizes.sm }}>handshaking with server…</Text>
            </View>
          ) : toolsError ? (
            <Text
              style={{
                fontFamily: fonts.sans.regular,
                color: colors.danger,
                fontSize: fontSizes.sm,
                paddingHorizontal: space.s8,
                paddingVertical: space.s3,
              }}
            >
              {toolsError}
            </Text>
          ) : tools.length === 0 ? (
            <Text
              style={{
                fontFamily: fonts.sans.regular,
                color: colors.ink3,
                fontSize: fontSizes.sm,
                paddingHorizontal: space.s8,
                paddingVertical: space.s3,
              }}
            >
              no tools
            </Text>
          ) : (
            tools.map((t) => (
              <View key={t.name} style={{ paddingHorizontal: space.s8, paddingVertical: space.s3, gap: 2 }}>
                <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.ink }}>{t.name}</Text>
                {t.description ? (
                  <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.xs, color: colors.ink3, lineHeight: fontSizes.xs * 1.4 }}>
                    {t.description}
                  </Text>
                ) : null}
              </View>
            ))
          )}
        </ScrollView>
      </Sheet>
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
