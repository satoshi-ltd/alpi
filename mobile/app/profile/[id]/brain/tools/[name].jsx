import { useLocalSearchParams, useRouter } from 'expo-router';
import { useMemo } from 'react';
import { ActivityIndicator, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { radii, space } from '../../../../../src/theme/tokens';

import { Pill } from '../../../../../src/components/Pill';
import { Eyebrow } from '../../../../../src/components/Eyebrow';
import { ScreenHeader } from '../../../../../src/components/ScreenHeader';
import { useTools } from '../../../../../src/hooks/useDaemonData';
import { useTheme } from '../../../../../src/theme/ThemeContext';

function formatType(schema) {
  if (!schema) return '—';
  if (schema.type) return Array.isArray(schema.type) ? schema.type.join('|') : schema.type;
  if (schema.enum) return 'enum';
  return 'any';
}

export default function ToolDetail() {
  const { id, name } = useLocalSearchParams();
  const router = useRouter();
  const { colors, fonts, fontSizes } = useTheme();
  const tools = useTools(id);
  const tool = useMemo(
    () => (tools.data?.tools ?? []).find((t) => t.name === String(name)) ?? null,
    [tools.data, name],
  );

  if (tools.loading && !tools.data) {
    return (
      <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
        <ScreenHeader title={String(name ?? '')} subtitle="TOOL · LOADING" onBack={() => router.back()} />
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <ActivityIndicator color={colors.ink3} />
        </View>
      </SafeAreaView>
    );
  }

  if (!tool) {
    return (
      <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
        <ScreenHeader title={String(name ?? '')} subtitle="TOOL · NOT FOUND" onBack={() => router.back()} />
      </SafeAreaView>
    );
  }

  const props = tool.parameters?.properties || {};
  const required = new Set(tool.parameters?.required || []);
  const params = Object.entries(props);

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader
        title={tool.name}
        subtitle={`${tool.category ?? 'TOOL'} · @${id}`}
        onBack={() => router.back()}
      />
      <ScrollView contentContainerStyle={{ padding: space.s8, gap: space.s6, paddingBottom: space.s10 }}>
        {tool.denied ? (
          <View
            style={{
              padding: space.s5,
              backgroundColor: `${colors.warning}1f`,
              borderRadius: radii.md,
              borderWidth: 0.5,
              borderColor: `${colors.warning}66`,
            }}
          >
            <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.warning, lineHeight: fontSizes.sm * 1.5 }}>
              Denied for this profile via tools.deny in config.yaml. The agent does not see this tool.
            </Text>
          </View>
        ) : null}
        {tool.description ? (
          <Text
            style={{
              fontFamily: fonts.sans.regular,
              fontSize: fontSizes.md,
              color: colors.ink2,
              lineHeight: fontSizes.md * 1.5,
              opacity: tool.denied ? 0.6 : 1,
            }}
          >
            {tool.description}
          </Text>
        ) : null}
        <Eyebrow style={{ marginTop: space.s3 }}>Parameters</Eyebrow>
        {params.length === 0 ? (
          <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink3 }}>
            No parameters
          </Text>
        ) : (
          params.map(([key, schema]) => (
            <View
              key={key}
              style={{
                padding: space.s5,
                gap: space.s2,
                backgroundColor: colors.bgInput,
                borderRadius: radii.md,
              }}
            >
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s3 }}>
                <Text style={{ fontFamily: fonts.monoMedium, fontSize: fontSizes.md, color: colors.ink }}>
                  {key}
                </Text>
                <Pill>{formatType(schema)}</Pill>
                {required.has(key) ? <Pill tone="on">required</Pill> : null}
              </View>
              {schema.description ? (
                <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink2 }}>
                  {schema.description}
                </Text>
              ) : null}
            </View>
          ))
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
