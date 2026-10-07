import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

vi.mock('react-native', () => ({
  View: ({ children, style, accessibilityLabel, accessibilityRole, accessible, ...p }) =>
    React.createElement('div', { ...p, role: accessibilityRole, 'aria-label': accessibilityLabel, 'data-accessible': accessible ? 'true' : 'false' }, children),
}));
vi.mock('../../components/SkeletonBar', () => ({ SkeletonBar: () => React.createElement('i', { 'data-bar': '' }) }));
vi.mock('../../theme/ThemeContext', () => ({ useTheme: () => ({ colors: { hover: '#eee', line: '#ddd' } }) }));

const { InboxSkeleton } = await import('./InboxSkeleton');

afterEach(cleanup);

describe('InboxSkeleton', () => {
  it('announces what it waits for when it is given a label', () => {
    render(<InboxSkeleton rows={2} label="Loading the hub’s peers" />);
    expect(screen.getByRole('progressbar', { name: 'Loading the hub’s peers' }).dataset.accessible).toBe('true');
  });

  it('stays a plain group without a label', () => {
    const { container } = render(<InboxSkeleton rows={2} />);
    expect(container.querySelector('[role="progressbar"]')).toBeNull();
    expect(container.firstChild.dataset.accessible).toBe('false');
  });
});
