import { useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, Alert, Pressable, ScrollView, Text, View } from 'react-native';
import { radii, space , fontSizes} from '../../theme/tokens';

import { Field } from '../../components/Field';
import { PickerRow } from '../../components/PickerRow';
import { Pill } from '../../components/Pill';
import { RowSeparator, SectionHeader } from '../../components/Row';
import { Sheet } from '../../components/Sheet';
import { useToast } from '../../components/Toast';
import { nextSheetValue } from '../../lib/sheet-value';
import { useOllamaModels } from '../../hooks/useDaemonData';
import { useEndpoint } from '../../lib/EndpointContext';
import { noteFor } from '../../lib/curatedModels';
import { VOICE_SHORTLIST } from '../../lib/voices';
import {
  currentlyPlayingVoice,
  playVoicePreview,
  stopVoicePreview,
  subscribeVoicePreview,
} from '../../lib/voicePreview';
import { useTheme } from '../../theme/ThemeContext';

export function BudgetSheet({ open, onClose, profileName, initialValue, onSave }) {
  const toast = useToast();
  const [value, setValue] = useState(initialValue ?? '');
  useEffect(() => {
    if (open) setValue(initialValue != null ? String(initialValue) : '');
  }, [open, initialValue]);
  const save = async () => {
    try {
      await onSave?.(value);
      toast({ title: 'Budget saved', duration: 1400 });
      onClose?.();
    } catch (e) {
      toast({ title: 'Save failed', message: String(e), duration: 2400 });
    }
  };
  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Daily budget"
      subtitle={`@${profileName ?? ''} · per-day spend cap`}
      primaryAction={{ label: 'Save cap', onPress: save, disabled: !value }}
    >
      <View style={{ padding: space.s8, gap: space.s7 }}>
        <Field label="USD per day" value={value} onChangeText={setValue} keyboardType="decimal-pad" mono helper="Cost stops the agent at this number" />
      </View>
    </Sheet>
  );
}

const REASONING_OPTIONS = [
  { value: '', label: 'Default', helper: 'use provider default' },
  { value: 'low', label: 'Low', helper: 'fastest, cheapest' },
  { value: 'medium', label: 'Medium', helper: 'balanced' },
  { value: 'high', label: 'High', helper: 'slower, more thorough' },
];

export function ReasoningEffortSheet({ open, onClose, initialValue, onSave }) {
  const toast = useToast();
  const [value, setValue] = useState(initialValue ?? '');
  useEffect(() => { if (open) setValue(initialValue ?? ''); }, [open, initialValue]);
  const save = async () => {
    try {
      await onSave?.(value);
      toast({ title: 'Reasoning saved', duration: 1400 });
      onClose?.();
    } catch (e) {
      toast({ title: 'Save failed', message: String(e), duration: 2400 });
    }
  };
  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Reasoning effort"
      subtitle="how hard the model thinks before answering"
      primaryAction={{ label: 'Save', onPress: save }}
    >
      <View style={{ paddingVertical: space.s5 }}>
        {REASONING_OPTIONS.map((opt, i) => (
          <View key={opt.value || 'off'}>
            {i > 0 ? <RowSeparator /> : null}
            <PickerRow
              label={opt.label}
              helper={opt.helper}
              selected={value === opt.value}
              onPress={() => setValue(opt.value)}
            />
          </View>
        ))}
      </View>
    </Sheet>
  );
}


export function WorkspaceSheet({ open, onClose, profileName, initialValue, onSave }) {
  const toast = useToast();
  const [value, setValue] = useState(initialValue ?? '');
  const prevInitRef = useRef(null);
  useEffect(() => {
    if (!open) { prevInitRef.current = null; return; }
    const newInit = initialValue ?? '';
    setValue((current) => nextSheetValue({
      current,
      newInitial: newInit,
      prevInitial: prevInitRef.current,
    }));
    prevInitRef.current = newInit;
  }, [open, initialValue]);
  const save = async () => {
    try {
      await onSave?.(value);
      toast({ title: 'Workspace saved', duration: 1400 });
      onClose?.();
    } catch (e) {
      toast({ title: 'Save failed', message: String(e), duration: 2400 });
    }
  };
  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Workspace"
      subtitle={`@${profileName ?? ''} · root path`}
      primaryAction={{ label: 'Save workspace', onPress: save }}
    >
      <View style={{ padding: space.s8, gap: space.s7 }}>
        <Field
          label="Absolute path"
          value={value}
          onChangeText={setValue}
          placeholder="/Users/you/git/repo"
          mono
          autoCapitalize="none"
          autoCorrect={false}
          helper="Where this profile reads + writes files. Empty = no workspace."
        />
      </View>
    </Sheet>
  );
}

