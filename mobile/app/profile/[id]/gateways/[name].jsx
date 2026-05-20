// Daemon: host.gateway.config (returns masked secrets), host.providers.set_key/unset_key per field, host.gateway.remove. Gmail OAuth is desktop-only (streaming + in-app browser hand-off).

import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { space , fontSizes} from '../../../../src/theme/tokens';

import { Button } from '../../../../src/components/Button';
import { Field } from '../../../../src/components/Field';
import { ScreenHeader } from '../../../../src/components/ScreenHeader';
import { useToast } from '../../../../src/components/Toast';
import { Bold, Code, TypedConfirm } from '../../../../src/components/TypedConfirm';
import { useGatewayConfig } from '../../../../src/hooks/useDaemonData';
import { useEndpoint } from '../../../../src/lib/EndpointContext';
import { GATEWAY_DESC, GATEWAY_FIELDS, GATEWAY_LABELS } from '../../../../src/lib/gateways';
import { useTheme } from '../../../../src/theme/ThemeContext';

export default function GatewayConfig() {
  const { id, name } = useLocalSearchParams();
  const router = useRouter();
  const toast = useToast();
  const { call } = useEndpoint();
  const { colors, fonts, fontSizes } = useTheme();
  const cfg = useGatewayConfig(id, name);
  const [draft, setDraft] = useState({});
  // Secret fields render masked from the daemon — track which ones the user has touched so we don't overwrite the real key with the mask on save.
  const [touched, setTouched] = useState({});
  const [busy, setBusy] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(false);

  const fields = GATEWAY_FIELDS[name] ?? [];
  const label = GATEWAY_LABELS[name] ?? name;
  const desc = GATEWAY_DESC[name] ?? '';
  const current = cfg.data?.config ?? {};
  const configured = Object.keys(current).length > 0;

  useEffect(() => {
    setDraft({ ...current });
    setTouched({});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cfg.data]);

  const setField = (env, value) => {
    setDraft((d) => ({ ...d, [env]: value }));
    setTouched((t) => ({ ...t, [env]: true }));
  };

  const save = async () => {
    setBusy(true);
    try {
      for (const f of fields) {
        const value = draft[f.env] ?? '';
        // Skip untouched secret fields — daemon has the real value, draft has the mask.
        if (f.secret && !touched[f.env]) continue;
        if (value === '') {
          if (current[f.env]) {
            await call('host.providers.unset_key', { profile: id, key: f.env });
          }
        } else {
          await call('host.providers.set_key', { profile: id, key: f.env, value });
        }
      }
      toast({ title: `${label} saved`, duration: 1600 });
      cfg.refresh?.();
    } catch (e) {
      toast({ title: 'Save failed', message: String(e) });
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    setBusy(true);
    try {
      await call('host.gateway.remove', { profile: id, name });
      toast({ title: `${label} removed` });
      router.back();
    } catch (e) {
      toast({ title: 'Remove failed', message: String(e) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader
        title={label}
        subtitle={`@${id} · ${desc.toUpperCase()}`}
        onBack={() => router.back()}
        right={<Button title="Save" size="md" loading={busy} disabled={busy} onPress={save} />}
      />
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={{ padding: space.s8, gap: space.s7 }} keyboardShouldPersistTaps="handled">
          {cfg.loading && !cfg.data ? (
            <View style={{ padding: space.s10, alignItems: 'center' }}>
              <ActivityIndicator color={colors.ink3} />
            </View>
          ) : (
            <>
              {fields.length === 0 ? (
                <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.md, color: colors.ink3 }}>
                  Unknown gateway.
                </Text>
              ) : (
                fields.map((f) => {
                  const stored = current[f.env];
                  const isSecretMasked = f.secret && stored && !touched[f.env];
                  return (
                    <Field
                      key={f.env}
                      label={f.label + (f.required ? ' ·' : '')}
                      value={draft[f.env] ?? ''}
                      onChangeText={(t) => setField(f.env, t)}
                      placeholder={isSecretMasked ? stored : ''}
                      mono
                      autoCapitalize="none"
                      autoCorrect={false}
                      helper={
                        isSecretMasked
                          ? `${f.hint ?? ''}${f.hint ? ' · ' : ''}leave blank to keep current`
                          : f.hint
                      }
                    />
                  );
                })
              )}

              {name === 'gmail' ? (
                <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink4, lineHeight: fontSizes.xs * 1.6 }}>
                  Gmail OAuth grant has to be completed on the alpi desktop app for now — the
                  browser hand-off isn't yet supported here. You can still save the client id /
                  secret on this screen.
                </Text>
              ) : null}

              {configured ? (
                <Pressable
                  onPress={() => setConfirmRemove(true)}
                  style={{ alignSelf: 'flex-start', paddingVertical: space.s4 }}
                >
                  <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.md, color: colors.danger }}>
                    Remove {label} gateway
                  </Text>
                </Pressable>
              ) : null}
            </>
          )}
        </ScrollView>
      </KeyboardAvoidingView>

      <TypedConfirm
        open={confirmRemove}
        onClose={() => setConfirmRemove(false)}
        title={`Remove ${label} gateway`}
        body={
          <>
            Wipes <Code>{fields.filter((f) => f.required).length} env</Code>{' '}
            value{fields.filter((f) => f.required).length === 1 ? '' : 's'} from{' '}
            <Code>~/.alpi/profiles/{id}/.env</Code>. The agent stops accepting{' '}
            <Code>{name}</Code> traffic immediately. <Bold>You can re-add it any time.</Bold>
          </>
        }
        expected={name}
        confirmLabel="Remove"
        onConfirm={() => {
          setConfirmRemove(false);
          remove();
        }}
      />
    </SafeAreaView>
  );
}
