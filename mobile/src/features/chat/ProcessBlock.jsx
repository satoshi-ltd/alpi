import { View } from 'react-native';

import { PANE_PAD_X } from '../../lib/panes';
import { Reasoning } from './Reasoning';
import { ToolModule } from './ToolCallRow';
import { PROCESS_EDGE, PROCESS_GAP } from './processRow';
import { processSteps } from './processSteps';

const edgesAt = (i, n) => ({ top: i === 0, bottom: i === n - 1 });

export function ProcessBlock({ turn, tools, reasoning, seconds, reasoningLive, answered, showReasoning, accent }) {
  const steps = processSteps(turn, { tools, reasoning, seconds, streaming: reasoningLive, hasReasoning: showReasoning });
  if (!steps.length) return null;
  return (
    <View
      testID="process-block"
      style={{ paddingHorizontal: PANE_PAD_X, paddingVertical: PROCESS_EDGE, marginVertical: -PROCESS_EDGE, gap: PROCESS_GAP }}
    >
      {steps.map((step, i) => (step.kind === 'tools' ? (
        <ToolModule key={step.key} tools={step.tools} accent={accent} edges={edgesAt(i, steps.length)} />
      ) : (
        <Reasoning
          key={step.key}
          text={step.text}
          seconds={step.seconds}
          timeline={step.timeline}
          streaming={step.streaming}
          answered={answered}
          edges={edgesAt(i, steps.length)}
        />
      )))}
    </View>
  );
}
