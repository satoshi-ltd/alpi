import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

import { FALLBACK_ACCENT } from '../../../../common/folds.mjs';

afterEach(cleanup);

const h = vi.hoisted(() => ({ profiles: [] }));

vi.mock('react-native', () => {
  const View = ({ children, style }) =>
    React.createElement('div', { 'data-style': JSON.stringify(style ?? {}), ...(style?.borderColor ? { 'data-edge': style.borderColor } : {}) }, children);
  const Text = ({ children }) => React.createElement('span', {}, children);
  const Pressable = ({ children, onPress, style, accessibilityRole, accessibilityLabel }) =>
    React.createElement('button', { type: 'button', onClick: onPress, role: accessibilityRole, 'aria-label': accessibilityLabel, 'data-style': JSON.stringify(typeof style === 'function' ? style({ pressed: false }) : style ?? {}) }, children);
  const ScrollView = ({ children, style }) => React.createElement('div', { 'data-scroll': JSON.stringify(style ?? {}) }, children);
  return { Pressable, ScrollView, Text, View };
});

vi.mock('../../components/Fold', () => ({
  Fold: ({ fold, color }) => React.createElement('span', { 'data-fold': fold ?? '', 'data-color': color }),
}));
vi.mock('../../components/Pill', () => ({ Pill: ({ children }) => React.createElement('span', {}, children) }));
vi.mock('../../hooks/useDaemonData', () => ({ useProfileSummaries: () => ({ data: { profiles: h.profiles } }) }));
vi.mock('../../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { bgElev: '#fff', ink: '#000', ink3: '#666', line: '#eee', selected: '#ddd' },
    fonts: { mono: 'GeistMono_400Regular', sans: { regular: 'Geist_400Regular' } },
    fontSizes: { sm: 12, md: 14 },
    shadow: { float: { borderWidth: 1, borderColor: '#token-edge' } },
  }),
}));

import { PANE_PAD_X } from '../../lib/panes';
import { MentionPopover } from './MentionPopover';

describe('MentionPopover', () => {
  it('floats on the theme edge, not a literal one', () => {
    h.profiles = [];
    const { container } = render(<MentionPopover candidates={[{ id: 'doc' }]} />);
    expect(container.querySelector('[data-edge]').getAttribute('data-edge')).toBe('#token-edge');
  });

  it('insets the card by the pane gutter and gives every row a 44 pt button target', () => {
    h.profiles = [];
    const { container, getAllByRole } = render(<MentionPopover candidates={[{ id: 'doc' }, { id: 'lex' }]} />);
    expect(JSON.parse(container.firstChild.getAttribute('data-style')).marginHorizontal).toBe(PANE_PAD_X);
    const rows = getAllByRole('button');
    expect(rows).toHaveLength(2);
    for (const row of rows) expect(JSON.parse(row.getAttribute('data-style')).minHeight).toBeGreaterThanOrEqual(44);
  });

  it('scrolls past four rows instead of growing', () => {
    h.profiles = [];
    const { container } = render(<MentionPopover candidates={['a', 'b', 'c', 'd', 'e'].map((id) => ({ id }))} />);
    expect(JSON.parse(container.querySelector('[data-scroll]').getAttribute('data-scroll')).maxHeight).toBe(176);
  });

  it('says so when the token matches nobody, and vanishes only without a token', () => {
    h.profiles = [];
    const { container, rerender } = render(<MentionPopover candidates={[]} token="zz" />);
    expect(container.textContent).toBe('No peer matches “zz”');
    rerender(<MentionPopover candidates={[]} token="" />);
    expect(container.firstChild).toBeNull();
  });

  it('paints each candidate with its summary accent', () => {
    h.profiles = [{ name: 'doc', accent: '#3ac9f3', fold: 'house' }];
    const { container } = render(<MentionPopover candidates={[{ id: 'doc' }]} />);
    const fold = container.querySelector('[data-fold]');
    expect(fold.getAttribute('data-color')).toBe('#3ac9f3');
    expect(fold.getAttribute('data-fold')).toBe('house');
  });

  it('falls back to the shared accent for a profile the summaries do not know, whatever its name', () => {
    h.profiles = [];
    const { container } = render(<MentionPopover candidates={[{ id: 'lex' }, { id: 'ghost' }]} />);
    const colors = [...container.querySelectorAll('[data-fold]')].map((n) => n.getAttribute('data-color'));
    expect(colors).toEqual([FALLBACK_ACCENT, FALLBACK_ACCENT]);
  });
});
