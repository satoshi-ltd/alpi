import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => ({
  View: ({ children, accessibilityLabel }) => React.createElement('div', { 'aria-label': accessibilityLabel }, children),
  Text: ({ children }) => React.createElement('span', {}, children),
}));
vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({ colors: { danger: '#f00', onDanger: '#fff', ink3: '#666' }, fonts: { monoMedium: 'm', sans: { regular: 'r' } }, fontSizes: { xs: 11, md: 14 } }),
}));

import { AttentionPill, AttentionValue } from './AttentionPill';

describe('AttentionPill', () => {
  it('renders the count with its accessible label and nothing at zero', () => {
    const { container, rerender } = render(<AttentionPill count={2} label="2 files need you" />);
    expect(container.querySelector('[aria-label="2 files need you"]').textContent).toBe('2');
    rerender(<AttentionPill count={0} label="" />);
    expect(container.textContent).toBe('');
  });

  it('puts the pill before the value, and leaves the value alone when healthy', () => {
    const { container, rerender } = render(<AttentionValue count={1} label="1 skill needs you">5</AttentionValue>);
    expect(container.textContent).toBe('15');
    rerender(<AttentionValue count={0} label="">5</AttentionValue>);
    expect(container.textContent).toBe('5');
  });
});
