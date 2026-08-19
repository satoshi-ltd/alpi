import { useLocalSearchParams } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { KeyboardPane } from '../../../../src/components/KeyboardPane';
import { SafeAreaView } from 'react-native-safe-area-context';
import { radii, space } from '../../../../src/theme/tokens';

import { Button } from '../../../../src/components/Button';
import { Field } from '../../../../src/components/Field';
import { Eyebrow } from '../../../../src/components/Eyebrow';
import { Icon } from '../../../../src/components/Icon';
import { Pill } from '../../../../src/components/Pill';
import { Row, RowSeparator, SectionHeader } from '../../../../src/components/Row';
import { ScreenHeader } from '../../../../src/components/ScreenHeader';
import { useToast } from '../../../../src/components/Toast';
import { Bold, Code, TypedConfirm } from '../../../../src/components/TypedConfirm';
import { useBack } from '../../../../src/hooks/useBack';
import { useOllamaModels } from '../../../../src/hooks/useDaemonData';
import { useProfile } from '../../../../src/hooks/useSubject';
import { useEndpoint } from '../../../../src/lib/EndpointContext';
import { useTheme } from '../../../../src/theme/ThemeContext';

const KEY_INFO = {
  anthropic: { label: 'Anthropic', env: 'ANTHROPIC_API_KEY', placeholder: 'sk-ant-…', console: 'console.anthropic.com' },
  openai: { label: 'OpenAI', env: 'OPENAI_API_KEY', placeholder: 'sk-…', console: 'platform.openai.com' },
  openrouter: { label: 'OpenRouter', env: 'OPENROUTER_API_KEY', placeholder: 'sk-or-…', console: 'openrouter.ai' },
  gemini: { label: 'Google Gemini', env: 'GEMINI_API_KEY', placeholder: 'AIza…', console: 'aistudio.google.com' },
};

