import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { space , fontSizes} from '../../../src/theme/tokens';

import { Button } from '../../../src/components/Button';
import { Field } from '../../../src/components/Field';
import { ScreenHeader } from '../../../src/components/ScreenHeader';
import { useToast } from '../../../src/components/Toast';
import { useDirtyBack } from '../../../src/hooks/useDirtyBack';
import { useProfile } from '../../../src/hooks/useSubject';
import { useEndpoint } from '../../../src/lib/EndpointContext';
import { useTheme } from '../../../src/theme/ThemeContext';

export default function EditIdentity() {
  const { id } = useLocalSearchParams();
  const router = useRouter();
  const toast = useToast();
  const { colors, fonts, fontSizes } = useTheme();
  const { call } = useEndpoint();
  const { profile } = useProfile(id);
  const [text, setText] = useState('');
  const [drafting, setDrafting] = useState(false);

  useEffect(() => {
    if (profile?.bio != null) setText(profile.bio);
  }, [profile?.bio]);

  const dirty = text !== (profile?.bio ?? '');
  const askBack = useDirtyBack(dirty, () => router.back());

  const save = async () => {
    try {
      await call('host.config.set_field', { profile: id, key: 'public_bio', value: text });
      toast({ title: 'Identity saved', duration: 1400 });
      router.back();
    } catch (e) {
      toast({ title: 'Save failed', message: String(e), duration: 2400 });
    }
  };

  // host.identity.draft synthesizes from AGENT.md via current LLM; needs cfg.model (else -32010 draft-failed).
  const draft = async () => {
    if (drafting) return;
    if (!profile?.model) {
      toast({ title: 'Set a model first', message: 'Drafting needs an LLM wired up', duration: 2400 });
      return;
    }
    setDrafting(true);
    try {
      const result = await call('host.identity.draft', { profile: id });
      const bio = result?.bio ?? '';
      if (bio) {
        setText(bio);
        toast({ title: 'Drafted from AGENT.md', duration: 1600 });
      } else {
        toast({ title: 'Draft empty', message: 'AGENT.md may be missing or terse', duration: 2400 });
      }
    } catch (e) {
      toast({ title: 'Draft failed', message: String(e) });
    } finally {
      setDrafting(false);
    }
  };

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader
        title="Identity"
        subtitle={`@${id} · PUBLIC BIO`}
        onBack={askBack}
        right={<Button title="Save" size="md" onPress={save} />}
      />
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={{ padding: space.s8, gap: space.s6 }} keyboardShouldPersistTaps="handled">
          <Field
            value={text}
            onChangeText={setText}
            multiline
            rows={12}
            placeholder="one-line public identity — visible to peers"
            autoCapitalize="sentences"
          />
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s5 }}>
            <View style={{ flex: 1 }}>
              <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink4, lineHeight: fontSizes.xs * 1.6 }}>
                Need a starting point? Tap Draft — the agent reads <Text style={{ color: colors.ink2 }}>AGENT.md</Text> and writes a one-liner.
              </Text>
            </View>
            <Button title="Draft" size="md" variant="ghost" onPress={draft} loading={drafting} disabled={drafting} />
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
