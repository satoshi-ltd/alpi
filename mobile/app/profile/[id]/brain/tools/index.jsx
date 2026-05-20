import { useLocalSearchParams, useRouter } from 'expo-router';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { space , fontSizes} from '../../../../../src/theme/tokens';

import { Row, RowSeparator, SectionHeader } from '../../../../../src/components/Row';
import { ScreenHeader } from '../../../../../src/components/ScreenHeader';
import { useTools } from '../../../../../src/hooks/useDaemonData';
import { useTheme } from '../../../../../src/theme/ThemeContext';

// Same category order as desktop ToolsPanel.
const CATEGORY_ORDER = [
  'Filesystem',
  'Workspace',
  'Web',
  'Memory',
  'Comms',
  'Agent',
  'Media',
  'System',
  'Collab',
];

export default function ToolsList() {
  const { id } = useLocalSearchParams();
  const router = useRouter();
  const { colors, fonts, fontSizes } = useTheme();
  const tools = useTools(id);
  const rows = tools.data?.tools ?? [];

  const groups = rows.reduce((m, t) => {
    const k = t.category ?? 'Other';
    if (!m.has(k)) m.set(k, []);
    m.get(k).push(t);
    return m;
  }, new Map());
  const cats = [
    ...CATEGORY_ORDER.filter((c) => groups.has(c)),
    ...[...groups.keys()].filter((c) => !CATEGORY_ORDER.includes(c)).sort(),
  ];

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader
        title="Tools"
        subtitle={`@${id} · ${rows.length} CALLABLE`}
        onBack={() => router.back()}
      />
      <ScrollView contentContainerStyle={{ paddingBottom: space.s9 }}>
        {tools.loading && rows.length === 0 ? (
          <View style={{ padding: space.s10, alignItems: 'center' }}>
            <ActivityIndicator color={colors.ink3} />
          </View>
        ) : rows.length === 0 ? (
          <Row label="No tools registered" chevron={false} />
        ) : (
          cats.map((cat) => (
            <View key={cat}>
              <SectionHeader>{cat}</SectionHeader>
              {groups.get(cat).map((t, i) => (
                <View key={t.name}>
                  {i > 0 ? <RowSeparator /> : null}
                  <Pressable
                    onPress={() =>
                      router.push({
                        pathname: `/profile/${id}/brain/tools/[name]`,
                        params: { name: t.name },
                      })
                    }
                    android_ripple={{ color: colors.selected }}
                    style={({ pressed }) => ({
                      paddingHorizontal: space.s8,
                      paddingVertical: space.s6,
                      gap: space.s1,
                      backgroundColor: pressed ? colors.selected : 'transparent',
                    })}
                  >
                    <Text style={{ fontFamily: fonts.monoMedium, fontSize: fontSizes.lg, color: colors.ink }}>
                      {t.name}
                    </Text>
                    {t.description ? (
                      <Text numberOfLines={2} style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink3 }}>
                        {t.description}
                      </Text>
                    ) : null}
                  </Pressable>
                </View>
              ))}
            </View>
          ))
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
