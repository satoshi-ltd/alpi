import { useEffect, useMemo, useRef, useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { lineHeights, space } from '../../theme/tokens';

import { EdgeFade } from '../../components/EdgeFade';
import { SkeletonBar } from '../../components/SkeletonBar';
import { Sheet } from '../../components/Sheet';
import { PhaseChip, PhaseMark } from '../workgroups/PhaseChip';
import { phaseJumpable, phaseUnavailable } from '../../lib/workgroupPipelines';
import { chainChips, orderedPipelines, phaseCostLine, phaseTask, runChips } from '../../../../common/pipelinePhases.mjs';
import { useTheme } from '../../theme/ThemeContext';

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
    paddingVertical: space.s1,
  },
  step: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.s3,
  },
  who: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.s3,
  },
  detail: {
    gap: space.s5,
    paddingBottom: space.s4,
  },

});

const PHASE_WORD = { completed: 'completed', current: 'running', skipped: 'skipped', blocked: 'blocked', pending: 'pending' };

const PLACEHOLDER_WIDTHS = [62, 70, 66, 70, 74];
const CHIP_H = 44;

const CHAIN_STATUSES = new Set(['running', 'between']);
const SETTLED_STATUSES = new Set(['blocked', 'completed']);

export function stripPlan({ run, pending = false, mode = false, status = null, pipelines = null, launch = null, phaseMap = null, active = null }) {
  if (run) return { chips: runChips(run, phaseMap, active), pipeline: run.pipeline ?? '' };
  const nothing = { chips: [], pipeline: '' };
  if (!pending || !mode || !(CHAIN_STATUSES.has(status) || SETTLED_STATUSES.has(status))) return nothing;
  const chains = orderedPipelines(pipelines, launch);
  if (chains.length === 0) return nothing;
  if (chains.length === 1 && CHAIN_STATUSES.has(status)) {
    const chips = chainChips(chains[0].phases, phaseMap, null).map((c) => ({ ...c, assignee: null, seq: null, cost: null, task: phaseTask(phaseMap, c.slug) }));
    return { chips, pipeline: chains[0].key };
  }
  return { ...nothing, placeholders: Math.min(chains[0].phases.length, PLACEHOLDER_WIDTHS.length) };
}

function Placeholders({ count }) {
  const { colors, fontSizes } = useTheme();
  return (
    <View testID="strip-placeholder" accessible accessibilityRole="progressbar" accessibilityLabel="Loading the pipeline" style={[STYLES.content, { overflow: 'hidden' }]}>
      {Array.from({ length: count }, (_, i) => (
        <View key={i} style={STYLES.step}>
          {i > 0 ? <Text style={{ fontSize: fontSizes.xs, color: colors.ink4 ?? colors.ink3 }}>›</Text> : null}
          <SkeletonBar width={PLACEHOLDER_WIDTHS[i]} height={CHIP_H} delay={i * 80} />
        </View>
      ))}
    </View>
  );
}

export function centreOffset(chip, viewport) {
  return Math.max(0, chip.x + chip.width / 2 - viewport / 2);
}

export function focusIndex(chips) {
  const live = chips.findIndex((c) => c.state === 'current' || c.state === 'blocked');
  if (live >= 0) return live;
  let last = -1;
  chips.forEach((c, i) => { if (c.state === 'completed' || c.state === 'skipped') last = i; });
  return Math.max(0, last);
}

function Who({ name, note, profileOf }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <View style={STYLES.who}>
      <PhaseMark name={name} profileOf={profileOf} size={16} />
      <Text style={{ fontFamily: fonts.monoSemibold, fontSize: fontSizes.md, color: colors.ink }}>@{name}</Text>
      <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink3 }}>{note}</Text>
    </View>
  );
}

function PhaseDetail({ chip, profileOf, jumpable }) {
  const { colors, fonts, fontSizes } = useTheme();
  const cost = phaseCostLine(chip.cost);
  const meta = { fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.ink2 };
  return (
    <View style={STYLES.detail}>
      {chip.owner ? <Who name={chip.owner} note="declared owner" profileOf={profileOf} /> : null}
      {chip.assignee ? <Who name={chip.assignee} note="assigned by the hub" profileOf={profileOf} /> : null}
      {chip.task ? (
        <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.md, lineHeight: fontSizes.md * lineHeights.normal, color: colors.ink }}>{chip.task}</Text>
      ) : null}
      {cost ? <Text style={meta}>{cost}</Text> : null}
      <Text style={meta}>{jumpable ? `opened at post #${chip.seq}` : phaseUnavailable(chip)}</Text>
    </View>
  );
}

