import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render } from '@testing-library/react';

const h = vi.hoisted(() => ({
  push: vi.fn(),
  refresh: vi.fn(),
  state: { data: null, loading: true, error: null },
  activity: { running: [] },
}));

vi.mock('react-native', () => {
  const View = ({ children }) => React.createElement('div', {}, children);
  const Text = ({ children }) => React.createElement('span', {}, children);
  const Pressable = ({ children, onPress, accessibilityLabel, style }) =>
    React.createElement('button', { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel, 'data-bg': (typeof style === 'function' ? style({ pressed: false }) : style)?.backgroundColor }, typeof children === 'function' ? children({ pressed: false }) : children);
  return { View, Text, Pressable, ScrollView: ({ children }) => React.createElement('div', {}, children), RefreshControl: () => null };
});
vi.mock('expo-router', () => ({ useRouter: () => ({ push: h.push }) }));
vi.mock('../../components/FadeIn', () => ({ FadeIn: ({ children, animate = true }) => React.createElement('div', { 'data-fade': String(animate) }, children) }));
vi.mock('../../components/Button', () => ({ Button: ({ title, onPress }) => React.createElement('button', { type: 'button', onClick: onPress }, title) }));
vi.mock('../../components/Dot', () => ({ Dot: ({ color, pulse }) => React.createElement('i', { 'data-dot': color, 'data-pulse': String(!!pulse) }) }));
vi.mock('../../components/Field', () => ({
  Field: ({ value, onChangeText, placeholder }) => React.createElement('input', { value, placeholder, 'aria-label': 'search', onChange: (e) => onChangeText(e.target.value) }),
}));
vi.mock('../../components/EmptyState', () => ({ EmptyState: ({ title, detail, action }) => React.createElement('div', {}, `${title}|${detail}`, React.createElement('button', { type: 'button', onClick: action?.onPress }, action?.label)) }));
vi.mock('../../components/ListSkeleton', () => ({ ListSkeleton: () => React.createElement('div', { 'data-bones': '' }) }));
vi.mock('../../components/LoadFailed', () => ({
  LoadFailed: ({ label, error, onRetry }) => React.createElement('div', { role: 'alert' }, `Couldn't load ${label}: ${error}`, React.createElement('button', { type: 'button', onClick: onRetry }, 'Retry')),
}));
vi.mock('../../components/Row', () => ({
  Row: ({ label, helper }) => React.createElement('div', {}, `${label}|${helper}`),
  RowGroup: ({ children }) => React.createElement('div', {}, children),
  RowSeparator: () => null,
  SectionHeader: ({ children }) => React.createElement('h2', {}, children),
}));
vi.mock('../../hooks/useDaemonData', () => ({ useScheduleList: () => ({ ...h.state, refresh: h.refresh }) }));
vi.mock('../../hooks/useEvents', () => ({ useEventEffect: () => {} }));
vi.mock('../../hooks/usePullRefresh', () => ({ usePullRefresh: () => ({ refreshing: false, onRefresh: vi.fn() }) }));
vi.mock('../../hooks/useActivity', async (importOriginal) => ({ ...(await importOriginal()), useActivity: () => ({ activity: h.activity }) }));
vi.mock('../../theme/ThemeContext', async () => {
  const tokens = await import('../../theme/tokens');
  return {
    useTheme: () => ({
      colors: { bg: '#fff', ink: '#000', ink2: '#333', ink3: '#666', ink4: '#999', danger: '#f00', dangerText: '#a00', selected: '#ddd' },
      fonts: { sans: { regular: 'r', semibold: 's' }, mono: 'm' },
      fontSizes: tokens.fontSizes,
    }),
  };
});

import { JobList } from './JobList';

const JOBS = [{ id: 'a', title: 'Weekly listing refresh', kind: 'cron', expression: '0 6 * * 1' }];
const loading = { data: null, loading: true, error: null };
const loaded = { data: { jobs: JOBS }, loading: false, error: null };
const failed = { data: null, loading: false, error: 'offline' };

const tick = (ms) => act(() => { vi.advanceTimersByTime(ms); });
const bones = (c) => c.querySelector('[data-bones]') != null;
const fade = (c) => c.querySelector('[data-fade]')?.dataset.fade ?? null;

beforeEach(() => {
  vi.useFakeTimers();
  h.state = loading;
  h.activity = { running: [] };
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe('job list with the real skeleton hook', () => {
  const mount = () => {
    const view = render(<JobList profile="scout" onOpen={vi.fn()} />);
    return { ...view, again: () => view.rerender(<JobList profile="scout" onOpen={vi.fn()} />) };
  };

  it('draws nothing before 150 ms, holds the bones to 400 ms, then fades the jobs in', () => {
    const { container, again } = mount();
    tick(149);
    expect(bones(container)).toBe(false);
    expect(container.textContent).not.toContain('Weekly listing refresh');
    tick(1);
    expect(bones(container)).toBe(true);
    h.state = loaded;
    again();
    tick(399);
    expect(bones(container)).toBe(true);
    tick(1);
    expect(bones(container)).toBe(false);
    expect(container.textContent).toContain('Weekly listing refresh');
    expect(fade(container)).toBe('true');
  });

  it('shows cached jobs without a fade', () => {
    h.state = loaded;
    const { container } = mount();
    expect(fade(container)).toBe('false');
  });

  it('still surfaces a failed load after the hand-over', () => {
    const { container, again } = mount();
    tick(150);
    h.state = failed;
    again();
    tick(400);
    expect(bones(container)).toBe(false);
    expect(container.querySelector('[role="alert"]').textContent).toContain('offline');
  });
});
