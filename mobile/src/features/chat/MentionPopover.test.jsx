import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

import { FALLBACK_ACCENT } from '../../../../common/folds.mjs';

afterEach(cleanup);

const h = vi.hoisted(() => ({ profiles: [] }));

vi.mock('react-native', () => {
  const View = ({ children, style }) =>
    React.createElement('div', style?.shadowColor ? { 'data-shadow': style.shadowColor } : {}, children);
  const Text = ({ children }) => React.createElement('span', {}, children);
  const Pressable = ({ children, onPress }) => React.createElement('button', { type: 'button', onClick: onPress }, children);
  return { Pressable, Text, View };
});

vi.mock('../../components/Fold', () => ({
  Fold: ({ fold, color }) => React.createElement('span', { 'data-fold': fold ?? '', 'data-color': color }),
}));
vi.mock('../../components/Pill', () => ({ Pill: ({ children }) => React.createElement('span', {}, children) }));
vi.mock('../../hooks/useDaemonData', () => ({ useProfileSummaries: () => ({ data: { profiles: h.profiles } }) }));
vi.mock('../../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { bgElev: '#fff', ink: '#000', ink3: '#666', line: '#eee', selected: '#ddd' },
    fonts: { mono: 'GeistMono_400Regular' },
    fontSizes: { sm: 12, md: 14 },
    shadow: { base: { shadowColor: '#token-shadow', shadowRadius: 24 } },
  }),
}));

import { MentionPopover } from './MentionPopover';

describe('MentionPopover', () => {
  it('casts the theme shadow, not a literal one', () => {
    h.profiles = [];
    const { container } = render(<MentionPopover candidates={[{ id: 'doc' }]} />);
    expect(container.querySelector('[data-shadow]').getAttribute('data-shadow')).toBe('#token-shadow');
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
