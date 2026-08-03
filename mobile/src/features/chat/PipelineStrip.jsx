import { useMemo, useRef, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { fontSizes, radii, space } from '../../theme/tokens';

import { ActionSheet } from '../../components/ActionSheet';
import { Dot } from '../../components/Dot';
import { Icon } from '../../components/Icon';
import {
  activePhaseIndex,
  runActionLabel,
  runPhases,
  runStateLabel,
  triggerBlock,
  triggerSummary,
  triggerableChains,
} from '../../lib/workgroupPipelines';
import { useTheme } from '../../theme/ThemeContext';

const SCROLL_LEAD = 24;

const STYLES = StyleSheet.create({
  strip: {
    flexGrow: 0,
    flexShrink: 0,
  },
  content: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.s3,
    paddingHorizontal: space.s7,
    paddingVertical: space.s4,
  },
  label: {
    fontSize: fontSizes.xs,
    letterSpacing: 0.8,
    textTransform: 'uppercase',
  },
  separator: {
    fontSize: fontSizes.sm,
    marginRight: space.s3,
  },
  phaseWrap: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  phase: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.s1,
  },
  phaseBlocked: {
    borderRadius: radii.pill,
    paddingHorizontal: space.s3,
    paddingVertical: 2,
  },
  slug: {
    fontSize: fontSizes.sm,
  },
  slugSkipped: {
    textDecorationLine: 'line-through',
  },
  launcher: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.s4,
    paddingHorizontal: space.s7,
    paddingTop: space.s3,
    paddingBottom: space.s4,
  },
  launchButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.s2,
    height: 28,
    paddingHorizontal: space.s4,
    borderWidth: 0.5,
    borderRadius: radii.pill,
  },
  launchLabel: {
    fontSize: fontSizes.xs,
  },
  launchNote: {
    flex: 1,
    fontSize: fontSizes.xs,
  },
});

function Phase({ phase, accent, onPress }) {
  const { colors, fonts } = useTheme();
  const { slug, state } = phase;
  const icon =
    state === 'completed' ? <Icon name="check" size={12} color={colors.success} />
    : state === 'skipped' ? <Icon name="x" size={12} color={colors.warning} />
    : state === 'blocked' ? <Icon name="ban" size={12} color={colors.danger} />
    : state === 'current' ? <Dot color={accent ?? colors.ink} pulse />
    : null;
  const textColor =
    state === 'blocked' ? colors.danger
    : state === 'current' ? accent
    : state === 'skipped' ? colors.ink4 ?? colors.ink3
    : state === 'pending' ? colors.ink3
    : colors.ink2;
  const Wrapper = onPress ? Pressable : View;
  return (
    <Wrapper
      onPress={onPress}
      accessibilityLabel={`#${slug} ${state}`}
      style={[
        STYLES.phase,
        state === 'blocked' && STYLES.phaseBlocked,
        state === 'blocked' && { backgroundColor: `${colors.danger}17` },
      ]}
    >
      {icon}
      <Text
        style={[
          STYLES.slug,
          state === 'skipped' && STYLES.slugSkipped,
          { fontFamily: fonts.mono, color: textColor },
        ]}
      >
        #{slug}
      </Text>
    </Wrapper>
  );
}

export function PipelineStrip({ run, accent, onPickSeq }) {
  const { colors, fonts } = useTheme();
  const scrollRef = useRef(null);
  const phases = useMemo(() => runPhases(run), [run]);
  const active = useMemo(() => activePhaseIndex(phases), [phases]);

  if (!run || phases.length === 0) return null;

  return (
    <ScrollView
      ref={scrollRef}
      horizontal
      showsHorizontalScrollIndicator={false}
      style={STYLES.strip}
      contentContainerStyle={STYLES.content}
    >
      <Text style={[STYLES.label, { fontFamily: fonts.mono, color: colors.ink3 }]}>
        {run.pipeline}
      </Text>
      {phases.map((p, i) => (
        <View
          key={p.slug}
          style={STYLES.phaseWrap}
          onLayout={(e) => {
            if (i !== active) return;
            const x = Math.max(0, e.nativeEvent.layout.x - SCROLL_LEAD);
            scrollRef.current?.scrollTo?.({ x, animated: false });
          }}
        >
          {i > 0 ? <Text style={[STYLES.separator, { color: colors.ink4 ?? colors.ink3 }]}>›</Text> : null}
          <Phase
            phase={p}
            accent={accent}
            onPress={p.seq != null && onPickSeq ? () => onPickSeq(p.seq) : undefined}
          />
        </View>
      ))}
    </ScrollView>
  );
}

export function PipelineLauncher({ workgroup, tasks, accent, onRun }) {
  const { colors, fonts } = useTheme();
  const [pickerOpen, setPickerOpen] = useState(false);
  const [target, setTarget] = useState(null);
  const chains = useMemo(() => triggerableChains(workgroup), [workgroup]);
  const block = triggerBlock(workgroup, tasks);
  const run = tasks?.pipeline_run ?? null;

  if (chains.length === 0 || block?.reason === 'not-hub') return null;

  return (
    <View style={STYLES.launcher}>
      <Pressable
        onPress={block ? undefined : () => setPickerOpen(true)}
        disabled={!!block}
        accessibilityLabel="run a pipeline"
        style={[
          STYLES.launchButton,
          { borderColor: colors.line2, backgroundColor: colors.bgInput, opacity: block ? 0.5 : 1 },
        ]}
      >
        <Icon name="play" size={11} color={block ? colors.ink4 ?? colors.ink3 : accent ?? colors.ink} />
        <Text style={[STYLES.launchLabel, { fontFamily: fonts.monoMedium, color: colors.ink }]}>
          Run pipeline
        </Text>
      </Pressable>
      <Text numberOfLines={1} style={[STYLES.launchNote, { fontFamily: fonts.mono, color: colors.ink3 }]}>
        {block
          ? block.message
          : `${chains.length} ${chains.length === 1 ? 'chain' : 'chains'} declared by the recipe`}
      </Text>
      <ActionSheet
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        title="Run pipeline"
        subtitle="DECLARED BY THE RECIPE"
        description="Pick the chain to start. The hub authors the opening task from the recipe."
        actions={chains.map((chain) => ({
          id: chain.key,
          label: `#${chain.key}`,
          detail:
            runStateLabel(chain.key, run) ??
            `${chain.phases.length} ${chain.phases.length === 1 ? 'phase' : 'phases'}`,
          icon: <Icon name="play" size={20} color={colors.ink} />,
          onPress: () => setTarget(chain),
        }))}
      />
      <ActionSheet
        open={!!target}
        onClose={() => setTarget(null)}
        title={target ? `${runActionLabel(target.key, run)} #${target.key}` : ''}
        subtitle="PIPELINE TRIGGER"
        description={target ? triggerSummary(target, run) : undefined}
        actions={
          target
            ? [
                {
                  id: 'run',
                  label: `${runActionLabel(target.key, run)} #${target.key}`,
                  icon: <Icon name="play" size={20} color={colors.ink} />,
                  onPress: () => onRun?.(target),
                },
              ]
            : []
        }
      />
    </View>
  );
}
