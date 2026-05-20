import { useLocalSearchParams, useRouter } from 'expo-router';
import { ActivityIndicator, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { space } from '../../../../../src/theme/tokens';

import { Row, RowSeparator } from '../../../../../src/components/Row';
import { ScreenHeader } from '../../../../../src/components/ScreenHeader';
import { useProfileMemory } from '../../../../../src/hooks/useDaemonData';
import { useTheme } from '../../../../../src/theme/ThemeContext';

// Same three files the desktop MemoryPanel loads (USER.md, MEMORY.md, AGENT.md) — files alpi reads on every turn.
const FILES = [
  { name: 'USER.md', label: 'About you', helper: 'Things alpi knows about you' },
  { name: 'MEMORY.md', label: 'Memories', helper: 'Things alpi has learned' },
  { name: 'AGENT.md', label: 'Identity', helper: 'Things alpi is' },
];

function humanBytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export default function MemoryList() {
  const { id } = useLocalSearchParams();
  const router = useRouter();
  const { colors } = useTheme();
  const mem = useProfileMemory(id);

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader
        title="Memories"
        subtitle={`@${id} · LOADED EVERY TURN`}
        onBack={() => router.back()}
      />
      <ScrollView contentContainerStyle={{ paddingBottom: space.s9 }}>
        {mem.loading && !mem.data ? (
          <View style={{ padding: space.s10, alignItems: 'center' }}>
            <ActivityIndicator color={colors.ink3} />
          </View>
        ) : (
          FILES.map((f, i) => {
            const text = mem.data?.[f.name] ?? '';
            const size = text ? humanBytes(text.length) : 'empty';
            return (
              <View key={f.name}>
                {i > 0 ? <RowSeparator /> : null}
                <Row
                  label={f.label}
                  helper={f.helper}
                  value={size}
                  onPress={() =>
                    router.push({
                      pathname: `/profile/${id}/brain/memory/[name]`,
                      params: { name: f.name, label: f.label, helper: f.helper },
                    })
                  }
                />
              </View>
            );
          })
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
