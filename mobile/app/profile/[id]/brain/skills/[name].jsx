import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { space , fontSizes} from '../../../../../src/theme/tokens';

import { ScreenHeader } from '../../../../../src/components/ScreenHeader';
import { useEndpoint } from '../../../../../src/lib/EndpointContext';
import { useTheme } from '../../../../../src/theme/ThemeContext';

// Skill detail = raw SKILL.md body. ``host.skills.list`` ships only metadata now (saves ~32KB/skill on the wire); the body is fetched on demand via ``host.skill.read``.

export default function SkillDetail() {
  const { id, name, path, category } = useLocalSearchParams();
  const router = useRouter();
  const { colors, fonts, fontSizes } = useTheme();
  const { call } = useEndpoint();
  const [body, setBody] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id || !name) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    const params = { profile: String(id), name: String(name) };
    if (category) params.category = String(category);
    call('host.skill.read', params)
      .then((r) => {
        if (cancelled) return;
        setBody(r?.skill?.body ?? '');
        setLoading(false);
      })
      .catch(() => {
        if (cancelled) return;
        setBody('');
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id, name, category, call]);

  const subtitle = (category ? String(category).toUpperCase() : 'SKILL') + ` · @${id}`;

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader title={String(name ?? 'Skill')} subtitle={subtitle} onBack={() => router.back()} />
      {loading ? (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <ActivityIndicator color={colors.ink3} />
        </View>
      ) : (
        <ScrollView contentContainerStyle={{ padding: space.s8, gap: space.s3, paddingBottom: space.s10 }}>
          {path ? (
            <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink4 }} numberOfLines={1}>
              {String(path)}
            </Text>
          ) : null}
          <Text
            style={{
              fontFamily: fonts.mono,
              fontSize: fontSizes.sm,
              lineHeight: fontSizes.sm * 1.55,
              color: colors.ink,
            }}
          >
            {body || '(empty)'}
          </Text>
        </ScrollView>
      )}
    </SafeAreaView>
  );
}
