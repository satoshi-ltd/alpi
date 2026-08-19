// Daemon: host.mcp.add({profile, name, command, args:[], env:{}}). stdio transport only — daemon pipes JSON-RPC over subprocess stdin/stdout.

import { useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { ScrollView, Text, View } from 'react-native';
import { KeyboardPane } from '../../../../src/components/KeyboardPane';
import { SafeAreaView } from 'react-native-safe-area-context';
import { space } from '../../../../src/theme/tokens';

import { Button } from '../../../../src/components/Button';
import { Field } from '../../../../src/components/Field';
import { ScreenHeader } from '../../../../src/components/ScreenHeader';
import { useToast } from '../../../../src/components/Toast';
import { useBack } from '../../../../src/hooks/useBack';
import { useEndpoint } from '../../../../src/lib/EndpointContext';
import { useTheme } from '../../../../src/theme/ThemeContext';

// Naive shell-quote split — handles "a b" / 'a b' grouping. Daemon receives JSON list as-is.
function splitArgs(s) {
  const out = [];
  const re = /"([^"\\]*(?:\\.[^"\\]*)*)"|'([^'\\]*(?:\\.[^'\\]*)*)'|(\S+)/g;
  let m;
  while ((m = re.exec(s)) !== null) {
    out.push((m[1] ?? m[2] ?? m[3]).replace(/\\(.)/g, '$1'));
  }
  return out;
}

function parseEnv(text) {
  const out = {};
  for (const line of (text || '').split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#') || !trimmed.includes('=')) continue;
    const eq = trimmed.indexOf('=');
    const key = trimmed.slice(0, eq).trim();
    const value = trimmed.slice(eq + 1).trim();
    if (key) out[key] = value;
  }
  return out;
}

export default function NewMcp() {
  const { id } = useLocalSearchParams();
  const goBack = useBack();
  const toast = useToast();
  const { call } = useEndpoint();
  const { colors, fonts, fontSizes } = useTheme();
  const [name, setName] = useState('');
  const [command, setCommand] = useState('');
  const [argsRaw, setArgsRaw] = useState('');
  const [envRaw, setEnvRaw] = useState('');
  const [busy, setBusy] = useState(false);

  const trimmedName = name.trim();
  const trimmedCmd = command.trim();
  const validName = /^[a-z0-9_-]+$/.test(trimmedName);
  const ready = validName && trimmedCmd.length > 0 && !busy;

  const save = async () => {
    if (!ready) return;
    setBusy(true);
    try {
      await call('host.mcp.add', {
        profile: id,
        name: trimmedName,
        command: trimmedCmd,
        args: splitArgs(argsRaw),
        env: parseEnv(envRaw),
      });
      toast({ title: 'MCP added', message: trimmedName });
      goBack();
    } catch (e) {
      toast({ title: 'Add failed', message: String(e) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader
        title="Add MCP server"
        subtitle={`@${id} · CONNECT TOOLSET`}
        onBack={goBack}
        right={<Button title="Add" size="md" disabled={!ready} loading={busy} onPress={save} />}
      />
      <KeyboardPane>
        <ScrollView contentContainerStyle={{ padding: space.s8, gap: space.s8 }} keyboardShouldPersistTaps="handled">
          <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink3, lineHeight: fontSizes.sm * 1.5 }}>
            Example — GitHub MCP: command <Text style={{ fontFamily: fonts.mono }}>npx</Text>, args{' '}
            <Text style={{ fontFamily: fonts.mono }}>-y @modelcontextprotocol/server-github</Text>, env{' '}
            <Text style={{ fontFamily: fonts.mono }}>GITHUB_TOKEN=ghp_…</Text>
          </Text>

          <Field
            label="Name"
            value={name}
            onChangeText={(t) => setName(t.replace(/[^a-z0-9_-]/g, ''))}
            placeholder="github · notion · linear"
            mono
            autoCapitalize="none"
            autoCorrect={false}
            helper="lowercase id — used as `mcp_<name>__<tool>` tool prefix"
          />

          <Field
            label="Command"
            value={command}
            onChangeText={setCommand}
            placeholder="npx · uvx · python · /path/to/server"
            mono
            autoCapitalize="none"
            autoCorrect={false}
          />

          <Field
            label="Args"
            value={argsRaw}
            onChangeText={setArgsRaw}
            placeholder='-y @modelcontextprotocol/server-github'
            mono
            autoCapitalize="none"
            autoCorrect={false}
            helper="space-separated · use double quotes for grouping"
          />

          <Field
            label="Env (KEY=VALUE per line)"
            value={envRaw}
            onChangeText={setEnvRaw}
            multiline
            rows={4}
            placeholder={'GITHUB_TOKEN=ghp_xxx\nFOO=bar'}
            mono
            autoCapitalize="none"
            autoCorrect={false}
            helper="env values are stored encrypted on the daemon and never read back"
          />
        </ScrollView>
      </KeyboardPane>
    </SafeAreaView>
  );
}
