import { useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { ScrollView, Text, View } from 'react-native';
import { KeyboardPane } from '../../../../src/components/KeyboardPane';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '../../../../src/components/Button';
import { Field } from '../../../../src/components/Field';
import { ScreenHeader } from '../../../../src/components/ScreenHeader';
import { useToast } from '../../../../src/components/Toast';
import { useBack } from '../../../../src/hooks/useBack';
import { useEndpoint } from '../../../../src/lib/EndpointContext';
import { IMAP_FIELDS, buildAddPayload, isAddReady } from '../../../../src/lib/emailAccounts';
import { space } from '../../../../src/theme/tokens';
import { useTheme } from '../../../../src/theme/ThemeContext';

export default function NewEmail() {
  const { id } = useLocalSearchParams();
  const goBack = useBack();
  const toast = useToast();
  const { call } = useEndpoint();
  const { colors, fonts, fontSizes } = useTheme();
  const [draft, setDraft] = useState({});
  const [busy, setBusy] = useState(false);

  const ready = isAddReady(draft) && !busy;
  const setField = (key, value) => setDraft((d) => ({ ...d, [key]: value }));

  const save = async () => {
    if (!ready) return;
    setBusy(true);
    try {
      await call('host.email.add', buildAddPayload(id, draft));
      toast({ title: 'Email added', message: (draft.address || '').trim() });
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
        title="Add IMAP account"
        subtitle={`@${id} · IMAP / SMTP`}
        onBack={goBack}
        right={<Button title="Add" size="md" disabled={!ready} loading={busy} onPress={save} />}
      />
      <KeyboardPane>
        <ScrollView contentContainerStyle={{ padding: space.s8, gap: space.s7 }} keyboardShouldPersistTaps="handled">
          <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink3, lineHeight: fontSizes.sm * 1.5 }}>
            Connect a mailbox over IMAP / SMTP. Use an app password if the provider
            enforces 2FA. Ports default to 993 (IMAP) and 587 (SMTP) when left blank.
          </Text>
          {IMAP_FIELDS.map((f) => (
            <Field
              key={f.key}
              label={f.label + (f.required ? ' ·' : '')}
              value={draft[f.key] ?? ''}
              onChangeText={(t) => setField(f.key, t)}
              placeholder={f.hint}
              keyboardType={f.key === 'imap_port' || f.key === 'smtp_port' ? 'number-pad' : 'default'}
              mono
              autoCapitalize="none"
              autoCorrect={false}
              helper={f.hint}
            />
          ))}
        </ScrollView>
      </KeyboardPane>
    </SafeAreaView>
  );
}
