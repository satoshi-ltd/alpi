import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render } from '@testing-library/react';

import { BUSY_DELAY_MS, BUSY_MIN_MS } from '../../../common/busy.mjs';
import { useBusyVisible } from './useBusyVisible';

function Probe({ active }) {
  return <span data-testid="probe">{useBusyVisible(active) ? 'shown' : 'hidden'}</span>;
}

beforeEach(() => { vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'Date'] }); });
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const state = (view) => view.getByTestId('probe').textContent;
const wait = (ms) => act(() => { vi.advanceTimersByTime(ms); });

describe('useBusyVisible', () => {
  it('shows the wait only after 300 ms', () => {
    const view = render(<Probe active />);
    wait(BUSY_DELAY_MS - 1);
    expect(state(view)).toBe('hidden');
    wait(1);
    expect(state(view)).toBe('shown');
  });

  it('never shows a wait that ends inside the delay', () => {
    const view = render(<Probe active />);
    wait(BUSY_DELAY_MS - 50);
    view.rerender(<Probe active={false} />);
    wait(BUSY_DELAY_MS + BUSY_MIN_MS);
    expect(state(view)).toBe('hidden');
  });

  it('keeps a shown wait on screen for at least 400 ms', () => {
    const view = render(<Probe active />);
    wait(BUSY_DELAY_MS);
    view.rerender(<Probe active={false} />);
    wait(BUSY_MIN_MS - 1);
    expect(state(view)).toBe('shown');
    wait(1);
    expect(state(view)).toBe('hidden');
  });

  it('lets a long wait go as soon as it ends once the minimum has passed', () => {
    const view = render(<Probe active />);
    wait(BUSY_DELAY_MS);
    wait(BUSY_MIN_MS + 200);
    view.rerender(<Probe active={false} />);
    expect(state(view)).toBe('hidden');
  });

  it('starts the delay again for the next wait', () => {
    const view = render(<Probe active />);
    wait(BUSY_DELAY_MS);
    wait(BUSY_MIN_MS);
    view.rerender(<Probe active={false} />);
    expect(state(view)).toBe('hidden');
    view.rerender(<Probe active />);
    wait(BUSY_DELAY_MS - 1);
    expect(state(view)).toBe('hidden');
    wait(1);
    expect(state(view)).toBe('shown');
  });

  it('leaves no timer behind when it unmounts', () => {
    const view = render(<Probe active />);
    expect(vi.getTimerCount()).toBe(1);
    view.unmount();
    expect(vi.getTimerCount()).toBe(0);
  });
});