export function PipelineStrip({ run, phaseMap = null, active = null, pending = false, mode = false, status = null, pipelines = null, launch = null, profileOf = null, loadedSeqs, onPickSeq }) {
  const { colors, fontSizes } = useTheme();
  const surface = colors.bgPane ?? colors.bg;
  const plan = useMemo(() => stripPlan({ run, pending, mode, status, pipelines, launch, phaseMap, active }), [run, pending, mode, status, pipelines, launch, phaseMap, active]);
  const chips = plan.chips;
  const focus = focusIndex(chips);
  const scrollRef = useRef(null);
  const viewport = useRef(0);
  const focusLayout = useRef(null);
  const centre = () => {
    if (!focusLayout.current || !viewport.current) return;
    scrollRef.current?.scrollTo?.({ x: centreOffset(focusLayout.current, viewport.current), animated: false });
  };
  const [edges, setEdges] = useState({ left: false, right: false });
  const [picked, setPicked] = useState(null);
  const identity = run ? `${run.pipeline}|${run.started_seq}` : plan.pipeline;
  const shownIdentity = useRef(identity);
  useEffect(() => {
    const before = shownIdentity.current;
    shownIdentity.current = identity;
    if (before !== identity && !(run && before === run.pipeline)) setPicked(null);
  }, [identity, run]);
  const onScrollFrame = (e) => {
    const { contentOffset, contentSize, layoutMeasurement } = e.nativeEvent;
    const overflow = contentSize.width - layoutMeasurement.width;
    setEdges({ left: contentOffset.x > 1, right: overflow > 1 && contentOffset.x < overflow - 1 });
  };

  if (plan.placeholders) return <Placeholders count={plan.placeholders} />;
  if (chips.length === 0) return null;
  const pickedLive = picked ? chips.find((c) => c.slug === picked.slug) ?? null : null;
  const pickedJumpable = !!pickedLive && !!onPickSeq && phaseJumpable(pickedLive, loadedSeqs);

  return (
    <View testID="strip">
      <ScrollView
        ref={scrollRef}
        horizontal
        showsHorizontalScrollIndicator={false}
        scrollEventThrottle={16}
        onScroll={onScrollFrame}
        onLayout={(e) => { viewport.current = e.nativeEvent.layout.width; centre(); }}
        onContentSizeChange={(w, h) => onScrollFrame({ nativeEvent: {
          contentOffset: { x: 0 }, contentSize: { width: w, height: h }, layoutMeasurement: { width: viewport.current },
        } })}
        style={STYLES.strip}
        contentContainerStyle={STYLES.content}
      >
        {chips.map((chip, i) => (
          <View
            key={chip.slug}
            style={STYLES.step}
            onLayout={(e) => {
              if (i !== focus) return;
              focusLayout.current = e.nativeEvent.layout;
              centre();
            }}
          >
            {i > 0 ? (
              <Text
                accessibilityElementsHidden
                importantForAccessibility="no-hide-descendants"
                style={{ fontSize: fontSizes.xs, color: colors.ink4 ?? colors.ink3 }}
              >
                ›
              </Text>
            ) : null}
            <PhaseChip chip={chip} profileOf={profileOf} height={CHIP_H} hint="Shows the phase" onPress={() => setPicked(chip)} />
          </View>
        ))}
      </ScrollView>
      {edges.left ? <EdgeFade side="left" color={surface} /> : null}
      {edges.right ? <EdgeFade side="right" color={surface} /> : null}
      <Sheet
        open={!!pickedLive}
        onClose={() => setPicked(null)}
        title={pickedLive ? `#${pickedLive.slug}` : ''}
        subtitle={pickedLive ? `${PHASE_WORD[pickedLive.state] ?? pickedLive.state} · ${plan.pipeline}` : ''}
        primaryAction={pickedJumpable ? {
          label: `Jump to #${pickedLive.slug}`,
          onPress: () => {
            const seq = pickedLive.seq;
            setPicked(null);
            onPickSeq(seq);
          },
        } : undefined}
      >
        {pickedLive ? <PhaseDetail chip={pickedLive} profileOf={profileOf} jumpable={pickedJumpable} /> : null}
      </Sheet>
    </View>
  );
}
