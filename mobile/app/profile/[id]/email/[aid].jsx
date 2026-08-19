import { useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Field } from '../../../../src/components/Field';
import { Pill } from '../../../../src/components/Pill';
import { ScreenHeader } from '../../../../src/components/ScreenHeader';
import { useToast } from '../../../../src/components/Toast';
import { Bold, Code, TypedConfirm } from '../../../../src/components/TypedConfirm';
import { useBack } from '../../../../src/hooks/useBack';
import { useEmailConfig } from '../../../../src/hooks/useDaemonData';
import { useEndpoint } from '../../../../src/lib/EndpointContext';
import { EMAIL_TYPE_LABELS } from '../../../../src/lib/emailAccounts';
import { space } from '../../../../src/theme/tokens';
import { useTheme } from '../../../../src/theme/ThemeContext';

const VIEW_FIELDS = [
  { key: 'imap_host', label: 'IMAP host' },
  { key: 'imap_port', label: 'IMAP port' },
  { key: 'smtp_host', label: 'SMTP host' },
  { key: 'smtp_port', label: 'SMTP port' },
];

export default function EmailConfig() {
  const { id, aid } = useLocalSearchParams();
  const goBack = useBack();
  const toast = useToast();
  const { call } = useEndpoint();
  const { colors, fonts, fontSizes } = useTheme();
  const cfg = useEmailConfig(id, aid);
  const [busy, setBusy] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(false);

  const config = cfg.data?.config ?? {};
  const type = config.type ?? '';
  const typeLabel = EMAIL_TYPE_LABELS[type] ?? type;
  const address = config.address ?? aid;
  const isImap = type === 'imap';

  const remove = async () => {
    setBusy(true);
    try {
      await call('host.email.remove', { profile: id, id: aid });
      toast({ title: 'Email removed', message: address });
      goBack();
    } catch (e) {
      toast({ title: 'Remove failed', message: String(e) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader
        title={address}
        subtitle={`@${id} · ${(typeLabel || 'EMAIL').toUpperCase()}`}
        onBack={goBack}
      />
      <ScrollView contentContainerStyle={{ padding: space.s8, gap: space.s7 }}>
        {cfg.loading && !cfg.data ? (
          <View style={{ padding: space.s10, alignItems: 'center' }}>
            <ActivityIndicator color={colors.ink3} />
          </View>
        ) : (
          <>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s3, flexWrap: 'wrap' }}>
              <Pill tone="on">{typeLabel || 'email'}</Pill>
              {config.password_set ? <Pill tone="on">password set</Pill> : null}
            </View>

            <Field label="Email address" value={address} editable={false} mono />

            {isImap ? (
              VIEW_FIELDS.map((f) =>
                config[f.key] != null && config[f.key] !== '' ? (
                  <Field key={f.key} label={f.label} value={String(config[f.key])} editable={false} mono />
                ) : null,
              )
            ) : (
              <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink4, lineHeight: fontSizes.xs * 1.6 }}>
                Gmail accounts are managed through the OAuth grant on the alpi desktop app.
                You can remove this account here.
              </Text>
            )}

            <Pressable
              onPress={() => setConfirmRemove(true)}
              style={{ alignSelf: 'flex-start', paddingVertical: space.s4 }}
            >
              <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.md, color: colors.danger }}>
                Remove account
              </Text>
            </Pressable>
          </>
        )}
      </ScrollView>

      <TypedConfirm
        open={confirmRemove}
        onClose={() => setConfirmRemove(false)}
        title="Remove email account"
        body={
          <>
            Detaches <Code>{address}</Code> from this profile and wipes its credentials from{' '}
            <Code>~/.alpi/profiles/{id}/.env</Code>. Future <Code>email</Code> tool calls can no
            longer use this account. <Bold>You can re-add it any time.</Bold>
          </>
        }
        expected={address}
        confirmLabel="Remove"
        onConfirm={() => {
          setConfirmRemove(false);
          remove();
        }}
      />
    </SafeAreaView>
  );
}
