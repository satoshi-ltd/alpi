import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({ window: { width: 690, height: 829 } }));

vi.mock('react-native', async () => {
  const R = await import('react');
  const flat = (style) => Object.assign({}, ...[style].flat(Infinity).filter(Boolean));
  return {
    View: ({ children, testID, style }) =>
      R.createElement('div', { 'data-testid': testID, 'data-style': JSON.stringify(flat(style)) }, children),
    useWindowDimensions: () => h.window,
  };
});
vi.mock('expo-router', () => ({ usePathname: () => '/' }));
vi.mock('../../lib/reduceMotion', () => ({ useReduceMotion: () => false }));
vi.mock('../../lib/sidebarPref', () => ({ loadSidebarPref: async () => null, saveSidebarPref: () => {} }));
vi.mock('../../theme/ThemeContext', () => ({ useTheme: () => ({ colors: { bg: '#fff' } }) }));
vi.mock('./SidebarPane', async () => {
  const R = await import('react');
  return { SidebarPane: () => R.createElement('div', { 'data-testid': 'sidebar' }) };
});

import { finishTimings, state } from '../../../tests/mocks/reanimated.js';
import { SIDEBAR_W } from '../../lib/panes';
import { usePane } from '../../nav/PaneContext';
import { motionMs } from '../../theme/tokens';
import { PaneShell } from './PaneShell';

function Toggle() {
  const { toggleSidebar } = usePane();
  return <button type="button" onClick={toggleSidebar}>toggle</button>;
}

const space = () => JSON.parse(screen.getByTestId('sidebar-space').getAttribute('data-style')).width;
const shell = () => (
  <PaneShell>
    <Toggle />
  </PaneShell>
);

beforeEach(() => {
  h.window = { width: 690, height: 829 };
  state.hold = true;
  state.pending.length = 0;
  state.timings.length = 0;
});
afterEach(() => {
  state.hold = false;
  state.pending.length = 0;
});

describe('sidebar motion', () => {
  it('snaps the chat pane width once per toggle and only slides the roster layer', () => {
    render(shell());
    expect(space()).toBe(0);
    fireEvent.click(screen.getByText('toggle'));
    expect(state.timings.at(-1)).toEqual({ to: 1, duration: motionMs.sidebar });
    expect(space()).toBe(SIDEBAR_W);
    expect(screen.getByTestId('sidebar')).toBeTruthy();
    act(() => finishTimings());
    fireEvent.click(screen.getByText('toggle'));
    expect(state.timings.at(-1)).toEqual({ to: 0, duration: motionMs.sidebar });
    expect(space()).toBe(SIDEBAR_W);
    expect(screen.getByTestId('sidebar')).toBeTruthy();
    const layer = JSON.parse(screen.getByTestId('sidebar-layer').getAttribute('data-style'));
    expect(layer.position).toBe('absolute');
    expect(layer.width).toBe(SIDEBAR_W);
    act(() => finishTimings());
    expect(space()).toBe(0);
    expect(screen.queryByTestId('sidebar')).toBeNull();
  });

  it('snaps without animating when folding drops the second pane', () => {
    h.window = { width: 1194, height: 834 };
    const { rerender } = render(shell());
    expect(screen.getByTestId('sidebar')).toBeTruthy();
    h.window = { width: 344, height: 882 };
    rerender(shell());
    expect(state.timings).toEqual([]);
    expect(screen.queryByTestId('sidebar')).toBeNull();
    expect(space()).toBe(0);
  });
});
