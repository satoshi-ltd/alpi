import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

import { lineHeights, mobile, space } from '../theme/tokens';

vi.mock('react-native', () => ({
  View: ({ children, style, accessibilityLabel, accessibilityRole, accessible, ...p }) =>
    React.createElement('div', { ...p, role: accessibilityRole, 'aria-label': accessibilityLabel, 'data-style': JSON.stringify(style ?? {}) }, children),
}));
vi.mock('../theme/ThemeContext', () => ({ useTheme: () => ({ fontSizes: { xs: 11, sm: 12, md: 14, lg: 15 } }) }));
vi.mock('./Row', () => ({
  RowGroup: ({ children }) => React.createElement('section', { 'data-card': '' }, children),
  RowSeparator: () => React.createElement('hr'),
}));
vi.mock('./SkeletonBar', () => ({ SkeletonBar: ({ width }) => React.createElement('i', { 'data-bar': width }) }));

const { ListSkeleton } = await import('./ListSkeleton');
const { ReaderSkeleton } = await import('./ReaderSkeleton');

afterEach(cleanup);

describe('ListSkeleton', () => {
  it('draws placeholder rows inside the card the rows will fill, a title and a helper each', () => {
    const { container } = render(<ListSkeleton rows={4} label="Loading skills" />);
    const card = container.querySelector('[data-card]');
    expect(card).not.toBeNull();
    expect(card.querySelectorAll('[data-bar]')).toHaveLength(8);
    expect(card.querySelectorAll('hr')).toHaveLength(3);
    expect(container.querySelector('[role="progressbar"]').getAttribute('aria-label')).toBe('Loading skills');
  });

  it('draws flat rows for a list that has no card', () => {
    const { container } = render(<ListSkeleton flat rows={2} label="Loading outputs" />);
    expect(container.querySelector('[data-card]')).toBeNull();
    expect(container.querySelectorAll('[data-bar]')).toHaveLength(4);
  });

  it('gives each row the height of a real row: the 44 pt target, the row padding and one line per text', () => {
    const { container } = render(<ListSkeleton rows={1} helper="sm" />);
    const row = JSON.parse(container.querySelector('[data-row]').dataset.style);
    expect(row).toMatchObject({ minHeight: mobile.tap, paddingHorizontal: space.s8, paddingVertical: space.s6 });
    const lines = [...container.querySelectorAll('[data-line]')].map((l) => [Number(l.dataset.line), JSON.parse(l.dataset.style).height]);
    expect(lines).toEqual([[15, 15 * lineHeights.cozy], [12, 12 * lineHeights.cozy]]);
  });

  it('leaves out the helper line for lists whose rows have none, and adds a value where the rows carry one', () => {
    const { container } = render(<ListSkeleton rows={1} title="md" helper={false} value />);
    expect([...container.querySelectorAll('[data-line]')].map((l) => l.dataset.line)).toEqual(['14']);
    expect(container.querySelectorAll('[data-bar]')).toHaveLength(2);
  });

  it('shows no word on screen', () => {
    const { container } = render(<ListSkeleton label="Loading skills" />);
    expect(container.textContent).toBe('');
  });
});

describe('ReaderSkeleton', () => {
  it('draws placeholder lines where the text will land, never the word', () => {
    const { container } = render(<ReaderSkeleton label="Loading the file" />);
    expect(container.querySelectorAll('[data-bar]').length).toBeGreaterThan(2);
    expect(container.textContent).toBe('');
  });
});
