import { useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { lineHeights, space } from '../../../../src/theme/tokens';

import { RichText } from '../../../../src/components/RichText';
import { PanelHeader } from '../../../../src/features/profile/PanelHeader';
import { useBack } from '../../../../src/hooks/useBack';
import { useEndpoint } from '../../../../src/lib/EndpointContext';
import { fileSize } from '../../../../src/lib/skillDetail';
import { useTheme } from '../../../../src/theme/ThemeContext';
import { ReaderSkeleton } from '../../../../src/components/ReaderSkeleton';

export default function SkillFile() {
  const { id, name, category, file } = useLocalSearchParams();
  const goBack = useBack();
  const { colors, fonts, fontSizes } = useTheme();
  const { call } = useEndpoint();
  const [state, setState] = useState({ loading: true, file: null, error: null });

  useEffect(() => {
    if (!id || !name || !file) return undefined;
    let cancelled = false;
    const params = { profile: String(id), name: String(name), path: String(file) };
    if (category) params.category = String(category);
    call('host.skill.file', params)
      .then((r) => { if (!cancelled) setState({ loading: false, file: r?.file ?? null, error: null }); })
      .catch((e) => { if (!cancelled) setState({ loading: false, file: null, error: String(e?.message ?? e) }); });
    return () => { cancelled = true; };
  }, [id, name, category, file, call]);

  const f = state.file;
  const markdown = f && !f.binary && (f.ftype === 'md' || f.ftype === 'skill');
  const meta = { fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 };

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <PanelHeader profile={id} section={`SKILLS · ${String(name ?? '').toUpperCase()}`} onBack={goBack} />
      {state.loading ? (
        <ReaderSkeleton label="Loading the file" />
      ) : !f ? (
        <View style={{ padding: space.s8, gap: space.s2 }}>
          <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.md, color: colors.ink2 }}>Could not open {String(file)}</Text>
          {state.error ? <Text style={meta}>{state.error}</Text> : null}
        </View>
      ) : (
        <ScrollView contentContainerStyle={{ padding: space.s8, gap: space.s5, paddingBottom: space.s10 }}>
          <View style={{ gap: space.s1 }}>
            <Text style={{ fontFamily: fonts.monoSemibold ?? fonts.mono, fontSize: fontSizes.md, color: colors.ink }}>{String(file)}</Text>
            <Text style={meta}>{[fileSize(f.size), f.truncated ? 'truncated' : null].filter(Boolean).join(' · ')}</Text>
          </View>
          {f.binary ? (
            <Text style={meta}>Binary file · not shown</Text>
          ) : markdown ? (
            <RichText size={fontSizes.md} color={colors.ink}>{f.text ?? ''}</RichText>
          ) : (
            <Text selectable style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, lineHeight: fontSizes.sm * lineHeights.cozy, color: colors.ink }}>
              {f.text ?? ''}
            </Text>
          )}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}
