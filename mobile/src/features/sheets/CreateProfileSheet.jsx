import { usePathname, useRouter } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { Pressable, ScrollView, View } from 'react-native';
import { mobile, space } from '../../theme/tokens';

import { Field, FieldLabel } from '../../components/Field';
import { Pill } from '../../components/Pill';
import { Sheet } from '../../components/Sheet';
import { useToast } from '../../components/Toast';
import { useProfileSummaries } from '../../hooks/useDaemonData';
import { createProfileWithProvider } from '../../lib/createProfile';
import { useEndpoint } from '../../lib/EndpointContext';
import { openVerb } from '../../lib/panes';
import { profileNameError } from '../../lib/profileName';
import { CLOUD_PROVIDERS } from '../../lib/providers';
import { usePane } from '../../nav/PaneContext';

const PROVIDERS = [{ id: 'ollama', label: 'Ollama' }, ...CLOUD_PROVIDERS];

const DEFAULT_OLLAMA_NAME = 'local';
const DEFAULT_OLLAMA_URL = 'http://localhost:11434';
const OLLAMA_NAME_RE = /^[a-z0-9_-]+$/;

export function CreateProfileSheet({ open, onClose }) {
  const router = useRouter();
  const pathname = usePathname();
  const { twoPane } = usePane();
  const toast = useToast();
  const { call } = useEndpoint();
  const summaries = useProfileSummaries();

  const [name, setName] = useState('');
  const [providerId, setProviderId] = useState('ollama');
  const [ollamaName, setOllamaName] = useState(DEFAULT_OLLAMA_NAME);
  const [ollamaUrl, setOllamaUrl] = useState(DEFAULT_OLLAMA_URL);
  const [apiKey, setApiKey] = useState('');
  const [openrouterModel, setOpenrouterModel] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setName('');
    setProviderId('ollama');
    setOllamaName(DEFAULT_OLLAMA_NAME);
    setOllamaUrl(DEFAULT_OLLAMA_URL);
    setApiKey('');
    setOpenrouterModel('');
    setBusy(false);
  }, [open]);

  const provider = PROVIDERS.find((p) => p.id === providerId);
  const taken = useMemo(
    () => (summaries.data?.profiles ?? []).map((p) => p.name),
    [summaries.data],
  );

  const trimmed = name.trim().toLowerCase();
  const nameError = profileNameError(trimmed, taken);
  const validName = trimmed.length > 0 && nameError === null;

  const validProvider = (() => {
    if (providerId === 'ollama') {
      return OLLAMA_NAME_RE.test(ollamaName.trim()) && ollamaUrl.trim().length > 0;
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
      onClose?.();
      router[openVerb({ twoPane, pathname })](`/profile/${trimmed}/settings`);
    } catch (e) {
      toast({ title: 'Create failed', message: String(e) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="New profile"
      subtitle="NAME · PROVIDER"
      primaryAction={{ label: 'Create', onPress: create, disabled: !ready, loading: busy }}
    >
      <ScrollView
        contentContainerStyle={{ padding: space.s8, gap: space.s9 }}
        keyboardShouldPersistTaps="handled"
      >
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
          <FieldLabel>Provider · pick one to start</FieldLabel>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: space.s2 }}>
            {PROVIDERS.map((p) => {
              const on = providerId === p.id;
              return (
                <Pressable
                  key={p.id}
                  accessibilityLabel={p.label}
                  onPress={() => setProviderId(p.id)}
                  style={{ minHeight: mobile.tap, justifyContent: 'center' }}
                >
                  <Pill tone={on ? 'on' : undefined} off={!on}>● {p.label}</Pill>
                </Pressable>
              );
            })}
          </View>
        </View>

        {providerId === 'ollama' ? (
          <View style={{ gap: space.s5 }}>
            <Field
              label="Name"
              placeholder="local · home-gpu"
              value={ollamaName}
              onChangeText={(t) => setOllamaName(t.replace(/[^a-z0-9_-]/g, ''))}
              mono
              autoCapitalize="none"
              autoCorrect={false}
            />
            <Field
              label="URL"
              placeholder={DEFAULT_OLLAMA_URL}
              value={ollamaUrl}
              onChangeText={setOllamaUrl}
              mono
              autoCapitalize="none"
              autoCorrect={false}
            />
          </View>
        ) : (
          <View style={{ gap: space.s5 }}>
            <Field
              label="API key"
              placeholder={provider?.placeholder}
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
    </Sheet>
  );
}
