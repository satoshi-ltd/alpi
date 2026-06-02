import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { fonts, fontSizes, space } from '../../../src/theme/tokens';

import { Button } from '../../../src/components/Button';
import { Field } from '../../../src/components/Field';
import { Icon } from '../../../src/components/Icon';
import { ScreenHeader } from '../../../src/components/ScreenHeader';
import { useToast } from '../../../src/components/Toast';
import { useDirtyBack } from '../../../src/hooks/useDirtyBack';
import { useWorkgroup } from '../../../src/hooks/useSubject';
import { useEndpoint } from '../../../src/lib/EndpointContext';
import { useTheme } from '../../../src/theme/ThemeContext';
import { AdminGuard } from '../../../src/components/AdminGuard';

export default function EditPipelineRoute() {
  return (
    <AdminGuard>
      <EditPipeline />
    </AdminGuard>
  );
}

// Reorder by tap (↑↓ 44px targets), not drag — tap doesn't fight the scroll on
// touch. Local edits; persist on Save (comma-joined; host splits + validates).
function EditPipeline() {
  const { id } = useLocalSearchParams();
  const router = useRouter();
  const toast = useToast();
  const { call } = useEndpoint();
  const { colors } = useTheme();
  const { workgroup: wg } = useWorkgroup(id);
  const [stages, setStages] = useState([]);
  const [draft, setDraft] = useState('');

  useEffect(() => {
    if (wg?.pipeline != null) setStages(wg.pipeline ?? []);
  }, [wg?.pipeline]);

  const dirty = stages.join(',') !== (wg?.pipeline ?? []).join(',');
  const askBack = useDirtyBack(dirty, () => router.back());

  const move = (i, dir) => {
    const j = i + dir;
    if (j < 0 || j >= stages.length) return;
    const next = [...stages];
    [next[i], next[j]] = [next[j], next[i]];
    setStages(next);
  };
  const remove = (i) => setStages(stages.filter((_, k) => k !== i));
  const add = () => {
    const slug = draft.trim().replace(/^#/, '').toLowerCase();
    if (!slug) return;
    if (!/^[a-z0-9][a-z0-9_-]*$/.test(slug)) {
      toast({ title: `Invalid slug "${slug}"`, duration: 2000 });
      return;
    }
    if (stages.includes(slug)) {
      toast({ title: `"${slug}" is already a stage`, duration: 2000 });
      return;
    }
    setStages([...stages, slug]);
    setDraft('');
  };

  const save = async () => {
    if (!wg) return;
    try {
      await call('host.workgroup.update', { profile: wg.profile, wg_id: id, pipeline: stages.join(',') });
      toast({ title: 'Pipeline saved', duration: 1400 });
      router.back();
    } catch (e) {
      toast({ title: 'Save failed', message: String(e), duration: 2400 });
    }
  };

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader
        title="Pipeline"
        subtitle={`#${wg?.name ?? id} · ${stages.length} ${stages.length === 1 ? 'stage' : 'stages'}`}
        onBack={askBack}
        right={<Button title="Save" size="md" onPress={save} />}
      />
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={{ padding: space.s8, gap: space.s7 }}>
          <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink3, lineHeight: 20 }}>
            The hub opens these tasks in order. When a stage closes with #done, the next opens automatically.
          </Text>

          <View>
            {stages.map((s, i) => (
              <View
                key={s}
                style={{
                  flexDirection: 'row',
                  alignItems: 'center',
                  gap: space.s4,
                  paddingVertical: space.s3,
                  borderTopWidth: 0.5,
                  borderTopColor: colors.line,
                  ...(i === stages.length - 1 ? { borderBottomWidth: 0.5, borderBottomColor: colors.line } : null),
                }}
              >
                <Text style={{ width: 18, fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.ink4 }}>{i + 1}</Text>
                <Text style={{ flex: 1, fontFamily: fonts.mono, fontSize: fontSizes.md, color: colors.ink }}>#{s}</Text>
                <StepBtn dir="up" disabled={i === 0} onPress={() => move(i, -1)} color={colors.ink2} />
                <StepBtn dir="down" disabled={i === stages.length - 1} onPress={() => move(i, 1)} color={colors.ink2} />
                <Pressable
                  onPress={() => remove(i)}
                  hitSlop={8}
                  style={{ width: 44, height: 44, alignItems: 'center', justifyContent: 'center' }}
                  accessibilityLabel={`remove ${s}`}
                >
                  <Text style={{ fontSize: 20, color: colors.danger }}>×</Text>
                </Pressable>
              </View>
            ))}
          </View>

          <View style={{ gap: space.s3 }}>
            <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.xs, letterSpacing: 0.5, color: colors.ink4 }}>
              ADD STAGE
            </Text>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s4 }}>
              <View style={{ flex: 1 }}>
                <Field value={draft} onChangeText={setDraft} autoCapitalize="none" placeholder="stage slug — e.g. research" />
              </View>
              <Button title="Add" size="md" onPress={add} />
            </View>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function StepBtn({ dir, disabled, onPress, color }) {
  return (
    <Pressable
      onPress={disabled ? undefined : onPress}
      hitSlop={8}
      style={{ width: 44, height: 44, alignItems: 'center', justifyContent: 'center', opacity: disabled ? 0.25 : 1 }}
      accessibilityState={{ disabled }}
    >
      <View style={dir === 'up' ? { transform: [{ rotate: '180deg' }] } : null}>
        <Icon name="chevron-down" size={20} color={color} strokeWidth={2} />
      </View>
    </Pressable>
  );
}
