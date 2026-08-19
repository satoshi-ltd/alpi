import { useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ActionSheet } from '../../../../src/components/ActionSheet';
import { Button } from '../../../../src/components/Button';
import { Icon } from '../../../../src/components/Icon';
import { Pill } from '../../../../src/components/Pill';
import { Row, RowSeparator } from '../../../../src/components/Row';
import { ScreenHeader } from '../../../../src/components/ScreenHeader';
import { useBack } from '../../../../src/hooks/useBack';
import { useEmailAccounts } from '../../../../src/hooks/useDaemonData';
import { useEventEffect } from '../../../../src/hooks/useEvents';
import { EMAIL_TYPE_LABELS } from '../../../../src/lib/emailAccounts';
import { space } from '../../../../src/theme/tokens';
import { useTheme } from '../../../../src/theme/ThemeContext';

export default function EmailList() {
  const { id } = useLocalSearchParams();
  const router = useRouter();
  const goBack = useBack();
  const { colors, fonts, fontSizes } = useTheme();
  const accounts = useEmailAccounts(id);
  const [chooser, setChooser] = useState(false);

  useEventEffect('email_changed', (ev) => {
    if (ev?.data?.profile && ev.data.profile !== id) return;
    accounts.refresh?.();
  });

  const list = accounts.data?.accounts ?? [];

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader
        title="Email"
        subtitle={`@${id} · ${list.length} ACCOUNT${list.length === 1 ? '' : 'S'}`}
        onBack={goBack}
        right={<Button title="+ Add" size="md" variant="ghost" onPress={() => setChooser(true)} />}
      />
      <ScrollView>
        {accounts.loading && !accounts.data ? (
          <View style={{ padding: space.s11, alignItems: 'center' }}>
            <ActivityIndicator color={colors.ink3} />
          </View>
        ) : list.length === 0 ? (
          <Row label="No email accounts configured" helper="tap + Add to connect one" chevron={false} />
        ) : (
          list.map((a, i) => {
            const type = EMAIL_TYPE_LABELS[a.type] ?? a.type;
            return (
              <View key={a.id}>
                {i > 0 ? <RowSeparator /> : null}
                <Pressable
                  onPress={() => router.push(`/profile/${id}/email/${a.id}`)}
                  android_ripple={{ color: colors.selected }}
                  style={({ pressed }) => ({
                    paddingHorizontal: space.s8,
                    paddingVertical: space.s6,
                    gap: space.s1,
                    backgroundColor: pressed ? colors.selected : 'transparent',
                  })}
                >
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s3 }}>
                    <Text
                      numberOfLines={1}
                      ellipsizeMode="middle"
                      style={{ flex: 1, fontFamily: fonts.sans.semibold, fontSize: fontSizes.lg, color: colors.ink }}
                    >
                      {a.address}
                    </Text>
                    {a.configured ? <Pill tone="on">on</Pill> : <Pill off>off</Pill>}
                  </View>
                  <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3, letterSpacing: 0.6 }}>
                    {type}
                  </Text>
                </Pressable>
              </View>
            );
          })
        )}
      </ScrollView>
      <ActionSheet
        open={chooser}
        onClose={() => setChooser(false)}
        title="Add email account"
        description="Gmail accounts are added by completing the OAuth grant on the alpi desktop app — here you can add an IMAP / SMTP account."
        actions={[
          {
            id: 'imap',
            label: 'IMAP / SMTP',
            icon: <Icon name="server" size="lg" color={colors.ink} />,
            onPress: () => {
              setChooser(false);
              router.push(`/profile/${id}/email/new`);
            },
          },
        ]}
      />
    </SafeAreaView>
  );
}
