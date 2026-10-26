import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render } from '@testing-library/react';

const h = vi.hoisted(() => ({ state: null }));

vi.mock('react-native', () => {
  const View = ({ children }) => React.createElement('div', {}, children);
  const Text = ({ children }) => React.createElement('span', {}, children);
  const Pressable = ({ children }) => React.createElement('button', { type: 'button' }, typeof children === 'function' ? children({ pressed: false }) : children);
  return { View, Text, Pressable, ScrollView: ({ children }) => React.createElement('div', {}, children), RefreshControl: () => null };
});
vi.mock('../../components/FadeIn', () => ({ FadeIn: ({ children, animate = true }) => React.createElement('div', { 'data-fade': String(animate) }, children) }));
vi.mock('../../components/ListSkeleton', () => ({ ListSkeleton: () => React.createElement('div', { 'data-bones': '' }) }));
vi.mock('../../components/Dot', () => ({ Dot: () => null }));
vi.mock('../../components/LoadFailed', () => ({ LoadFailed: ({ error }) => React.createElement('div', { role: 'alert' }, String(error)) }));
vi.mock('../../components/Row', () => ({
  Row: ({ label }) => React.createElement('div', {}, label),
  RowGroup: ({ children }) => React.createElement('div', {}, children),
  RowSeparator: () => null,
  SectionHeader: ({ children }) => React.createElement('h3', {}, children),
}));
vi.mock('../../hooks/useAttention', () => ({ useAttention: () => ({ att: null, refresh: () => {} }) }));
vi.mock('../../hooks/useDaemonData', () => ({ useSkills: () => h.state }));
vi.mock('../../hooks/usePullRefresh', () => ({ usePullRefresh: () => ({ refreshing: false, onRefresh: vi.fn() }) }));
vi.mock('../../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { ink: '#000', ink3: '#666', danger: '#c00', dangerText: '#a00', selected: '#eee' },
    fonts: { sans: { regular: 'r', semibold: 's' }, mono: 'm' },
    fontSizes: { xs: 11, sm: 12, lg: 15 },
  }),
}));

import { SkillsList } from './SkillsList';

const loaded = { data: { skills: [{ name: 'writer', category: 'docs', path: 'docs/writer' }] }, loading: false, error: null, refresh: vi.fn() };
const loading = { data: null, loading: true, error: null, refresh: vi.fn() };
const failed = { data: null, loading: false, error: 'offline', refresh: vi.fn() };

const tick = (ms) => act(() => { vi.advanceTimersByTime(ms); });
const bones = (c) => c.querySelector('[data-bones]') != null;
const fade = (c) => c.querySelector('[data-fade]')?.dataset.fade ?? null;

beforeEach(() => {
  vi.useFakeTimers();
  h.state = loading;
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe('skills list with the real skeleton hook', () => {
  const mount = () => {
    const view = render(<SkillsList profile="doc" onOpen={vi.fn()} />);
    return { ...view, again: () => view.rerender(<SkillsList profile="doc" onOpen={vi.fn()} />) };
  };

  it('draws nothing before 150 ms, holds the bones to 400 ms, then fades the list in', () => {
    const { container, again } = mount();
    tick(149);
    expect(bones(container)).toBe(false);
    expect(container.textContent).toBe('');
    tick(1);
    expect(bones(container)).toBe(true);
    h.state = loaded;
    again();
    tick(399);
    expect(bones(container)).toBe(true);
    tick(1);
    expect(bones(container)).toBe(false);
    expect(container.textContent).toContain('writer');
    expect(fade(container)).toBe('true');
  });

  it('shows the list without a fade when the load ends inside the delay', () => {
    const { container, again } = mount();
    tick(100);
    h.state = loaded;
    again();
    tick(1000);
    expect(bones(container)).toBe(false);
    expect(container.textContent).toContain('writer');
    expect(fade(container)).toBe('false');
  });

  it('still surfaces a failed load after the hand-over', () => {
    const { container, again } = mount();
    tick(150);
    h.state = failed;
    again();
    tick(400);
    expect(bones(container)).toBe(false);
    expect(container.querySelector('[role="alert"]').textContent).toBe('offline');
  });

  it('does not fade a list that was already cached at mount', () => {
    h.state = loaded;
    const { container } = mount();
    expect(fade(container)).toBe('false');
  });
});
