import * as Clipboard from 'expo-clipboard';
import { useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Linking, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '../../../../src/components/Button';
import { ConfirmDialog } from '../../../../src/components/ConfirmDialog';
import { Field } from '../../../../src/components/Field';
import { KeyboardPane } from '../../../../src/components/KeyboardPane';
import { Row, RowGroup, RowSeparator, SectionHeader } from '../../../../src/components/Row';
import { ScreenHeader } from '../../../../src/components/ScreenHeader';
import { useToast } from '../../../../src/components/Toast';
import { useBack } from '../../../../src/hooks/useBack';
import { useDirtyBack } from '../../../../src/hooks/useDirtyBack';
import { useProfile } from '../../../../src/hooks/useSubject';
import {
  CALLBACK_START, CHATGPT_CALL, CHATGPT_CALLBACK_PORT, CHATGPT_USAGE_URL, PLAN_DECLINED, SIGN_IN_STEPS,
  failureMessage, isSignInUrl, looksLikeCallback, signedInMessage, signedOutMessage,
} from '../../../../src/lib/chatgptPlan';
import { useEndpoint } from '../../../../src/lib/EndpointContext';
import { runsOnPlan } from '../../../../src/lib/modelLabel';
import { useTheme } from '../../../../src/theme/ThemeContext';
import { space } from '../../../../src/theme/tokens';

export default function ChatGPTPlan() {
  const { id } = useLocalSearchParams();
  const goBack = useBack();
  const toast = useToast();
  const { call } = useEndpoint();
  const { colors, fonts, fontSizes } = useTheme();
  const { profile, refresh } = useProfile(id);
  const state = profile?.provider_chatgpt;

  const [opened, setOpened] = useState(false);
  const [busy, setBusy] = useState('');
  const [answer, setAnswer] = useState('');
  const [confirmSignOut, setConfirmSignOut] = useState(false);
  const askBack = useDirtyBack(answer.trim().length > 0, goBack);

  const note = { fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink3, lineHeight: fontSizes.sm * 1.5 };
  const frame = { flex: 1, backgroundColor: colors.bg };

  if (profile && !state) {
    return (
      <SafeAreaView edges={['top', 'left', 'right']} style={frame}>
        <ScreenHeader title="ChatGPT plan" onBack={goBack} />
        <Text style={{ ...note, padding: space.s7 }}>Update alpi on this daemon to sign in with ChatGPT.</Text>
      </SafeAreaView>
    );
  }

  const start = async () => {
    setBusy('start');
    try {
      const begun = await call('host.providers.chatgpt_begin', { profile: id, port: CHATGPT_CALLBACK_PORT });
      if (!isSignInUrl(begun?.url)) throw new Error("The daemon returned an address that is not OpenAI's sign-in.");
      await Linking.openURL(begun.url);
      // Only once the browser did open: until then the first button stays the way in.
      setOpened(true);
    } catch (e) {
      toast({ title: 'Sign-in failed', message: failureMessage(e) });
    } finally {
      setBusy('');
    }
  };

  const paste = async () => {
    const clip = String(await Clipboard.getStringAsync().catch(() => '') || '').trim();
    if (looksLikeCallback(clip)) setAnswer(clip);
    else toast({ title: 'Clipboard has no sign-in address' });
  };

  const finish = async () => {
    setBusy('finish');
    try {
      const result = await call('host.providers.chatgpt_finish', { profile: id, callback: answer.trim() }, CHATGPT_CALL);
      await refresh().catch(() => {});
      setOpened(false);
      setAnswer('');
      toast(result.signed_in ? signedInMessage(result) : { title: 'Plan use declined', message: 'Sign in again to allow it.' });
    } catch (e) {
      toast({ title: 'Sign-in failed', message: failureMessage(e) });
    } finally {
      setBusy('');
    }
  };

  const signOut = async () => {
    if (busy) return;
    setBusy('signout');
    try {
      const out = await call('host.providers.chatgpt_logout', { profile: id, forget: true }, CHATGPT_CALL);
      await refresh().catch(() => {});
      toast(signedOutMessage(out, id));
    } catch (e) {
      toast({ title: 'Sign out failed', message: failureMessage(e) });
    } finally {
      setBusy('');
    }
  };

  const signedIn = !!state?.signed_in;
  const answerOk = looksLikeCallback(answer);

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={frame}>
      <ScreenHeader title="ChatGPT plan" subtitle={`@${id} · ${signedIn ? 'signed in' : 'not signed in'}`} onBack={askBack} />
      <KeyboardPane>
        <ScrollView contentContainerStyle={{ paddingBottom: space.s10 }} keyboardShouldPersistTaps="handled">
          {signedIn ? (
            <>
              <SectionHeader>Account</SectionHeader>
              <RowGroup>
                <Row label={state.email || 'Signed in'} chevron={false} />
                <RowSeparator />
                <Row label="Manage usage" onPress={() => Linking.openURL(CHATGPT_USAGE_URL).catch(() => {})} />
              </RowGroup>
              <View style={{ paddingHorizontal: space.s7, paddingVertical: space.s8 }}>
                <Button title="Sign out" variant="ghost" size="md" fullWidth disabled={!!busy} onPress={() => setConfirmSignOut(true)} />
              </View>
            </>
          ) : (
            <View style={{ paddingHorizontal: space.s7, paddingVertical: space.s8, gap: space.s8 }}>
              {state?.plan_declined ? <Text style={{ ...note, color: colors.ink2 }}>{PLAN_DECLINED}</Text> : null}
              <View style={{ gap: space.s3 }}>
                {SIGN_IN_STEPS.map((step, i) => (
                  <Text key={step} style={note}>{`${i + 1}. ${step}`}</Text>
                ))}
              </View>
              <Button
                title={opened ? 'Open browser again' : 'Continue with ChatGPT'}
                variant={opened ? 'ghost' : undefined}
                size={opened ? 'md' : 'lg'}
                fullWidth
                loading={busy === 'start'}
                disabled={!!busy}
                onPress={start}
              />
              <Field
                label="Address"
                value={answer}
                onChangeText={setAnswer}
                placeholder={`${CALLBACK_START}?…`}
                mono
                autoCapitalize="none"
                autoCorrect={false}
                helper={answer && !answerOk ? `must start with ${CALLBACK_START}` : undefined}
                rightSlot={
                  <Pressable onPress={paste} hitSlop={16} accessibilityRole="button" accessibilityLabel="Paste address">
                    <Text style={{ fontFamily: fonts.sans.medium, fontSize: fontSizes.sm, color: colors.ink2 }}>Paste</Text>
                  </Pressable>
                }
              />
              <Button title="Finish" size="lg" fullWidth loading={busy === 'finish'} disabled={!!busy || !answerOk} onPress={finish} />
              {state?.plan_declined || state?.registered ? (
                <Button title="Sign out" variant="ghost" size="md" fullWidth disabled={!!busy} onPress={() => setConfirmSignOut(true)} />
              ) : null}
            </View>
          )}
        </ScrollView>
      </KeyboardPane>
      <ConfirmDialog
        open={confirmSignOut}
        onClose={() => setConfirmSignOut(false)}
        title="Sign out?"
        body={runsOnPlan(profile?.model) ? `@${id} is left without a model.` : `@${id} can no longer use plan models.`}
        confirmLabel="Sign out"
        onConfirm={() => {
          setConfirmSignOut(false);
          signOut();
        }}
      />
    </SafeAreaView>
  );
}
