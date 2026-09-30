import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => {
  const View = ({ children, style, testID }) =>
    React.createElement('div', {
      'data-testid': testID,
      'data-pad-v': style?.paddingVertical,
      'data-margin-v': style?.marginVertical,
      'data-gap': style?.gap,
    }, children);
  const Text = ({ children }) => React.createElement('span', {}, children);
  const Pressable = ({ children, onPress, accessibilityLabel, style, hitSlop }) => {
    const resolved = typeof style === 'function' ? style({ pressed: false }) : style;
    return React.createElement('button', {
      type: 'button',
      onClick: onPress,
      'aria-label': accessibilityLabel,
      'data-row': 'true',
      'data-min-h': resolved?.minHeight,
      'data-slop-top': hitSlop?.top ?? 0,
      'data-slop-bottom': hitSlop?.bottom ?? 0,
    }, children);
  };
  const Animated = {
    View,
    Value: class { constructor(v) { this.v = v; } },
    timing: () => ({ start() {}, stop() {} }),
    loop: () => ({ start() {}, stop() {} }),
    sequence: () => ({ start() {}, stop() {} }),
  };
  const ScrollView = ({ children }) => React.createElement('div', { 'data-scroll': 'true' }, children);
  return { View, Text, Pressable, Animated, ScrollView, useWindowDimensions: () => ({ height: 800 }) };
});

vi.mock('react-native-reanimated', async () => import('../../../tests/mocks/reanimated.js'));
vi.mock('../../lib/reduceMotion', () => ({ useReduceMotion: () => true }));
vi.mock('../../theme/ThemeContext', async () => {
  const tokens = await import('../../theme/tokens');
  return {
    useTheme: () => ({
      colors: { ink: '#000', ink2: '#333', ink3: '#666', ink4: '#999', line: '#eee', danger: '#f00', dangerText: '#c00' },
      fonts: tokens.fonts,
      fontSizes: tokens.fontSizes,
    }),
  };
});
vi.mock('../../components/Icon', () => ({ Icon: () => null }));
vi.mock('./ToolDetailSheet', () => ({
  ToolDetailSheet: ({ tool }) => (tool ? React.createElement('div', { 'data-sheet': tool.name }) : null),
}));

import { mobile } from '../../theme/tokens';
import { PROCESS_EDGE, PROCESS_GAP, PROCESS_ROW_H } from './processRow';
import { ProcessBlock } from './ProcessBlock';

function targets() {
  const rows = [...document.querySelectorAll('[data-row]')];
  return rows.map((row, k) => {
    const y = k * (PROCESS_ROW_H + PROCESS_GAP);
    expect(Number(row.getAttribute('data-min-h'))).toBe(PROCESS_ROW_H);
    return {
      top: y - Number(row.getAttribute('data-slop-top')),
      bottom: y + PROCESS_ROW_H + Number(row.getAttribute('data-slop-bottom')),
      visualBottom: y + PROCESS_ROW_H,
    };
  });
}

const failingTurn = {
  reasoning: 'plan\n\nwrap up',
  reasoning_spans: [{ seconds: 3, before_tool: 0 }, { seconds: 1, before_tool: 3 }],
  tools: [
    { name: 'read', tool_id: 't1', reasoning: 'plan', ok: true },
    { name: 'grep', tool_id: 't2', ok: false, result: 'boom' },
    { name: 'lint', tool_id: 't3', ok: true },
  ],
};

function renderBlock(turn, extra = {}) {
  return render(
    <ProcessBlock
      turn={turn}
      tools={turn.tools}
      reasoning={turn.reasoning}
      seconds={turn.reasoned_s}
      showReasoning={!!turn.reasoning || !!extra.reasoningLive}
      {...extra}
    />,
  );
}

describe('process block touch targets', () => {
  it('gives every row its own target: neighbours touch, never overlap, and the outer slop stays inside the block', () => {
    renderBlock(failingTurn);
    const rects = targets();
    expect(rects.length).toBe(6);
    for (let k = 1; k < rects.length; k += 1) {
      expect(rects[k].top).toBe(rects[k - 1].bottom);
    }
    const block = document.querySelector('[data-testid="process-block"]');
    const pad = Number(block.getAttribute('data-pad-v'));
    expect(Number(block.getAttribute('data-margin-v'))).toBe(-pad);
    expect(rects[0].top).toBeGreaterThanOrEqual(-pad);
    expect(rects[rects.length - 1].bottom).toBeLessThanOrEqual(rects[rects.length - 1].visualBottom + pad);
    expect(rects[0].bottom - rects[0].top).toBe(PROCESS_ROW_H + PROCESS_EDGE + PROCESS_GAP / 2);
    expect(PROCESS_ROW_H + 2 * PROCESS_EDGE).toBe(mobile.tap);
  });

  it('gives the last visible row the outer edge even when a trailing sub-second span has no text', () => {
    renderBlock({
      reasoning: 'plan',
      reasoning_spans: [{ seconds: 3, before_tool: 0, text: 'plan' }, { seconds: 0.4, before_tool: 1 }],
      tools: [{ name: 'read', tool_id: 't1', ok: true }],
    });
    const rows = [...document.querySelectorAll('[data-row]')];
    expect(Number(rows[rows.length - 1].getAttribute('data-slop-bottom'))).toBe(PROCESS_EDGE);
  });

  it('keeps a lone row at the full 44 pt target', () => {
    renderBlock({ tools: [{ name: 'read', tool_id: 't1', ok: true }] });
    const [only] = targets();
    expect(only.bottom - only.top).toBe(mobile.tap);
  });
});

describe('process block state across the first reasoning_done', () => {
  it('keeps an expanded bucket and an open tool sheet when spans start arriving', () => {
    const tools = [
      { name: 'read', tool_id: 't1', reasoning: 'plan', ok: true },
      { name: 'grep', tool_id: 't2', ok: true },
    ];
    const live = { req: 'm-1', pending: true, reasoning: '', tools };
    const { rerender } = render(<ProcessBlock turn={live} tools={tools} reasoning="plan" showReasoning />);
    expect(screen.getByText('Thought')).toBeTruthy();
    fireEvent.click(screen.getByText('2 tool calls').closest('button'));
    fireEvent.click(screen.getByLabelText('grep. Show details'));
    expect(document.querySelector('[data-sheet="grep"]')).toBeTruthy();
    const withSpans = { ...live, reasoning_spans: [{ seconds: 2, before_tool: 0 }] };
    rerender(
      <ProcessBlock turn={withSpans} tools={tools} reasoning="plan" showReasoning />,
    );
    expect(screen.getByText('Thought for 2s')).toBeTruthy();
    expect(screen.getByText('Hide tool calls')).toBeTruthy();
    expect(document.querySelector('[data-sheet="grep"]')).toBeTruthy();
  });
});
