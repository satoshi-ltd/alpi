import { useRouter } from 'expo-router';
import { useMemo, useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { space , fontSizes} from '../../src/theme/tokens';

import { Button } from '../../src/components/Button';
import { Field } from '../../src/components/Field';
import { Pill } from '../../src/components/Pill';
import { ScreenHeader } from '../../src/components/ScreenHeader';
import { useToast } from '../../src/components/Toast';
import { useProfileSummaries } from '../../src/hooks/useDaemonData';
import { useEndpoint } from '../../src/lib/EndpointContext';
import { profileNameError } from '../../src/lib/profileName';
import { createProfileWithProvider } from '../../src/lib/createProfile';
import { useTheme } from '../../src/theme/ThemeContext';
import { AdminGuard } from '../../src/components/AdminGuard';

const PROVIDERS = [
  { id: 'ollama', label: 'Ollama' },
  { id: 'anthropic', label: 'Anthropic', env: 'ANTHROPIC_API_KEY', placeholder: 'sk-ant-…' },
  { id: 'openai', label: 'OpenAI', env: 'OPENAI_API_KEY', placeholder: 'sk-…' },
  { id: 'openrouter', label: 'OpenRouter', env: 'OPENROUTER_API_KEY', placeholder: 'sk-or-…' },
  { id: 'gemini', label: 'Gemini', env: 'GEMINI_API_KEY', placeholder: 'AIza…' },
];

export default function NewProfileRoute() {
  return (
    <AdminGuard>
      <NewProfile />
    </AdminGuard>
  );
}

function NewProfile() {
  const router = useRouter();
  const toast = useToast();
  const { call } = useEndpoint();
  const summaries = useProfileSummaries();
  const { colors, fonts, fontSizes } = useTheme();

  const [name, setName] = useState('');
  const [providerId, setProviderId] = useState('ollama');
  const [ollamaName, setOllamaName] = useState('local');
  const [ollamaUrl, setOllamaUrl] = useState('http://localhost:11434');
  const [apiKey, setApiKey] = useState('');
  const [openrouterModel, setOpenrouterModel] = useState('');
  const [busy, setBusy] = useState(false);

  const provider = PROVIDERS.find((p) => p.id === providerId);
  const taken = useMemo(
    () => new Set((summaries.data?.profiles ?? []).map((p) => p.name)),
    [summaries.data],
  );

  const trimmed = name.trim().toLowerCase();
  const nameError = profileNameError(trimmed, [...taken]);
  const validName = trimmed.length > 0 && nameError === null;

  const validProvider = (() => {
    if (providerId === 'ollama') {
      return ollamaName.trim().length > 0 && /^[a-z0-9_-]+$/.test(ollamaName.trim()) && ollamaUrl.trim().length > 0;
    }
    if (providerId === 'openrouter') {
      return apiKey.trim().length > 0 && openrouterModel.trim().length > 0;
    }
    return apiKey.trim().length > 0;
  })();

  const ready = validName && validProvider && !busy;

  const create = async () => {
    if (!ready) return;
    setBusy(true);
    try {
      await createProfileWithProvider(call, {
        name: trimmed,
        providerId,
        env: provider?.env,
        apiKey,
        ollamaName,
        ollamaUrl,
        openrouterModel,
      });

      await summaries.refresh?.();
      toast({ title: 'Profile created', message: `@${trimmed}`, duration: 1800 });
      router.replace(`/profile/${trimmed}/settings`);
    } catch (e) {
      toast({ title: 'Create failed', message: String(e) });
      setBusy(false);
    }
  };

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader
        title="New profile"
        subtitle="NAME · PROVIDER"
        onBack={() => router.back()}
        right={<Button title="Create" size="md" onPress={create} disabled={!ready} loading={busy} />}
      />
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={{ padding: space.s8, gap: space.s9 }} keyboardShouldPersistTaps="handled">
          <Field
            label="Name"
            placeholder="work · personal · home-server"
            value={name}
            onChangeText={(t) => setName(t.replace(/[^a-zA-Z0-9._-]/g, '').toLowerCase())}
            mono
            autoCapitalize="none"
            autoCorrect={false}
            helper={nameError ?? 'Configure workspace, accent, peers, etc. after.'}
          />

          <View style={{ gap: space.s4 }}>
            <Text
              style={{
                fontFamily: fonts.mono,
                fontSize: fontSizes.xs,
                color: colors.ink3,
                letterSpacing: 0.6,
                textTransform: 'uppercase',
              }}
            >
              Provider · pick one to start
            </Text>
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: space.s2 }}>
              {PROVIDERS.map((p) => {
                const on = providerId === p.id;
                return (
                  <Pressable key={p.id} onPress={() => setProviderId(p.id)} hitSlop={4}>
                    <Pill tone={on ? 'on' : undefined} off={!on}>● {p.label}</Pill>
                  </Pressable>
                );
              })}
            </View>
          </View>

          {providerId === 'ollama' ? (
            <View style={{ flexDirection: 'row', gap: space.s4 }}>
              <View style={{ flex: 1 }}>
                <Field
                  label="Name"
                  placeholder="local · home-gpu"
                  value={ollamaName}
                  onChangeText={(t) => setOllamaName(t.replace(/[^a-z0-9_-]/g, ''))}
                  mono
                  autoCapitalize="none"
                  autoCorrect={false}
                />
              </View>
              <View style={{ flex: 1.4 }}>
                <Field
                  label="URL"
                  placeholder="http://localhost:11434"
                  value={ollamaUrl}
                  onChangeText={setOllamaUrl}
                  mono
                  autoCapitalize="none"
                  autoCorrect={false}
                />
              </View>
            </View>
          ) : (
            <View style={{ gap: space.s5 }}>
              <Field
                label="API key"
                placeholder={provider.placeholder}
                value={apiKey}
                onChangeText={setApiKey}
                mono
                autoCapitalize="none"
                autoCorrect={false}
                helper="Stored encrypted on the daemon's .env"
              />
              {providerId === 'openrouter' ? (
                <Field
                  label="Initial model"
                  placeholder="anthropic/claude-sonnet-4.5"
                  value={openrouterModel}
                  onChangeText={setOpenrouterModel}
                  mono
                  autoCapitalize="none"
                  autoCorrect={false}
                  helper="Pick more later from Providers · OpenRouter"
                />
              ) : null}
            </View>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
