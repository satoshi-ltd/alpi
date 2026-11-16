import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => ({
  View: ({ children, style, testID }) =>
    React.createElement('div', { 'data-testid': testID, 'data-pad': style?.paddingHorizontal, 'data-gap': style?.gap }, children),
  Text: ({ children }) => React.createElement('span', {}, children),
  Pressable: ({ children, onPress, accessibilityLabel, accessibilityState, accessibilityLiveRegion, testID }) =>
    React.createElement('button', { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel, 'aria-expanded': String(!!accessibilityState?.expanded), 'aria-live': accessibilityLiveRegion, 'data-testid': testID }, children),
}));
vi.mock('../../components/Expand', () => ({ Expand: ({ open, children }) => React.createElement('div', { 'data-open': String(!!open) }, children) }));
vi.mock('../../components/Icon', () => ({ Icon: () => null }));
vi.mock('../../components/Fold', () => ({ Fold: ({ shape, size, state }) => React.createElement('i', { 'data-mark': shape ?? '', 'data-size': size, 'data-state': state }) }));
vi.mock('../../theme/ThemeContext', async () => {
  const tokens = await import('../../theme/tokens');
  return { useTheme: () => ({ colors: { ink: '#000', ink2: '#333', ink3: '#666', danger: '#f00', dangerText: '#c00' }, fonts: tokens.fonts, fontSizes: tokens.fontSizes }) };
});

vi.mock('./Reasoning', () => ({
  Reasoning: ({ streaming, seconds, timeline, shape, accent }) =>
    React.createElement('section', {
      'data-step': 'reasoning',
      'data-shape': shape ?? '',
      'data-accent': accent ?? '',
      'data-streaming': String(!!streaming),
      'data-seconds': seconds,
      'data-timeline': timeline?.length ?? 0,
    }),
}));

vi.mock('./ToolCallRow', () => ({
  ToolModule: ({ tools }) => React.createElement('section', { 'data-step': 'tools', 'data-names': tools.map((t) => t.name).join(',') }),
}));

import { PANE_PAD_X } from '../../lib/panes';
import { PROCESS_GAP, PROCESS_ROW_H, TURN_GAP } from './processRow';
import { ProcessBlock, WORK_LINE_H, WORK_MARK } from './ProcessBlock';
import { MARK_SIZES } from '../../../../common/agentMarks.mjs';

const steps = () => [...document.querySelectorAll('[data-step]')].map((n) => n.getAttribute('data-step'));

function renderTurn(turn, extra = {}) {
  const tools = (turn.tools ?? []).filter((t) => t.name !== 'ask_user');
  return render(
    <ProcessBlock
      turn={turn}
      tools={tools}
      reasoning={turn.reasoning ?? ''}
      seconds={turn.reasoned_s}
      showReasoning={!!turn.reasoning}
      {...extra}
    />,
  );
}

