import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

afterEach(cleanup);

const flat = (style) => {
  const resolved = typeof style === 'function' ? style({ pressed: false }) : style;
  return [resolved].flat(Infinity).filter(Boolean).reduce((acc, s) => ({ ...acc, ...s }), {});
};

vi.mock('react-native', () => ({
  View: ({ children, style, accessibilityLabel, ...p }) =>
    React.createElement(
      'div',
      { ...p, 'data-style': JSON.stringify(flat(style)), ...(accessibilityLabel ? { 'aria-label': accessibilityLabel } : {}) },
      children,
    ),
  Text: ({ children, style, numberOfLines, ...p }) =>
    React.createElement('span', { ...p, 'data-style': JSON.stringify(flat(style)) }, children),
  Pressable: ({ children, onPress, onLongPress, style, accessibilityLabel, android_ripple, ...p }) =>
    React.createElement(
      'button',
      { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel, 'data-style': JSON.stringify(flat(style)), 'data-testid': 'row', ...p },
      children instanceof Function ? children({ pressed: false }) : children,
    ),
  StyleSheet: { create: (s) => s },
  Platform: { OS: 'ios', select: (s) => s?.ios ?? s?.default },
}));

vi.mock('../src/components/Glyph', () => ({ Glyph: () => React.createElement('span', { 'data-glyph': 'true' }) }));
vi.mock('../src/features/inbox/Pip', () => ({ Pip: () => React.createElement('span', { 'data-pip': 'true' }) }));
vi.mock('../src/theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { bg: '#fff', selected: '#eee', hover: '#f4f4f4', ink: '#000', ink2: '#333', ink3: '#666' },
    fonts: { sans: { regular: 'r', medium: 'm', semibold: 's', bold: 'b' }, mono: 'mono', monoMedium: 'mm', monoSemibold: 'ms' },
    fontSizes: { xs: 11, md: 14, lg: 15 },
    alpha: { muted: 0.55 },
  }),
}));

import { InboxRow } from '../src/features/inbox/InboxRow';
import { PaneContext } from '../src/nav/PaneContext';
import { space } from '../src/theme/tokens';

const READY_EMPTY = {
  kind: 'profile', id: 'doc', name: 'doc', label: 'doc',
  preview: 'tap to start a thread', ts: null, unread: false, needsProvider: false, paused: false,
};

function renderRow(item, { twoPane = false, showState = false } = {}) {
  const node = <InboxRow item={item} showState={showState} />;
  return render(
    twoPane ? <PaneContext.Provider value={{ twoPane: true, side: 'list' }}>{node}</PaneContext.Provider> : node,
  );
}

const row = () => screen.getByTestId('row');
const styleOf = (el) => JSON.parse(el.getAttribute('data-style') ?? '{}');
const metaColumns = (container) =>
  [...container.querySelectorAll('div')].filter((el) => styleOf(el).alignItems === 'flex-end');

describe('row with copy but no timestamp', () => {
  it('renders the invitation and drops the meta column', () => {
    const { container } = renderRow(READY_EMPTY);
    expect(screen.getByText('tap to start a thread')).toBeTruthy();
    expect(metaColumns(container)).toHaveLength(0);
    expect(row().children).toHaveLength(2);
  });

  it('would have paid a trailing gap for an empty column — the row gap is real', () => {
    renderRow(READY_EMPTY);
    expect(styleOf(row()).gap).toBe(space.s5);
  });

  it('keeps the meta column when a timestamp exists', () => {
    const { container } = renderRow({ ...READY_EMPTY, preview: 'shipped it', ts: '3m' });
    expect(metaColumns(container)).toHaveLength(1);
    expect(row().children).toHaveLength(3);
  });

  it('keeps the meta column for a working workgroup with no timestamp', () => {
    const { container } = renderRow(
      { kind: 'workgroup', id: 'w', label: 'alpha', preview: 'tap to open a #task', ts: null, state: 'working' },
      { showState: true },
    );
    expect(metaColumns(container)).toHaveLength(1);
    expect(container.querySelector('[data-pip]')).toBeTruthy();
    expect(screen.getByLabelText('alpha working')).toBeTruthy();
  });

  it('drops the pip column when the parent does not ask for state', () => {
    const { container } = renderRow(
      { kind: 'workgroup', id: 'w', label: 'alpha', preview: 'tap to open a #task', ts: null, state: 'working' },
      { showState: false },
    );
    expect(metaColumns(container)).toHaveLength(0);
    expect(row().children).toHaveLength(2);
  });

  it('renders the invitation in the plain sans face, not the blocked mono italic', () => {
    renderRow(READY_EMPTY);
    const preview = styleOf(screen.getByText('tap to start a thread'));
    expect(preview.fontFamily).toBe('r');
    expect(preview.fontStyle).toBe('normal');
  });

  it('mutes a paused row but still shows its copy', () => {
    renderRow({ ...READY_EMPTY, paused: true, preview: 'paused · resume to chat' });
    expect(styleOf(row()).opacity).toBe(0.55);
    expect(screen.getByText('paused · resume to chat')).toBeTruthy();
  });

  it('shows no preview at all in the compact sidebar row', () => {
    const { container } = renderRow(READY_EMPTY, { twoPane: true });
    expect(screen.queryByText('tap to start a thread')).toBeNull();
    expect(metaColumns(container)).toHaveLength(0);
    expect(row().children).toHaveLength(2);
  });
});