export default function ProviderKey() {
  const { id, key } = useLocalSearchParams();
  const goBack = useBack();
  const toast = useToast();
  const { call } = useEndpoint();
  const { colors, fonts, fontSizes } = useTheme();
  const { profile, refresh } = useProfile(id);

  const isOllama = typeof key === 'string' && key.startsWith('ollama-');
  const isNewOllama = key === 'ollama-new';
  const existingOllamaName = isOllama && !isNewOllama ? key.replace('ollama-', '') : null;

  const info = useMemo(() => {
    if (typeof key !== 'string') return null;
    if (isOllama) {
      return { label: isNewOllama ? 'Add Ollama' : `ollama/${existingOllamaName}`, env: null, isOllama: true };
    }
    return KEY_INFO[key];
  }, [key, isOllama, isNewOllama, existingOllamaName]);

  const [value, setValue] = useState('');
  const [show, setShow] = useState(false);
  const [url, setUrl] = useState('http://127.0.0.1:11434');
  const [name, setName] = useState('');
  const [confirmRemove, setConfirmRemove] = useState(false);

  const existingOllama = useMemo(() => {
    if (!existingOllamaName) return null;
    return (profile?.provider_ollama ?? []).find((o) => o.name === existingOllamaName) ?? null;
  }, [profile, existingOllamaName]);
  useEffect(() => {
    if (existingOllama) {
      setName(existingOllama.name);
      setUrl(existingOllama.url);
    }
  }, [existingOllama]);

  if (!info) {
    return (
      <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
        <ScreenHeader title="Unknown provider" onBack={goBack} />
      </SafeAreaView>
    );
  }

  if (info.isOllama) {
    return (
      <OllamaScreen
        id={id}
        isNew={isNewOllama}
        existingName={existingOllamaName}
        existingUrl={existingOllama?.url}
        nameValue={name}
        urlValue={url}
        onNameChange={setName}
        onUrlChange={setUrl}
        onSaved={async () => {
          await refresh();
          goBack();
        }}
        onRemoved={async () => {
          await refresh();
          goBack();
        }}
        call={call}
        toast={toast}
        colors={colors}
        fonts={fonts}
        fontSizes={fontSizes}
        radii={radii}
        info={info}
      />
    );
  }

  // Encrypted keys are never echoed back — `profile.provider_keys` only tells us IF the env is set.
  const isExisting = (profile?.provider_keys ?? []).some((k) => k.env === info.env);
  const trimmed = value.trim();
  const canSave = trimmed.length > 0;

  const onSave = async () => {
    if (!canSave) return;
    try {
      // Daemon reads `key` (the env var name is passed as the `key` value).
      await call('host.providers.set_key', { profile: id, key: info.env, value: trimmed });
      await refresh();
      toast({ title: isExisting ? 'Updated' : 'Saved', message: info.env, duration: 1500 });
      goBack();
    } catch (e) {
      toast({ title: 'Save failed', message: String(e) });
    }
  };

  const onRemove = async () => {
    try {
      await call('host.providers.unset_key', { profile: id, key: info.env });
      await refresh();
      toast({ title: 'Removed', message: info.env });
      goBack();
    } catch (e) {
      toast({ title: 'Remove failed', message: String(e) });
    }
  };

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader
        title={info.label}
        subtitle={`@${id} · ${info.env}${isExisting ? ' · set' : ''}`}
        onBack={goBack}
      />
      <KeyboardPane>
        <ScrollView contentContainerStyle={{ padding: space.s8, gap: space.s8 }} keyboardShouldPersistTaps="handled">
          <Field
            label={isExisting ? 'New API key' : 'API key'}
            value={value}
            onChangeText={setValue}
            placeholder={isExisting ? 'paste new key to replace' : info.placeholder}
            mono
            autoCapitalize="none"
            autoCorrect={false}
            helper={isExisting ? 'leaving this blank keeps the current key' : undefined}
            rightSlot={
              <Pressable onPress={() => setShow((v) => !v)} hitSlop={6}>
                <Icon name="eye" size="md" color={colors.ink3} />
              </Pressable>
            }
          />
          {show ? (
            <View
              style={{
                padding: space.s5,
                backgroundColor: colors.bgInput,
                borderRadius: radii.lg,
              }}
            >
              <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.ink }}>{value || '—'}</Text>
            </View>
          ) : null}
          <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink3 }}>
            Get a key at <Text style={{ fontFamily: fonts.mono, color: colors.ink2 }}>{info.console}</Text>. Keys are
            stored encrypted on the daemon's <Text style={{ fontFamily: fonts.mono, color: colors.ink2 }}>.env</Text>.
          </Text>
          <Button
            title={isExisting ? 'Save changes' : 'Add key'}
            size="lg"
            fullWidth
            disabled={!canSave}
            onPress={onSave}
          />
          {isExisting ? (
            <Button title="Remove key" variant="ghost" size="md" fullWidth onPress={() => setConfirmRemove(true)} />
          ) : null}
        </ScrollView>
      </KeyboardPane>
      <TypedConfirm
        open={confirmRemove}
        onClose={() => setConfirmRemove(false)}
        title={`Remove ${info.env}`}
        body={
          <>
            Clears <Code>{info.env}</Code> from the daemon's encrypted env. <Bold>Any model that needs this provider will stop working until you set it again.</Bold>
          </>
        }
        expected={info.env}
        confirmLabel="Remove key"
        onConfirm={() => {
          setConfirmRemove(false);
          onRemove();
        }}
      />
    </SafeAreaView>
  );
}

