import { describe, expect, it } from 'vitest';

import { orderedTools, processSteps, reasoningFirst, reasoningTimeline } from './processSteps';

const kinds = (turn, hasReasoning = true) =>
  processSteps(turn, { tools: orderedTools(turn.tools), hasReasoning }).map((s) => s.kind);

describe('processSteps', () => {
  it('puts the thought first when reasoning preceded the first tool', () => {
    const turn = { tools: [{ name: 'read', reasoning: 'look first', at: 10 }], reasoning: 'look first' };
    expect(kinds(turn)).toEqual(['reasoning', 'tools']);
  });

  it('puts the tools first when reasoning only came after them', () => {
    const turn = { req: 'm-1', pending: true, tools: [{ name: 'read', at: 10, ok: true }], reasoning: 'now summarise' };
    expect(kinds(turn)).toEqual(['tools', 'reasoning']);
  });

  it('streams reasoning alone before any tool starts', () => {
    expect(kinds({ req: 'm-1', pending: true, tools: [], reasoning: 'hmm' })).toEqual(['reasoning']);
  });

  it('reads a stored turn as reasoning-first when reasoned_s reaches the first tool', () => {
    const turn = { at: 100, reasoned_s: 4, tools: [{ name: 'read', at: 104.2 }], reasoning: 'plan' };
    expect(reasoningFirst(turn, turn.tools)).toBe(true);
    expect(kinds(turn)).toEqual(['reasoning', 'tools']);
  });

  it('keeps a stored turn tools-first when it acted before any thinking time', () => {
    const turn = { at: 100, reasoned_s: 0, tools: [{ name: 'read', at: 100.3 }], reasoning: 'afterthought' };
    expect(kinds(turn)).toEqual(['tools', 'reasoning']);
  });

  it('never infers from reasoned_s while the turn streams locally', () => {
    const turn = { req: 'm-1', at: 100, reasoned_s: 1, tools: [{ name: 'read', at: 100.5 }], reasoning: 'late' };
    expect(reasoningFirst(turn, turn.tools)).toBe(false);
  });

  it('drops the reasoning step when there is none, and ask_user never counts as a step', () => {
    expect(kinds({ tools: [{ name: 'read' }] }, false)).toEqual(['tools']);
    expect(kinds({ tools: [{ name: 'ask_user' }] }, false)).toEqual([]);
  });
});

describe('orderedTools', () => {
  it('sorts by start time and keeps arrival order for ties or missing times', () => {
    const tools = [
      { name: 'b', at: 20 },
      { name: 'a', at: 10 },
      { name: 'ask_user', at: 5 },
      { name: 'c', at: 20 },
    ];
    expect(orderedTools(tools).map((t) => t.name)).toEqual(['a', 'b', 'c']);
    expect(orderedTools([{ name: 'x' }, { name: 'y' }]).map((t) => t.name)).toEqual(['x', 'y']);
  });
});

describe('reasoningTimeline', () => {
  it('interleaves reasoning spans with the tool runs between them', () => {
    const tools = [
      { name: 'read', reasoning: 'read the log', at: 1 },
      { name: 'grep', at: 2 },
      { name: 'lint', reasoning: 'try the lint', at: 3 },
    ];
    expect(reasoningTimeline(tools, 'read the log\n\ntry the lint\n\nwrap up')).toEqual([
      { kind: 'text', text: 'read the log' },
      { kind: 'tools', names: ['read', 'grep'] },
      { kind: 'text', text: 'try the lint' },
      { kind: 'tools', names: ['lint'] },
      { kind: 'text', text: 'wrap up' },
    ]);
  });

  it('trims tool runs at either edge so the body opens and closes on reasoning', () => {
    const tools = [{ name: 'read', at: 1 }, { name: 'lint', reasoning: 'check', at: 2 }];
    expect(reasoningTimeline(tools, '')).toEqual([{ kind: 'text', text: 'check' }]);
    expect(reasoningTimeline([{ name: 'read' }], 'after')).toEqual([{ kind: 'text', text: 'after' }]);
  });
});

