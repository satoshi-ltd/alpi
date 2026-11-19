import { useEffect, useRef, useState } from 'react';
import { Pressable, Text, View } from 'react-native';

import { Expand } from '../../components/Expand';
import { Fold } from '../../components/Fold';
import { Icon } from '../../components/Icon';
import { PANE_PAD_X } from '../../lib/panes';
import { useTheme } from '../../theme/ThemeContext';
import { lineHeights, mobile, space } from '../../theme/tokens';
import { MARK_SIZES } from '../../../../common/agentMarks.mjs';
import { pluralize } from '../../../../common/pluralize.mjs';
import { workClock, workSummary } from '../../../../common/workLine.mjs';
import { Reasoning } from './Reasoning';
import { ToolModule } from './ToolCallRow';
import { PROCESS_EDGE, PROCESS_GAP } from './processRow';
import { processSteps } from './processSteps';
import { toolSummary } from './toolDetail';

export const WORK_LINE_H = 36;
export const WORK_MARK = MARK_SIZES.row;
const WORK_GAP = space.s3;
export const WORK_INDENT = WORK_MARK + WORK_GAP;

const edgesAt = (i, n) => ({ top: false, bottom: i === n - 1 });

function useElapsed(running, earliest) {
  const start = useRef(null);
  const [now, setNow] = useState(() => Date.now());
  if (running && start.current == null) start.current = Date.now();
  if (earliest != null && (start.current == null || earliest < start.current)) start.current = earliest;
  useEffect(() => {
    if (!running) return undefined;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [running]);
  return running && start.current != null ? Math.max(0, (now - start.current) / 1000) : null;
}

function toolStart(t) {
  const v = t.started_at ?? t.at;
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

export function workItems(steps) {
  return steps.flatMap((step) => (step.kind === 'tools'
    ? step.tools.map((t) => ({ kind: 'tool', name: t.name, target: toolSummary(t.args), ok: t.ok, seconds: t.duration_s, start: toolStart(t) ?? undefined }))
    : [{ kind: 'thought', text: step.text, seconds: step.seconds, live: !!step.streaming }]));
}

export function workLabel(summary, clock) {
  if (summary.running) return `Working · ${summary.phrase}`;
  const steps = `${summary.steps} ${pluralize(summary.steps, 'step')}`;
  return `${clock ? `Worked for ${clock}` : 'Worked'} · ${steps}${summary.failed ? ` · ${summary.failed} failed` : ''}`;
}

export function ProcessBlock({ turn, tools, reasoning, seconds, reasoningLive, answered, showReasoning, accent, shape, running = false }) {
  return <WorkBlock key={turn?.req ?? 'settled'} turn={turn} tools={tools} reasoning={reasoning} seconds={seconds} reasoningLive={reasoningLive} answered={answered} showReasoning={showReasoning} accent={accent} shape={shape} running={running} />;
}

function WorkBlock({ turn, tools, reasoning, seconds, reasoningLive, answered, showReasoning, accent, shape, running }) {
  const { colors, fonts, fontSizes } = useTheme();
  const [open, setOpen] = useState(false);
  const steps = processSteps(turn, { tools, reasoning, seconds, streaming: reasoningLive, hasReasoning: showReasoning });
  const items = workItems(steps);
  const summary = workSummary(items, { thinking: !!reasoningLive, running, writing: !!answered, note: running ? turn?.note ?? '' : '' });
  const starts = items.filter((i) => i.start != null).map((i) => i.start * 1000);
  if (running && Number.isFinite(turn?.at)) starts.push(turn.at * 1000);
  const elapsed = useElapsed(summary.running, starts.length ? Math.min(...starts) : null);
  if (!steps.length) return null;
  const clock = summary.running ? (elapsed >= 1 ? workClock(Math.floor(elapsed)) : '') : workClock(summary.seconds);
  const text = (color, weight = 'regular') => ({
    fontFamily: fonts.sans[weight],
    fontSize: fontSizes.lg,
    lineHeight: fontSizes.lg * lineHeights.cozy,
    color,
    includeFontPadding: false,
  });
  const stepsText = `${summary.steps} ${pluralize(summary.steps, 'step')}`;
  const slop = (mobile.tap - WORK_LINE_H) / 2;
  return (
    <View
      testID="process-block"
      style={{ paddingHorizontal: PANE_PAD_X, paddingVertical: PROCESS_EDGE, marginVertical: -PROCESS_EDGE, gap: PROCESS_GAP }}
    >
      <Pressable
        testID="work-line"
        onPress={() => setOpen((v) => !v)}
        hitSlop={{ top: slop, bottom: open ? PROCESS_GAP / 2 : slop, left: 0, right: 0 }}
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        accessibilityLabel={workLabel(summary, clock)}
        accessibilityLiveRegion={summary.running ? 'polite' : 'none'}
        style={{ flexDirection: 'row', alignItems: 'center', gap: WORK_GAP, minHeight: WORK_LINE_H }}
      >
        <Fold shape={shape} color={accent} size={WORK_MARK} state={summary.running ? 'working' : 'idle'} />
        <Text numberOfLines={1} style={[text(summary.running ? colors.ink : colors.ink2, 'medium'), { flexShrink: 0 }]}>
          {summary.running ? 'Working' : clock ? `Worked for ${clock}` : 'Worked'}
        </Text>
        <Text numberOfLines={1} style={[text(colors.ink3), { flexShrink: 1 }]}>
          {summary.running ? `${summary.phrase}…` : `· ${stepsText}`}
        </Text>
        {!summary.running && summary.failed > 0 ? (
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s1, flexShrink: 0 }}>
            <Icon name="triangle-alert" size="xs" color={colors.danger} />
            <Text style={text(colors.dangerText)}>{`${summary.failed} failed`}</Text>
          </View>
        ) : null}
        <View style={{ transform: [{ rotate: open ? '90deg' : '0deg' }] }}>
          <Icon name="chevron-right" size="xs" color={colors.ink3} />
        </View>
        {summary.running && clock ? (
          <Text importantForAccessibility="no" accessibilityElementsHidden style={[text(colors.ink3), { marginLeft: 'auto', fontSize: fontSizes.sm, fontVariant: ['tabular-nums'] }]}>{clock}</Text>
        ) : null}
      </Pressable>
      <Expand open={open}>
        <View style={{ paddingLeft: WORK_INDENT, gap: PROCESS_GAP }}>
          {steps.map((step, i) => (step.kind === 'tools' ? (
            <ToolModule key={step.key} tools={step.tools} accent={accent} edges={edgesAt(i, steps.length)} />
          ) : (
            <Reasoning
              key={step.key}
              accent={accent}
              shape={shape}
              text={step.text}
              seconds={step.seconds}
              timeline={step.timeline}
              streaming={step.streaming}
              answered={answered}
              edges={edgesAt(i, steps.length)}
            />
          )))}
        </View>
      </Expand>
    </View>
  );
}
