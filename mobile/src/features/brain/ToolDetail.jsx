import { useMemo } from 'react';
import { ScrollView, Text, View } from 'react-native';
import { DeadEnd } from '../../components/DeadEnd';
import { radii, space } from '../../theme/tokens';

import { Pill } from '../../components/Pill';
import { Eyebrow } from '../../components/Eyebrow';
import { ScreenHeader } from '../../components/ScreenHeader';
import { PanelHeader } from '../profile/PanelHeader';
import { useTools } from '../../hooks/useDaemonData';
import { useTheme } from '../../theme/ThemeContext';
import { Busy } from '../../components/Busy';
import { useBusyVisible } from '../../hooks/useBusyVisible';
import { SubtitleSkeleton } from '../../components/SubtitleSkeleton';
import { DetailHead } from '../../components/DetailHead';
import { FactTable } from '../../components/FactTable';
import { code } from '../../theme/code';

function formatType(schema) {
  if (!schema) return '—';
  if (schema.type) return Array.isArray(schema.type) ? schema.type.join('|') : schema.type;
  if (schema.enum) return 'enum';
  return 'any';
}

export function ToolDetail({ profile: id, name, embedded = false, onBack }) {
  const { colors, fonts, fontSizes } = useTheme();
  const tools = useTools(id);
  const tool = useMemo(
    () => (tools.data?.tools ?? []).find((t) => t.name === String(name)) ?? null,
    [tools.data, name],
  );
  const opening = tools.loading && !tools.data;
  const holding = useBusyVisible(opening);

  if (opening || holding) {
    return (
      <View style={{ flex: 1 }}>
        {embedded ? null : <ScreenHeader title={String(name ?? '')} subtitle={<SubtitleSkeleton />} onBack={onBack} />}
        <Busy fill visible={holding} label="Opening the tool" />
      </View>
    );
  }

  if (!tool) {
    return (
      <View style={{ flex: 1 }}>
        {embedded ? null : <ScreenHeader title={String(name ?? '')} subtitle="Tool · not found" onBack={onBack} />}
        <DeadEnd copy="missingTool" error={tools.error} onRetry={tools.refresh} label="this tool" />
      </View>
    );
  }

  const props = tool.parameters?.properties || {};
  const required = new Set(tool.parameters?.required || []);
  const params = Object.entries(props);

  return (
    <View style={{ flex: 1 }}>
      {embedded ? null : <PanelHeader profile={id} section={tool.category ? `Tools · ${String(tool.category)}` : 'Tools'} onBack={onBack} />}
      <ScrollView contentContainerStyle={{ padding: space.s8, gap: space.s6, paddingBottom: space.s10 }}>
        <DetailHead
          title={tool.name}
          state={tool.denied ? 'denied' : null}
          id={tool.name}
        />
        {tool.denied ? (
          <View
            style={{
              padding: space.s5,
              backgroundColor: `${colors.warning}1f`,
              borderRadius: radii.surface,
            }}
          >
            <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.warningText, lineHeight: fontSizes.sm * 1.5 }}>
              Denied for this profile via tools.deny in config.yaml. The agent does not see this tool.
            </Text>
          </View>
        ) : null}
        <FactTable
          rows={[
            { label: 'About', value: tool.description || null },
            { label: 'Category', value: tool.category || null },
          ]}
        />
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
                backgroundColor: colors.field,
                borderRadius: radii.surface,
              }}
            >
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s3 }}>
                <Text style={{ ...code(fonts, fontSizes.md, 'medium'), color: colors.ink }}>
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
    </View>
  );
}