describe('processSteps with reasoning_spans', () => {
  const run = (turn, streaming = false) => {
    const tools = turn.tools.filter((t) => t.name !== 'ask_user');
    return processSteps(turn, { tools, reasoning: turn.reasoning, seconds: turn.reasoned_s, streaming, hasReasoning: true });
  };
  const shape = (steps) => steps.map((s) => (s.kind === 'tools'
    ? `tools:${s.tools.map((t) => t.name).join(',')}`
    : `thought:${s.seconds ?? '-'}:${s.text}`));

  it('places three spans between two tools, each with its own seconds and text', () => {
    const turn = {
      reasoned_s: 9,
      reasoning: 'plan\n\ncheck\n\nwrap up',
      reasoning_spans: [
        { seconds: 3, before_tool: 0 },
        { seconds: 2.5, before_tool: 1 },
        { seconds: 1.5, before_tool: 2 },
      ],
      tools: [
        { name: 'read', reasoning: 'plan', at: 5 },
        { name: 'grep', reasoning: 'check', at: 2 },
      ],
    };
    expect(shape(run(turn))).toEqual(['thought:3:plan', 'tools:read', 'thought:2.5:check', 'tools:grep', 'thought:1.5:wrap up']);
  });

  it('puts a span that closed before the answer after every tool', () => {
    const turn = {
      reasoning: 'summing up',
      reasoning_spans: [{ seconds: 4, before_tool: 2 }],
      tools: [{ name: 'read', at: 1 }, { name: 'ask_user', at: 2 }],
    };
    expect(shape(run(turn))).toEqual(['tools:read', 'thought:4:summing up']);
  });

  it('merges spans that share a slot and clamps an index past the tools', () => {
    const turn = {
      reasoning: 'a\n\nb',
      reasoning_spans: [{ seconds: 1, before_tool: 0 }, { seconds: 2, before_tool: 0 }, { seconds: 5, before_tool: 9 }],
      tools: [{ name: 'read', reasoning: 'a' }],
    };
    expect(shape(run(turn))).toEqual(['thought:3:a', 'tools:read', 'thought:5:b']);
  });

  it('streams the live span after the last tool', () => {
    const turn = { req: 'm-1', reasoning: 'hmm', reasoning_spans: [{ seconds: 2, before_tool: 0 }], tools: [{ name: 'read', reasoning: 'plan' }] };
    const steps = run(turn, true);
    expect(shape(steps)).toEqual(['thought:2:plan', 'tools:read', 'thought:-:hmm']);
    expect(steps.map((s) => !!s.streaming)).toEqual([false, false, true]);
  });

  it('falls back to one thought row placed by the heuristic when the field is absent', () => {
    const turn = { at: 100, reasoned_s: 4, reasoning: 'plan', tools: [{ name: 'read', at: 104 }, { name: 'grep', at: 105 }] };
    expect(shape(run(turn))).toEqual(['thought:4:plan', 'tools:read,grep']);
    expect(run({ ...turn, reasoning_spans: [] })[0].timeline).toBeDefined();
  });
});

describe('processSteps keys', () => {
  it('keeps the same keys when the first reasoning_done turns the fallback into spans', () => {
    const tools = [{ name: 'read', tool_id: 't1', reasoning: 'plan' }, { name: 'grep', tool_id: 't2' }];
    const live = { req: 'm-1', pending: true, reasoning: '', tools };
    const keys = (turn, streaming = false) =>
      processSteps(turn, { tools, reasoning: 'plan', hasReasoning: true, streaming }).map((s) => s.key);
    expect(keys(live)).toEqual(['r0', 't:t1']);
    expect(keys({ ...live, reasoning_spans: [{ seconds: 2, before_tool: 0 }] })).toEqual(['r0', 't:t1']);
    expect(keys({ ...live, reasoning: 'more', reasoning_spans: [{ seconds: 2, before_tool: 0 }] }, true)).toEqual(['r0', 't:t1', 'r1']);
  });
});

