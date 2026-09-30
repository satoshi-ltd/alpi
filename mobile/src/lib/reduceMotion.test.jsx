import React from 'react';
import { act, cleanup, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const h = vi.hoisted(() => ({ enabled: false, listener: null, reads: 0, subscriptions: 0 }));

vi.mock('react-native', () => ({
  AccessibilityInfo: {
    isReduceMotionEnabled: async () => { h.reads += 1; return h.enabled; },
    addEventListener: (_name, fn) => {
      h.subscriptions += 1;
      h.listener = fn;
      return { remove: () => {} };
    },
  },
}));

import { _resetReduceMotionForTests, useReduceMotion } from './reduceMotion';

beforeEach(() => {
  _resetReduceMotionForTests();
  Object.assign(h, { enabled: false, listener: null, reads: 0, subscriptions: 0 });
});
afterEach(cleanup);

function Probe({ id }) {
  return React.createElement('span', { 'data-testid': id }, String(useReduceMotion()));
}

describe('useReduceMotion', () => {
  it('reads the OS setting and follows changes', async () => {
    h.enabled = true;
    const { getByTestId } = render(React.createElement(Probe, { id: 'a' }));
    await act(async () => {});
    expect(getByTestId('a').textContent).toBe('true');
    act(() => h.listener(false));
    expect(getByTestId('a').textContent).toBe('false');
  });

  it('asks the OS once and listens once however many components read it', async () => {
    const many = Array.from({ length: 40 }, (_, i) => React.createElement(Probe, { key: i, id: `p${i}` }));
    const { getByTestId } = render(React.createElement(React.Fragment, null, many));
    await act(async () => {});
    expect(h.reads).toBe(1);
    expect(h.subscriptions).toBe(1);
    act(() => h.listener(true));
    expect(getByTestId('p0').textContent).toBe('true');
    expect(getByTestId('p39').textContent).toBe('true');
  });
});