describe('ProcessBlock', () => {
  it('stacks every step in one block on the chat gutter with a tight rhythm', () => {
    renderTurn({ tools: [{ name: 'read', reasoning: 'plan', at: 1 }], reasoning: 'plan', reasoned_s: 3 });
    const block = document.querySelector('[data-testid="process-block"]');
    expect(Number(block.getAttribute('data-pad'))).toBe(PANE_PAD_X);
    expect(Number(block.getAttribute('data-gap'))).toBe(PROCESS_GAP);
    expect(PROCESS_GAP).toBeGreaterThanOrEqual(2);
    expect(PROCESS_GAP).toBeLessThanOrEqual(4);
    expect(block.querySelectorAll('[data-step]').length).toBe(2);
  });

  it('leads with one work line: the profile mark at the row size, how long it worked and how many steps', () => {
    renderTurn({ tools: [{ name: 'read', reasoning: 'plan', at: 1, ok: true, duration_s: 1 }, { name: 'grep', at: 2, ok: false, duration_s: 1 }], reasoning: 'plan', reasoned_s: 3 }, { shape: 'bell' });
    const line = document.querySelector('[data-testid="work-line"]');
    expect(line.getAttribute('aria-label')).toBe('Worked for 5s · 3 steps · 1 failed');
    expect(line.getAttribute('aria-expanded')).toBe('false');
    expect(document.querySelector('[data-open]').getAttribute('data-open')).toBe('false');
    const mark = line.querySelector('[data-mark]');
    expect(mark.getAttribute('data-mark')).toBe('bell');
    expect(Number(mark.getAttribute('data-size'))).toBe(MARK_SIZES.row);
    expect(WORK_MARK).toBe(MARK_SIZES.row);
    expect(WORK_LINE_H).toBe(36);
    fireEvent.click(line);
    expect(document.querySelector('[data-open]').getAttribute('data-open')).toBe('true');
  });

  it('stays Working between rounds while the turn runs, and announces the step politely', () => {
    renderTurn({ req: 'm-1', pending: true, tools: [{ name: 'read_file', at: 1, ok: true, reasoning: 'plan' }], reasoning: 'plan' }, { running: true });
    const line = document.querySelector('[data-testid="work-line"]');
    expect(line.getAttribute('aria-label')).toBe('Working · Thinking');
    expect(line.getAttribute('aria-live')).toBe('polite');
    cleanup();
    renderTurn({ tools: [{ name: 'grep', at: 10, ok: true, duration_s: 5 }, { name: 'read_file', at: 11, ok: true, duration_s: 5 }, { name: 'lint', at: 30, ok: true, duration_s: 2 }] });
    expect(document.querySelector('[data-testid="work-line"]').getAttribute('aria-label')).toBe('Worked for 22s · 3 steps');
  });

  it('says Writing while answer text streams before the next step, and stays Working', () => {
    renderTurn({ req: 'm-1', pending: true, assistant: 'Let me check', tools: [{ name: 'grep', at: 1, ok: true }] }, { running: true, answered: true });
    expect(document.querySelector('[data-testid="work-line"]').getAttribute('aria-label')).toBe('Working · Writing');
  });

  it('names the running step while it works and says Thinking while it thinks', () => {
    renderTurn({ req: 'm-1', pending: true, tools: [{ name: 'web_fetch', args: { url: 'status.example.com' }, at: 1 }] });
    expect(document.querySelector('[data-testid="work-line"]').getAttribute('aria-label')).toBe('Working · Fetching status.example.com');
    expect(document.querySelector('[data-testid="work-line"] [data-mark]').getAttribute('data-state')).toBe('working');
    cleanup();
    renderTurn({ req: 'm-1', pending: true, tools: [] }, { showReasoning: true, reasoningLive: true });
    expect(document.querySelector('[data-testid="work-line"]').getAttribute('aria-label')).toBe('Working · Thinking');
  });

  it('sits about 12 pt off the answer with 20 pt rows, so it reads as a block and not as the reply', () => {
    expect(TURN_GAP).toBe(12);
    expect(PROCESS_ROW_H).toBe(20);
  });

  it('shows the thought first when it came first', () => {
    renderTurn({ tools: [{ name: 'read', reasoning: 'plan', at: 1 }], reasoning: 'plan', reasoned_s: 3 });
    expect(steps()).toEqual(['reasoning', 'tools']);
  });

  it('shows the tools first when the thinking only followed them', () => {
    renderTurn({ req: 'm-1', pending: true, tools: [{ name: 'read', at: 1, ok: true }], reasoning: 'summing up' }, { reasoningLive: true });
    expect(steps()).toEqual(['tools', 'reasoning']);
    expect(document.querySelector('[data-step="reasoning"]').getAttribute('data-streaming')).toBe('true');
  });

  it('hands the tools over in the order they started', () => {
    renderTurn({ tools: [{ name: 'late', at: 9 }, { name: 'early', at: 2 }] });
    expect(document.querySelector('[data-step="tools"]').getAttribute('data-names')).toBe('early,late');
  });

  it('keeps a pending turn with nothing yet as a lone Thinking row', () => {
    renderTurn({ req: 'm-1', pending: true, tools: [] }, { showReasoning: true, reasoningLive: true });
    expect(steps()).toEqual(['reasoning']);
  });

  it('renders nothing for a turn with no process', () => {
    const { container } = renderTurn({ tools: [] });
    expect(container.textContent).toBe('');
    expect(document.querySelector('[data-testid="process-block"]')).toBeNull();
  });

  it('renders one thought row per stored span, in place', () => {
    renderTurn({
      reasoning: 'plan\n\ncheck',
      reasoning_spans: [{ seconds: 3, before_tool: 0 }, { seconds: 2, before_tool: 1 }],
      tools: [{ name: 'read', reasoning: 'plan' }, { name: 'grep', reasoning: 'check' }],
    });
    expect(steps()).toEqual(['reasoning', 'tools', 'reasoning', 'tools']);
    expect([...document.querySelectorAll('[data-step="reasoning"]')].map((n) => n.getAttribute('data-seconds'))).toEqual(['3', '2']);
  });
});

describe('ProcessBlock hands the profile to its reasoning', () => {
  it('passes the profile fold and colour to the thinking row', () => {
    renderTurn({ reasoning: 'plan', reasoned_s: 3 }, { shape: 'bell', accent: '#3899e2' });
    const reasoning = document.querySelector('[data-step="reasoning"]');
    expect(reasoning.getAttribute('data-shape')).toBe('bell');
    expect(reasoning.getAttribute('data-accent')).toBe('#3899e2');
  });
});