function storedDaemonTurn(overrides = {}) {
  return {
    at: 100,
    reasoned_s: 3,
    reasoning: 'weigh the log\n\ncompare the lint output\n\nsettle on the fix',
    reasoning_spans: [
      { seconds: 3, before_tool: 0, text: 'weigh the log' },
      { seconds: 2, before_tool: 1, text: 'compare the lint output' },
      { seconds: 1, before_tool: 2, text: 'settle on the fix' },
    ],
    tools: [
      { name: 'read', tool_id: 't1', reasoning: 'Let me look at the log.', at: 103 },
      { name: 'lint', tool_id: 't2', at: 106 },
    ],
    ...overrides,
  };
}

const replay = (turn) => processSteps(turn, { tools: turn.tools, reasoning: turn.reasoning, hasReasoning: true })
  .map((s) => (s.kind === 'tools' ? s.key : `${s.key}:${s.seconds ?? '-'}:${s.text}`));

describe('processSteps on a daemon-shaped stored turn', () => {
  it('reasoning → tool → answer: the span text, then the prose alpi wrote before the call', () => {
    const turn = storedDaemonTurn({
      reasoning: 'weigh the log',
      reasoning_spans: [{ seconds: 3, before_tool: 0, text: 'weigh the log' }],
      tools: [{ name: 'read', tool_id: 't1', reasoning: 'Let me look at the log.' }],
    });
    expect(replay(turn)).toEqual(['r0:3:weigh the log\n\nLet me look at the log.', 't:t1']);
  });

  it('reasoning → tool → reasoning → tool: each row keeps its own text and seconds', () => {
    expect(replay(storedDaemonTurn())).toEqual([
      'r0:3:weigh the log\n\nLet me look at the log.',
      't:t1',
      'r1:2:compare the lint output',
      't:t2',
      'r2:1:settle on the fix',
    ]);
  });

  it('keeps a preamble-only step and never repeats prose the span already carries', () => {
    const turn = storedDaemonTurn({
      reasoning_spans: [{ seconds: 3, before_tool: 0, text: 'weigh it. Let me look at the log.' }],
      tools: [
        { name: 'read', tool_id: 't1', reasoning: 'Let me look at the log.' },
        { name: 'lint', tool_id: 't2', reasoning: 'Now the linter.' },
      ],
    });
    expect(replay(turn)).toEqual([
      'r0:3:weigh it. Let me look at the log.',
      't:t1',
      'r1:-:Now the linter.',
      't:t2',
    ]);
  });

  it('spans without text (older daemon): prose stays in place, the trace lands once, empty spans stay static', () => {
    const spans = storedDaemonTurn().reasoning_spans.map(({ text, ...rest }) => rest);
    const turn = storedDaemonTurn({ reasoning_spans: spans });
    const steps = replay(turn);
    expect(steps).toEqual([
      'r0:3:Let me look at the log.',
      't:t1',
      'r1:2:',
      't:t2',
      'r2:1:weigh the log\n\ncompare the lint output\n\nsettle on the fix',
    ]);
    const all = steps.join('|');
    expect(all.split('Let me look at the log.').length - 1).toBe(1);
  });
});

describe('processSteps drops spans that would render nothing', () => {
  it('skips a sub-second span with no text, so the last visible row stays the last step', () => {
    const turn = {
      reasoning: 'plan',
      reasoning_spans: [{ seconds: 3, before_tool: 0, text: 'plan' }, { seconds: 0.4, before_tool: 1 }],
      tools: [{ name: 'read', tool_id: 't1' }],
    };
    const steps = processSteps(turn, { tools: turn.tools, reasoning: turn.reasoning, hasReasoning: true });
    expect(steps.map((s) => s.key)).toEqual(['r0', 't:t1']);
  });

  it('keeps tools in one run across a dropped span between them', () => {
    const turn = {
      reasoning: 'plan',
      reasoning_spans: [{ seconds: 3, before_tool: 0, text: 'plan' }, { seconds: 0.2, before_tool: 1 }],
      tools: [{ name: 'read', tool_id: 't1' }, { name: 'grep', tool_id: 't2' }],
    };
    const steps = processSteps(turn, { tools: turn.tools, reasoning: turn.reasoning, hasReasoning: true });
    expect(steps.map((s) => (s.kind === 'tools' ? s.tools.map((t) => t.name).join(',') : s.key))).toEqual(['r0', 'read,grep']);
  });
});