function providerKeyOf(modelId, ollamaServers) {
  if (!modelId) return 'other';
  const i = modelId.indexOf('/');
  if (i < 0) return 'other';
  const raw = modelId.slice(0, i);
  return ollamaServers.has(raw) ? `ollama/${raw}` : raw;
}

export function ModelSheet({
  open,
  onClose,
  profileName,
  accent,
  initialValue,
  profileModels = [],
  providerKeys = [],
  openrouterModels = [],
  ollamaNames = [],
  onSave,
  title = 'Model',
  subtitle = null,
  allowClear = false,
}) {
  const { colors, fonts, fontSizes } = useTheme();
  const toast = useToast();
  const [picked, setPicked] = useState(initialValue ?? '');
  const ollama = useOllamaModels(open ? profileName : null);

  useEffect(() => {
    if (open) setPicked(initialValue ?? '');
  }, [open, initialValue]);

  const save = async () => {
    if (!picked && !allowClear) return;
    try {
      await onSave?.(picked);
      toast({ title: `${title} saved`, message: picked || 'main model' });
      onClose?.();
    } catch (e) {
      toast({ title: 'Save failed', message: String(e) });
    }
  };

  const ollamaServers = useMemo(() => {
    const s = new Set();
    const list = ollama.data?.models ?? [];
    for (let i = 0; i < list.length; i += 1) {
      const slash = list[i].indexOf('/');
      if (slash > 0) s.add(list[i].slice(0, slash));
    }
    for (let i = 0; i < ollamaNames.length; i += 1) s.add(ollamaNames[i]);
    return s;
  }, [ollama.data, ollamaNames]);

  const groups = useMemo(() => {
    const seen = new Set();
    const acc = {};
    const sources = [profileModels, ollama.data?.models ?? []];
    for (let s = 0; s < sources.length; s += 1) {
      const src = sources[s];
      for (let i = 0; i < src.length; i += 1) {
        const m = src[i];
        if (!m || seen.has(m)) continue;
        seen.add(m);
        const k = providerKeyOf(m, ollamaServers);
        if (!acc[k]) acc[k] = [];
        acc[k].push(m);
      }
    }
    return acc;
  }, [profileModels, ollama.data, ollamaServers]);

  // ollama/* first (local before cloud) matches desktop ProviderPickerForm order.
  const KNOWN_ORDER = ['anthropic', 'openai', 'openrouter', 'gemini'];
  const allKeys = Object.keys(groups);
  const ollamaCats = allKeys.filter((k) => k.startsWith('ollama/')).sort();
  const knownCloud = KNOWN_ORDER.filter((k) => allKeys.includes(k));
  const rest = allKeys
    .filter((k) => !KNOWN_ORDER.includes(k) && !k.startsWith('ollama/') && k !== 'other')
    .sort();
  const cats = [
    ...ollamaCats,
    ...knownCloud,
    ...rest,
    ...(allKeys.includes('other') ? ['other'] : []),
  ];

  const noOllamaConfigured = ollamaNames.length === 0;
  const ollamaErrors = ollama.data?.errors ?? [];

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title={title}
      subtitle={subtitle ?? `@${profileName ?? ''} · default model`}
      primaryAction={{
        label: allowClear ? 'Save' : 'Set default',
        onPress: save,
        disabled: allowClear ? false : !picked,
      }}
    >
      <ScrollView contentContainerStyle={{ paddingBottom: space.s7 }}>
        {allowClear ? (
          <View>
            <PickerRow
              selected={!picked}
              accent={accent}
              label="Use main model"
              helper="tier unset — everything falls back to the profile model"
              onPress={() => setPicked('')}
            />
            <RowSeparator />
          </View>
        ) : null}
        {/* During the initial Ollama poll the cloud models (always synchronous via profile.models) are visible but the Ollama section is still loading — render a spinner instead of "No models available" only if BOTH are pending. */}
        {cats.length === 0 ? (
          ollama.loading ? (
            <View style={{ padding: space.s10, alignItems: 'center' }}>
              <ActivityIndicator color={colors.ink3} />
            </View>
          ) : (
            <View style={{ paddingHorizontal: space.s8, paddingVertical: space.s8, gap: space.s5 }}>
              <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.lg, color: colors.ink }}>
                No models available for @{profileName}
              </Text>
              <View style={{ gap: space.s1 }}>
                <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink4 }}>
                  daemon profile.models: {profileModels.length}
                </Text>
                <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink4 }}>
                  provider_keys: {providerKeys.length} ({providerKeys.map((k) => k.env).join(', ') || '—'})
                </Text>
                <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink4 }}>
                  ollama configured: {ollamaNames.length}, reachable: {ollama.data?.models?.length ?? 0}
                </Text>
              </View>
              {ollamaErrors.map((e) => (
                <Text
                  key={e.name}
                  style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.danger, lineHeight: fontSizes.xs * 1.5 }}
                >
                  ollama/{e.name} · {e.url} — {e.detail}
                </Text>
              ))}
              <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink4, marginTop: space.s1 }}>
                Go to Settings → Providers to fix.
              </Text>
            </View>
          )
        ) : (
          cats.map((cat) => (
            <View key={cat}>
              <SectionHeader>{cat}</SectionHeader>
              {groups[cat].map((m, i) => {
                const tag = noteFor(m);
                const labelText = m.includes('/') ? m.split('/').slice(1).join('/') : m;
                return (
                  <View key={m}>
                    {i > 0 ? <RowSeparator /> : null}
                    <PickerRow
                      selected={picked === m}
                      accent={accent}
                      label={labelText}
                      meta={tag ? <Pill>{tag}</Pill> : null}
                      onPress={() => setPicked(m)}
                    />
                  </View>
                );
              })}
            </View>
          ))
        )}
        {/* One block per failing Ollama — daemon hands us the exact reason (timeout / refused / bad json / …) so we don't have to guess. */}
        {!noOllamaConfigured && !ollama.loading && ollamaErrors.length > 0 ? (
          <View style={{ paddingHorizontal: space.s8, paddingTop: space.s5, gap: space.s2 }}>
            {ollamaErrors.map((e) => (
              <Text
                key={e.name}
                style={{
                  fontFamily: fonts.mono,
                  fontSize: fontSizes.xs,
                  color: colors.ink4,
                  lineHeight: fontSizes.xs * 1.5,
                }}
              >
                <Text style={{ color: colors.danger }}>ollama/{e.name}</Text> · {e.url} — {e.detail}
              </Text>
            ))}
          </View>
        ) : null}
        {/* Sub-spinner only when cloud models are already showing and Ollama is still polling, so the user sees that more is coming. */}
        {ollama.loading && cats.length > 0 ? (
          <View style={{ padding: space.s7, alignItems: 'center' }}>
            <ActivityIndicator color={colors.ink3} />
          </View>
        ) : null}
      </ScrollView>
    </Sheet>
  );
}

function formatCleanupBytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export function CleanupSheet({ open, onClose, profileName, call, onCleaned }) {
  const { colors, fonts, fontSizes } = useTheme();
  const toast = useToast();
  const [plan, setPlan] = useState(null);
  const [busyKey, setBusyKey] = useState(null);

  const fetchPlan = () =>
    call('host.cleanup.plan', { profile: profileName })
      .then((res) => setPlan(Array.isArray(res?.categories) ? res.categories : 'error'))
      .catch(() => setPlan('error'));

  useEffect(() => {
    if (!open) return;
    setPlan(null);
    fetchPlan();
  }, [open, profileName]);

  const doClean = async (cat) => {
    setBusyKey(cat.key);
    try {
      const res = await call('host.cleanup.apply', { profile: profileName, keys: [cat.key] });
      const results = Array.isArray(res?.results) ? res.results : [];
      const failed = results.filter((r) => !r.ok);
      const removed = results.reduce((n, r) => n + (r.removed ?? 0), 0);
      const freed = results.reduce((n, r) => n + (r.freed_bytes ?? 0), 0);
      if (failed.length > 0) {
        toast({
          title: `${cat.label} failed`,
          message: failed[0].errors?.[0] ?? 'cleanup failed',
          duration: 2600,
        });
      } else {
        toast({ title: `${cat.label}: freed ${formatCleanupBytes(freed)}`, duration: 1800 });
      }
      await fetchPlan();
      if (removed > 0) onCleaned?.();
    } catch (e) {
      toast({ title: 'Cleanup failed', message: String(e), duration: 2400 });
    } finally {
      setBusyKey(null);
    }
  };

  const clean = (cat) => {
    if (busyKey) return;
    if (!cat.destructive) {
      doClean(cat);
      return;
    }
    Alert.alert(
      `Delete ${cat.label.toLowerCase()}?`,
      `${cat.desc}. This cannot be undone.`,
      [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Delete', style: 'destructive', onPress: () => doClean(cat) },
      ],
    );
  };

  const reclaimable = plan === 'error' ? [] : (plan ?? []).filter((c) => c.size > 0);
  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Reclaim space"
      subtitle={`@${profileName ?? ''} · caches, logs, old transcripts`}
    >
      <View style={{ paddingVertical: space.s5 }}>
        {plan === null ? (
          <View style={{ padding: space.s10, alignItems: 'center' }}>
            <ActivityIndicator color={colors.ink3} />
          </View>
        ) : plan === 'error' ? (
          <Text
            style={{
              padding: space.s8, fontFamily: fonts.sans.regular,
              fontSize: fontSizes.sm, color: colors.ink3,
            }}
          >
            Cleanup unavailable — daemon offline or older than 0.10.24.
          </Text>
        ) : reclaimable.length === 0 ? (
          <Text
            style={{
              padding: space.s8, fontFamily: fonts.sans.regular,
              fontSize: fontSizes.sm, color: colors.ink3,
            }}
          >
            Nothing to clean — this profile is tidy.
          </Text>
        ) : (
          reclaimable.map((c, i) => (
            <View key={c.key}>
              {i > 0 ? <RowSeparator /> : null}
              <PickerRow
                label={c.label}
                helper={c.desc}
                meta={<Pill>{formatCleanupBytes(c.size)}</Pill>}
                onPress={() => (busyKey ? null : clean(c))}
              />
            </View>
          ))
        )}
      </View>
    </Sheet>
  );
}


