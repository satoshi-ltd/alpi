import { useEffect, useMemo, useRef, useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { lineHeights, space } from '../../theme/tokens';

import { EdgeFade } from '../../components/EdgeFade';
import { Sheet } from '../../components/Sheet';
import { PhaseChip, PhaseMark } from '../workgroups/PhaseChip';
import { phaseJumpable, phaseUnavailable } from '../../lib/workgroupPipelines';
import { phaseCostLine, runChips } from '../../../../common/pipelinePhases.mjs';
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

export function PipelineStrip({ run, phaseMap = null, active = null, profileOf = null, loadedSeqs, onPickSeq }) {
  const { colors, fontSizes } = useTheme();
  const surface = colors.bgPane ?? colors.bg;
  const chips = useMemo(() => runChips(run, phaseMap, active), [run, phaseMap, active]);
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
  useEffect(() => { setPicked(null); }, [run?.pipeline, run?.started_seq, !!run]);
  const onScrollFrame = (e) => {
    const { contentOffset, contentSize, layoutMeasurement } = e.nativeEvent;
    const overflow = contentSize.width - layoutMeasurement.width;
    setEdges({ left: contentOffset.x > 1, right: overflow > 1 && contentOffset.x < overflow - 1 });
  };

  if (!run || chips.length === 0) return null;
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
            <PhaseChip chip={chip} profileOf={profileOf} height={44} hint="Shows the phase" onPress={() => setPicked(chip)} />
          </View>
        ))}
      </ScrollView>
      {edges.left ? <EdgeFade side="left" color={surface} /> : null}
      {edges.right ? <EdgeFade side="right" color={surface} /> : null}
      <Sheet
        open={!!pickedLive}
        onClose={() => setPicked(null)}
        title={pickedLive ? `#${pickedLive.slug}` : ''}
        subtitle={pickedLive ? `${PHASE_WORD[pickedLive.state] ?? pickedLive.state} · ${run.pipeline}` : ''}
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
