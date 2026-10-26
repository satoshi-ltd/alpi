import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => {
  const R = require('react');
  const host = (tag) => ({ children, onPress, accessibilityRole, accessibilityLabel, style, hitSlop, ...rest }) =>
    R.createElement(tag, { role: accessibilityRole, 'aria-label': accessibilityLabel, onClick: onPress }, children);
  return { Pressable: host('button'), Text: host('span'), View: host('div') };
});
vi.mock('./Button', () => ({ Button: ({ title, onPress, variant }) => React.createElement('button', { type: 'button', 'data-variant': variant, onClick: onPress }, title) }));
vi.mock('./EmptyState', () => ({ EmptyState: ({ title, detail, action, alert }) => React.createElement('div', { role: alert ? 'alert' : undefined }, title, React.createElement('i', null, detail), action ? React.createElement('button', { type: 'button', 'data-variant': 'secondary', onClick: action.onPress }, action.label) : null) }));
vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({ colors: { ink: '#000', ink2: '#222', ink3: '#666', dangerText: '#b73737' }, fonts: { mono: 'm', sans: { medium: 'sm', semibold: 'ss' } }, fontSizes: { xs: 11, md: 15, lg: 18 } }),
}));

import { LoadFailed } from './LoadFailed';

describe('LoadFailed', () => {
  it('names what failed, shows the reason and retries', () => {
    const onRetry = vi.fn();
    render(<LoadFailed label="this conversation" error={new Error('read timeout')} onRetry={onRetry} />);
    expect(screen.getByRole('alert').textContent).toContain("Couldn't load this conversation");
    expect(screen.getByText('read timeout')).toBeTruthy();
    expect(screen.getByText('Retry').getAttribute('data-variant')).toBe('secondary');
    fireEvent.click(screen.getByText('Retry'));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('turns a raw transport error into a plain sentence', () => {
    render(<LoadFailed label="members" error={new Error('request timed out after 30000ms')} />);
    expect(screen.getByText('The daemon took too long to answer.')).toBeTruthy();
  });

  it('draws the inline Retry as the shared secondary button', () => {
    render(<LoadFailed inline label="members" onRetry={() => {}} />);
    expect(screen.getByText('Retry').getAttribute('data-variant')).toBe('secondary');
  });

  it('fits in a row when inline', () => {
    const onRetry = vi.fn();
    render(<LoadFailed inline label="members" onRetry={onRetry} />);
    fireEvent.click(screen.getByText('Retry'));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