export function VoiceSheet({ open, onClose, profileName, accent, initialValue, onSave }) {
  const { colors, fonts, fontSizes } = useTheme();
  const toast = useToast();
  const { call } = useEndpoint();
  const [picked, setPicked] = useState(initialValue ?? VOICE_SHORTLIST[0]?.id);
  const [previewState, setPreviewState] = useState({ voiceId: currentlyPlayingVoice(), kind: null });

  useEffect(() => {
    if (open && initialValue) setPicked(initialValue);
  }, [open, initialValue]);

  useEffect(() => {
    return subscribeVoicePreview((s) => setPreviewState(s));
  }, []);

  useEffect(() => {
    if (!open) stopVoicePreview();
    return () => stopVoicePreview();
  }, [open]);

  const save = async () => {
    try {
      await onSave?.(picked);
      toast({ title: 'Voice saved' });
      onClose?.();
    } catch (e) {
      toast({ title: 'Save failed', message: String(e) });
    }
  };

  const onPreview = (voiceId) => {
    playVoicePreview({ call, voiceId }).catch(() => {
      toast({ title: 'Preview failed', duration: 1600 });
    });
  };

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Voice"
      subtitle="Voice used for read-aloud"
      primaryAction={{ label: 'Save', onPress: save, disabled: !picked }}
    >
      <ScrollView contentContainerStyle={{ paddingBottom: space.s7 }}>
        {VOICE_SHORTLIST.map((v, i) => {
          const isPlaying = previewState.voiceId === v.id && (previewState.kind === 'playing' || previewState.kind === 'loading');
          const isLoading = previewState.voiceId === v.id && previewState.kind === 'loading';
          return (
            <View key={v.id}>
              {i > 0 ? <RowSeparator /> : null}
              <PickerRow
                selected={picked === v.id}
                accent={accent}
                label={v.name}
                helper={v.desc}
                onPress={() => setPicked(v.id)}
                right={
                  <Pressable
                    onPress={() => onPreview(v.id)}
                    hitSlop={8}
                    style={({ pressed }) => ({
                      paddingHorizontal: space.s5,
                      paddingVertical: space.s2,
                      borderRadius: radii.pill,
                      borderWidth: 0.5,
                      borderColor: isPlaying ? colors.ink : colors.line2,
                      backgroundColor: pressed ? colors.selected : isPlaying ? colors.bgInput : 'transparent',
                      flexDirection: 'row',
                      alignItems: 'center',
                      gap: space.s2,
                    })}
                  >
                    {isLoading ? <ActivityIndicator size="small" color={colors.ink3} /> : null}
                    <Text style={{ fontFamily: fonts.monoMedium, fontSize: fontSizes.xs, color: isPlaying ? colors.ink : colors.ink2 }}>
                      {isLoading ? 'loading' : isPlaying ? 'stop' : 'preview'}
                    </Text>
                  </Pressable>
                }
              />
            </View>
          );
        })}
      </ScrollView>
    </Sheet>
  );
}
