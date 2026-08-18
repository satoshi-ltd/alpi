import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { ScrollView } from 'react-native';
import { KeyboardPane } from '../../../src/components/KeyboardPane';
import { SafeAreaView } from 'react-native-safe-area-context';
import { space } from '../../../src/theme/tokens';

import { Button } from '../../../src/components/Button';
import { Field } from '../../../src/components/Field';
import { ScreenHeader } from '../../../src/components/ScreenHeader';
import { useToast } from '../../../src/components/Toast';
import { useDirtyBack } from '../../../src/hooks/useDirtyBack';
import { useWorkgroup } from '../../../src/hooks/useSubject';
import { useEndpoint } from '../../../src/lib/EndpointContext';
import { useTheme } from '../../../src/theme/ThemeContext';
import { AdminGuard } from '../../../src/components/AdminGuard';

export default function EditBriefingRoute() {
  return (
    <AdminGuard>
      <EditBriefing />
    </AdminGuard>
  );
}

function EditBriefing() {
  const { id } = useLocalSearchParams();
  const router = useRouter();
  const toast = useToast();
  const { call } = useEndpoint();
  const { colors } = useTheme();
  const { workgroup: wg } = useWorkgroup(id);
  const [text, setText] = useState('');

  useEffect(() => {
    if (wg?.briefing != null) setText(wg.briefing);
  }, [wg?.briefing]);

  const dirty = text !== (wg?.briefing ?? '');
  const askBack = useDirtyBack(dirty, () => router.back());

  const save = async () => {
    if (!wg) return;
    try {
      // host.workgroup.update accepts briefing; _action handles only pause/resume/leave.
      await call('host.workgroup.update', {
        profile: wg.profile,
        wg_id: id,
        briefing: text,
      });
      toast({ title: 'Briefing saved', duration: 1400 });
      router.back();
    } catch (e) {
      toast({ title: 'Save failed', message: String(e), duration: 2400 });
    }
  };

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader
        title="Briefing"
        subtitle={`#${id} · WHAT THIS DECIDES`}
        onBack={askBack}
        right={<Button title="Save" size="md" onPress={save} />}
      />
      <KeyboardPane>
        <ScrollView contentContainerStyle={{ padding: space.s8 }}>
          <Field
            value={text}
            onChangeText={setText}
            multiline
            rows={14}
            placeholder="What kind of decisions does this workgroup own…"
          />
        </ScrollView>
      </KeyboardPane>
    </SafeAreaView>
  );
}