// Daemon exposes only add_ollama + remove_ollama — to edit URL, remove + re-add.
function OllamaScreen({
  id,
  isNew,
  existingName,
  existingUrl,
  nameValue,
  urlValue,
  onNameChange,
  onUrlChange,
  onSaved,
  onRemoved,
  call,
  toast,
  colors,
  fonts,
  fontSizes,
  radii,
  info,
}) {
  const ollamaModels = useOllamaModels(id);
  const myModels = useMemo(() => {
    if (!existingName) return [];
    const prefix = `${existingName}/`;
    return (ollamaModels.data?.models ?? [])
      .filter((m) => m.startsWith(prefix))
      .map((m) => m.slice(prefix.length));
  }, [ollamaModels.data, existingName]);
  const myError = useMemo(() => {
    if (!existingName) return null;
    return (ollamaModels.data?.errors ?? []).find((e) => e.name === existingName) ?? null;
  }, [ollamaModels.data, existingName]);

  const [confirmRemove, setConfirmRemove] = useState(false);
  const canSave = !!urlValue.trim() && !!nameValue.trim();
  const handleSave = async () => {
    if (!canSave) return;
    try {
      await call('host.providers.add_ollama', { profile: id, name: nameValue.trim(), url: urlValue.trim() });
      toast({ title: 'Saved', message: nameValue.trim(), duration: 1500 });
      onSaved();
    } catch (e) {
      toast({ title: 'Save failed', message: String(e) });
    }
  };

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader
        title={info.label}
        subtitle={`@${id} · ${isNew ? 'NEW INSTANCE' : 'LOCAL MODELS'}`}
        onBack={() => onSaved()}
      />
      <KeyboardPane>
        <ScrollView contentContainerStyle={{ paddingBottom: space.s10 }} keyboardShouldPersistTaps="handled">
          <View style={{ padding: space.s8, gap: space.s8 }}>
            <Field
              label="Name"
              value={nameValue}
              onChangeText={onNameChange}
              placeholder="local"
              mono
              editable={isNew}
              autoCapitalize="none"
              autoCorrect={false}
              helper={isNew ? 'short id — used as model prefix (e.g. local/llama3)' : 'name is fixed once created — remove + re-add to change'}
            />
            <Field
              label="URL"
              value={urlValue}
              onChangeText={onUrlChange}
              mono
              editable={isNew}
              autoCapitalize="none"
              autoCorrect={false}
              helper={isNew ? 'reachable from the daemon, not from this phone' : (existingUrl ? `last known: ${existingUrl}` : 'reachable from the daemon, not from this phone')}
            />
            {isNew ? (
              <Button title="Add Ollama" size="lg" fullWidth disabled={!canSave} onPress={handleSave} />
            ) : null}
          </View>

          {!isNew ? (
            <>
              <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: space.s8, paddingBottom: space.s3 }}>
                <Eyebrow>Live models</Eyebrow>
                {ollamaModels.loading ? (
                  <ActivityIndicator color={colors.ink3} size="small" />
                ) : (
                  <Pill tone={myModels.length > 0 ? 'on' : undefined} off={myModels.length === 0}>
                    {myModels.length}
                  </Pill>
                )}
              </View>
              {ollamaModels.loading && myModels.length === 0 ? (
                <View style={{ padding: space.s7, alignItems: 'center' }}>
                  <ActivityIndicator color={colors.ink3} />
                </View>
              ) : myModels.length === 0 ? (
                <View style={{ paddingHorizontal: space.s8, paddingVertical: space.s5, gap: space.s3 }}>
                  {myError ? (
                    <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.danger, lineHeight: fontSizes.sm * 1.5 }}>
                      {myError.detail}
                    </Text>
                  ) : null}
                  <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink3, lineHeight: fontSizes.sm * 1.5 }}>
                    {myError
                      ? 'Verify ollama is running and the URL is reachable from the daemon host.'
                      : "No models reported. The daemon couldn't reach this server — verify ollama is running and the URL is correct."}
                  </Text>
                </View>
              ) : (
                myModels.map((m, i) => (
                  <View key={m}>
                    {i > 0 ? <RowSeparator /> : null}
                    <Row
                      label={m}
                      helper={`${existingName}/${m}`}
                      chevron={false}
                    />
                  </View>
                ))
              )}

              <View style={{ padding: space.s8 }}>
                <Button
                  title="Remove Ollama instance"
                  variant="ghost"
                  size="md"
                  fullWidth
                  onPress={() => setConfirmRemove(true)}
                />
              </View>
            </>
          ) : null}
        </ScrollView>
      </KeyboardPane>
      <TypedConfirm
        open={confirmRemove}
        onClose={() => setConfirmRemove(false)}
        title={`Remove ollama/${existingName ?? ''}`}
        body={
          <>
            Detaches <Code>{existingName}</Code> from this profile. Models served from this instance disappear from the picker. <Bold>The Ollama process keeps running — only the daemon's reference is dropped.</Bold>
          </>
        }
        expected={existingName ?? ''}
        confirmLabel="Remove instance"
        onConfirm={async () => {
          setConfirmRemove(false);
          try {
            await call('host.providers.remove_ollama', { profile: id, name: existingName });
            toast({ title: 'Removed' });
            onRemoved();
          } catch (e) {
            toast({ title: 'Remove failed', message: String(e) });
          }
        }}
      />
    </SafeAreaView>
  );
}
