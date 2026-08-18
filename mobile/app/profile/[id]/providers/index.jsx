import { useLocalSearchParams, useRouter } from 'expo-router';
import { useMemo } from 'react';
import { ActivityIndicator, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { space } from '../../../../src/theme/tokens';

import { Pill } from '../../../../src/components/Pill';
import { Row, RowSeparator, SectionHeader } from '../../../../src/components/Row';
import { ScreenHeader } from '../../../../src/components/ScreenHeader';
import { useOllamaModels } from '../../../../src/hooks/useDaemonData';
import { useProfile } from '../../../../src/hooks/useSubject';
import { useTheme } from '../../../../src/theme/ThemeContext';

const CLOUD = [
  { id: 'anthropic', label: 'Anthropic', env: 'ANTHROPIC_API_KEY' },
  { id: 'openai', label: 'OpenAI', env: 'OPENAI_API_KEY' },
  { id: 'openrouter', label: 'OpenRouter', env: 'OPENROUTER_API_KEY' },
  { id: 'gemini', label: 'Google Gemini', env: 'GEMINI_API_KEY' },
];

export default function ProvidersList() {
  const { id } = useLocalSearchParams();
  const router = useRouter();
  const { colors, fonts, fontSizes } = useTheme();
  const { profile } = useProfile(id);
  const ollamaModels = useOllamaModels(id);

  const providerKeys = profile?.provider_keys ?? [];
  const ollamas = profile?.provider_ollama ?? [];
  const keySet = new Set(providerKeys.map((k) => k.env));

  // Models are prefixed `<ollama-name>/<model:tag>` (alpi/host/device_state.py::_ollama_models). Build a per-server count map so each row can label its reachable count without re-fetching.
  const modelsByName = useMemo(() => {
    const out = new Map();
    for (const m of ollamaModels.data?.models ?? []) {
      const slash = m.indexOf('/');
      if (slash < 0) continue;
      const name = m.slice(0, slash);
      out.set(name, (out.get(name) ?? 0) + 1);
    }
    return out;
  }, [ollamaModels.data]);

  // Daemon (alpi 0.4.48+) returns errors[{name,url,detail}] when a server is unreachable so we can show *why* it failed instead of a silent empty count.
  const errorsByName = useMemo(() => {
    const out = new Map();
    for (const e of ollamaModels.data?.errors ?? []) {
      out.set(e.name, e);
    }
    return out;
  }, [ollamaModels.data]);

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader title="Providers" subtitle={`@${id} · LLM API KEYS + LOCAL`} onBack={() => router.back()} />
      <ScrollView>
        <SectionHeader>Ollama · local</SectionHeader>
        {ollamas.length === 0 ? (
          <Row label="No Ollama instance" helper="local LLMs — runs on the daemon host" chevron={false} />
        ) : (
          ollamas.map((o, i) => {
            const reachableCount = modelsByName.get(o.name);
            const err = errorsByName.get(o.name);
            const value = ollamaModels.loading
              ? <ActivityIndicator color={colors.ink3} size="small" />
              : reachableCount != null && reachableCount > 0
                ? <Pill tone="on">{reachableCount} model{reachableCount === 1 ? '' : 's'}</Pill>
                : <Pill off>unreachable</Pill>;
            const helper = err ? `${o.url} · ${err.detail}` : o.url;
            return (
              <View key={o.name}>
                {i > 0 ? <RowSeparator /> : null}
                <Row
                  label={`ollama/${o.name}`}
                  helper={helper}
                  value={value}
                  onPress={() => router.push(`/profile/${id}/providers/ollama-${o.name}`)}
                />
              </View>
            );
          })
        )}
        <RowSeparator />
        <Row label="+ Add Ollama instance" onPress={() => router.push(`/profile/${id}/providers/ollama-new`)} />

        <SectionHeader>Cloud providers</SectionHeader>
        {CLOUD.map((p, i) => {
          const set = keySet.has(p.env);
          return (
            <View key={p.id}>
              {i > 0 ? <RowSeparator /> : null}
              <Row
                label={p.label}
                helper={p.env}
                value={set ? <Pill tone="on">set</Pill> : <Pill off>not set</Pill>}
                onPress={() => router.push(`/profile/${id}/providers/${p.id}`)}
              />
            </View>
          );
        })}

        <View style={{ height: 16 }} />
        <Text style={{ paddingHorizontal: space.s8, fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink4, lineHeight: fontSizes.xs * 1.5 }}>
          Cloud keys are stored encrypted on the daemon's <Text style={{ color: colors.ink2 }}>.env</Text>. Ollama URLs must be reachable from the daemon host, not from this phone.
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}
