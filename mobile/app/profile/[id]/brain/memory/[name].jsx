import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { space , fontSizes} from '../../../../../src/theme/tokens';

import { ScreenHeader } from '../../../../../src/components/ScreenHeader';
import { useEndpoint } from '../../../../../src/lib/EndpointContext';
import { useTheme } from '../../../../../src/theme/ThemeContext';

// `§` on its own line is alpi's v2 memory entry delimiter (alpi/memory.py). Strip them for display so the file reads as continuous prose, same as desktop MemoryPanel does.
function stripMemoryDelimiters(text) {
  return text.replace(/^§$/gm, '').replace(/\n{3,}/g, '\n\n');
}

export default function MemoryDetail() {
  const { id, name, label, helper } = useLocalSearchParams();
  const router = useRouter();
  const { colors, fonts, fontSizes } = useTheme();
  const { call } = useEndpoint();
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id || !name) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    call('host.profile.read_file', { profile: id, rel_path: `memories/${name}` })
      .then((r) => {
        if (cancelled) return;
        setText(stripMemoryDelimiters(r?.text ?? ''));
        setLoading(false);
      })
      .catch(() => {
        if (cancelled) return;
        setText('');
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id, name, call]);

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader
        title={String(label ?? name ?? 'Memory')}
        subtitle={String(helper ?? `@${id}`)}
        onBack={() => router.back()}
      />
      {loading ? (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <ActivityIndicator color={colors.ink3} />
        </View>
      ) : (
        <ScrollView contentContainerStyle={{ padding: space.s8, gap: space.s3, paddingBottom: space.s10 }}>
          <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink4 }}>
            memories/{String(name)}
          </Text>
          <Text
            style={{
              fontFamily: fonts.mono,
              fontSize: fontSizes.sm,
              lineHeight: fontSizes.sm * 1.55,
              color: colors.ink,
            }}
          >
            {text || '(empty)'}
          </Text>
        </ScrollView>
      )}
    </SafeAreaView>
  );
}
