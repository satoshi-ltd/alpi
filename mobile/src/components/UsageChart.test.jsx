import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => {
  const View = ({ children, style, accessibilityLabel, ...p }) =>
    React.createElement('div', { ...p, ...(accessibilityLabel ? { 'aria-label': accessibilityLabel } : {}) }, children);
  const Text = ({ children, style, numberOfLines, ...p }) => React.createElement('span', p, children);
  const Pressable = ({ children, onPress, style, accessibilityLabel, ...p }) =>
    React.createElement('button', { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel, ...p }, children);
  return { View, Text, Pressable };
});

vi.mock('../theme/ThemeContext', async () => {
  const tokens = await import('../theme/tokens');
  return {
    useTheme: () => ({
      colors: {
        bgPane: '#ffffff', line2: '#ddd', accent: '#8a5a0a',
        ink: '#000', ink2: '#333', ink3: '#666', ink4: '#999',
      },
      fonts: {
        sans: { regular: 'r', medium: 'm', semibold: 's', bold: 'b' },
        mono: 'mono', monoMedium: 'monoMedium', monoSemibold: 'monoSemibold',
      },
      fontSizes: tokens.fontSizes,
    }),
  };
});

import { toUsageDays } from '../../../common/usage.mjs';
import { UsageChart } from './UsageChart';

const DAYS = toUsageDays([
  { iso: '2026-09-27', tokIn: 1000, tokOut: 200, cost: 0.5 },
  { iso: '2026-09-28', tokIn: 3000, tokOut: 500, cost: 1.25 },
]);

describe('UsageChart', () => {
  it('renders nothing without days', () => {
    const { container } = render(<UsageChart days={[]} />);
    expect(container.innerHTML).toBe('');
  });

  it('shows today, the token tiles and the 14-day totals', () => {
    render(<UsageChart days={DAYS} />);
    expect(screen.getByText('$1.25')).toBeTruthy();
    expect(screen.getByText('3K')).toBeTruthy();
    expect(screen.getByText('500')).toBeTruthy();
    expect(screen.getByText('Avg / day')).toBeTruthy();
    expect(screen.getByText('14-day total $1.75 · 4K in / 700 out')).toBeTruthy();
  });

  it('turns the last tile into the daily cap with what is left', () => {
    render(<UsageChart days={DAYS} capLine={5} />);
    expect(screen.getByText('Cap / day')).toBeTruthy();
    expect(screen.getByText('75% left')).toBeTruthy();
  });

  it('prefers the 30-day total when the daemon sends one', () => {
    render(<UsageChart days={DAYS} total30={{ cost: 9, tokIn: 20000, tokOut: 4000 }} />);
    expect(screen.getByText('30-day total $9.00 · 20K in / 4K out')).toBeTruthy();
  });

  it('pins a day on press and releases it on a second press', () => {
    render(<UsageChart days={DAYS} />);
    fireEvent.click(screen.getByLabelText('9/27 usage'));
    expect(screen.getByLabelText('Selected day').textContent).toContain('$0.50');
    expect(screen.getByLabelText('Selected day').textContent).toContain('1K in / 200 out');
    fireEvent.click(screen.getByLabelText('9/27 usage'));
    expect(screen.queryByLabelText('Selected day')).toBeNull();
  });
});
