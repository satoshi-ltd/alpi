import { StyleSheet, Text, View } from 'react-native';
import { lineHeights, radii, space } from '../../theme/tokens';

import { Pill } from '../../components/Pill';
import { RowSeparator, SectionHeader } from '../../components/Row';
import { isLaunchless, namedPipelines } from '../../lib/workgroupPipelines';
import { useTheme } from '../../theme/ThemeContext';

const STYLES = StyleSheet.create({
  head: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.s3,
    paddingHorizontal: space.s8,
    paddingTop: space.s5,
  },
  key: {
    flex: 1,
  },
  chips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: space.s3,
    paddingHorizontal: space.s8,
    paddingVertical: space.s4,
  },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.s2,
    paddingHorizontal: space.s4,
    paddingVertical: space.s2,
    borderWidth: 0.5,
    borderRadius: radii.md,
  },
  note: {
    paddingHorizontal: space.s8,
    paddingVertical: space.s4,
  },
});

function Note({ children }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <View style={STYLES.note}>
      <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, lineHeight: fontSizes.sm * lineHeights.normal, color: colors.ink3 }}>
        {children}
      </Text>
    </View>
  );
}

function Phases({ phases }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <View style={STYLES.chips}>
      {phases.map((slug, i) => (
        <View key={slug} style={[STYLES.chip, { borderColor: colors.line2, backgroundColor: colors.bgInput }]}>
          <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink4 }}>{i + 1}</Text>
          <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.ink }}>#{slug}</Text>
        </View>
      ))}
    </View>
  );
}

export function PipelinesSection({ workgroup }) {
  const { colors, fonts, fontSizes } = useTheme();
  const chains = namedPipelines(workgroup);

  return (
    <>
      <SectionHeader>Pipelines · declared by the recipe</SectionHeader>
      {chains.length === 0 ? (
        <Note>No pipelines · deliberation workgroup</Note>
      ) : (
        chains.map((chain, i) => (
          <View key={chain.key}>
            {i > 0 ? <RowSeparator indent={0} /> : null}
            <View style={STYLES.head}>
              <Text style={[STYLES.key, { fontFamily: fonts.monoSemibold, fontSize: fontSizes.md, color: colors.ink }]}>
                #{chain.key}
              </Text>
              {chain.isLaunch ? <Pill tone="on">launch</Pill> : <Pill off>on demand</Pill>}
            </View>
            <Phases phases={chain.phases} />
          </View>
        ))
      )}
      {isLaunchless(workgroup) ? (
        <Note>No launch pipeline — the hub stays idle until a chain is started from the chat.</Note>
      ) : null}
      {chains.length > 0 ? (
        <Note>Read-only — a recipe declares these chains. Run one from the chat.</Note>
      ) : null}
    </>
  );
}
