import { useMemo, useRef, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { radii, space } from '../../theme/tokens';

import { Dot } from '../../components/Dot';
import { EdgeFade } from '../../components/EdgeFade';
import { Eyebrow } from '../../components/Eyebrow';
import { Icon } from '../../components/Icon';
import { Pill } from '../../components/Pill';
import {
  phaseJumpable,
  phaseUnavailable,
  activePhaseIndex,
  runPhases,
  runStatus,
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
  separator: {
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
  slugSkipped: {
    textDecorationLine: 'line-through',
  },
});

function Phase({ phase, accent, hint, onPress }) {
  const { colors, fonts, fontSizes } = useTheme();
  const { slug, state } = phase;
  const icon =
    state === 'completed' ? <Icon name="check" size="xs" color={colors.success} />
    : state === 'skipped' ? <Icon name="x" size="xs" color={colors.warning} />
    : state === 'blocked' ? <Icon name="ban" size="xs" color={colors.danger} />
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
      accessibilityHint={hint}
      accessibilityState={onPress ? undefined : { disabled: true }}
      style={[
        STYLES.phase,
        state === 'blocked' && STYLES.phaseBlocked,
        state === 'blocked' && { backgroundColor: `${colors.danger}17` },
      ]}
    >
      {icon}
      <Text
        style={[
          state === 'skipped' && STYLES.slugSkipped,
          { fontFamily: fonts.mono, fontSize: fontSizes.sm, color: textColor },
        ]}
      >
        #{slug}
      </Text>
    </Wrapper>
  );
}

export function PipelineStrip({ run, accent, loadedSeqs, onPickSeq }) {
  const { colors, fonts, fontSizes } = useTheme();
  const surface = colors.bgPane ?? colors.bg;
  const phases = useMemo(() => runPhases(run), [run]);
  const active = useMemo(() => activePhaseIndex(phases), [phases]);
  const scrollRef = useRef(null);
  const [edges, setEdges] = useState({ left: false, right: false });
  const onScrollFrame = (e) => {
    const { contentOffset, contentSize, layoutMeasurement } = e.nativeEvent;
    const overflow = contentSize.width - layoutMeasurement.width;
    setEdges({ left: contentOffset.x > 1, right: overflow > 1 && contentOffset.x < overflow - 1 });
  };
  const status = runStatus(run);

  if (!run || phases.length === 0) return null;

  return (
    <View testID="strip">
      <ScrollView
        ref={scrollRef}
        horizontal
        showsHorizontalScrollIndicator={false}
        scrollEventThrottle={16}
        onScroll={onScrollFrame}
        onContentSizeChange={(w, h) => onScrollFrame({ nativeEvent: {
          contentOffset: { x: 0 }, contentSize: { width: w, height: h }, layoutMeasurement: { width: 0 },
        } })}
        style={STYLES.strip}
        contentContainerStyle={STYLES.content}
      >
      <Eyebrow>{`pipeline · ${run.pipeline}`}</Eyebrow>
      {phases.map((p, i) => {
        const canJump = !!onPickSeq && phaseJumpable(p, loadedSeqs);
        return (
          <View
            key={p.slug}
            style={STYLES.phaseWrap}
            onLayout={(e) => {
              if (i !== active) return;
              const x = Math.max(0, e.nativeEvent.layout.x - SCROLL_LEAD);
              scrollRef.current?.scrollTo?.({ x, animated: false });
            }}
          >
            {i > 0 ? (
              <Text
                accessibilityElementsHidden
                importantForAccessibility="no-hide-descendants"
                style={[STYLES.separator, { fontFamily: fonts.sans.regular, fontSize: fontSizes.xs, color: colors.ink4 ?? colors.ink3 }]}
              >
                ›
              </Text>
            ) : null}
            <Phase
              phase={p}
              accent={accent}
              hint={canJump ? `Jump to #${p.slug}` : phaseUnavailable(p)}
              onPress={canJump ? () => onPickSeq(p.seq) : undefined}
            />
          </View>
        );
      })}
        {status ? (
          <Pill tone={status.tone === 'off' ? undefined : status.tone} off={status.tone === 'off'}>
            {status.text}
          </Pill>
        ) : null}
      </ScrollView>
      {edges.left ? <EdgeFade side="left" color={surface} /> : null}
      {edges.right ? <EdgeFade side="right" color={surface} /> : null}
    </View>
  );
}
