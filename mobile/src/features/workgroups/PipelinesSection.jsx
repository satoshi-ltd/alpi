import { StyleSheet, Text, View } from 'react-native';
import { lineHeights, space } from '../../theme/tokens';

import { RowGroup, SectionHeader } from '../../components/Row';
import { PhaseChip } from './PhaseChip';
import { isLaunchless } from '../../lib/workgroupPipelines';
import { chainChips, orderedPipelines, pipelineTrigger, runSummary, runSummaryLine } from '../../../../common/pipelinePhases.mjs';
import { useTheme } from '../../theme/ThemeContext';
import { EMPTY } from '../../../../common/emptyCopy.mjs';

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
  step: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.s2,
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

function Phases({ chips, profileOf }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <View style={STYLES.chips}>
      {chips.map((chip, i) => (
        <View key={chip.slug} style={STYLES.step}>
          <PhaseChip chip={chip} profileOf={profileOf} />
          {i < chips.length - 1 ? <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>→</Text> : null}
        </View>
      ))}
    </View>
  );
}

export function PipelinesSection({ workgroup, run = null, profileOf = null }) {
  const { colors, fonts, fontSizes } = useTheme();
  const chains = orderedPipelines(workgroup?.pipelines, workgroup?.launch_pipeline);

  return (
    <>
      <SectionHeader>Pipelines · declared by the recipe</SectionHeader>
      {chains.length === 0 ? (
        <Note>
          {workgroup?.needs_relaunch
            ? `${EMPTY.retiredPipelines.title}. ${EMPTY.retiredPipelines.hint}`
            : `${EMPTY.noPipelines.title}. ${EMPTY.noPipelines.hint}`}
        </Note>
      ) : (
        <View style={{ gap: space.s4 }}>
          {chains.map((chain) => (
            <RowGroup key={chain.key}>
              <View style={STYLES.head}>
                <Text style={{ fontFamily: fonts.monoSemibold, fontSize: fontSizes.md, color: colors.ink }}>{chain.key}</Text>
                <Text style={[STYLES.key, { fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink3 }]}>
                  {pipelineTrigger(chain.isLaunch)}
                </Text>
              </View>
              {runSummary(run, chain.key) ? (
                <Text style={{ paddingHorizontal: space.s8, paddingTop: space.s2, fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink2 }}>
                  {runSummaryLine(runSummary(run, chain.key))}
                </Text>
              ) : null}
              <Phases chips={chainChips(chain.phases, workgroup?.phase_map, run)} profileOf={profileOf} />
            </RowGroup>
          ))}
        </View>
      )}
      {isLaunchless(workgroup) ? (
        <Note>{EMPTY.launchPipeline.title}. {EMPTY.launchPipeline.hint}</Note>
      ) : null}
      {chains.length > 0 ? (
        <Note>Read-only — a recipe declares these chains.</Note>
      ) : null}
    </>
  );
}
