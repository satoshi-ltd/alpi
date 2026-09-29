import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => {
  const R = require('react');
  const host = (tag) => ({ children }) => R.createElement(tag, {}, children);
  return { Text: host('span'), View: host('div') };
});
vi.mock('../src/components/Button', () => ({ Button: ({ title, onPress }) => React.createElement('button', { type: 'button', onClick: onPress }, title) }));
vi.mock('../src/theme/ThemeContext', () => ({
  ThemeProvider: ({ children }) => children,
  useTheme: () => ({ colors: { bg: '#fff', ink: '#000', ink3: '#666' }, fonts: { mono: 'm', sans: { semibold: 's' } }, fontSizes: { xs: 11, lg: 18 } }),
}));

import { ErrorBoundary } from '../src/features/shell/CrashScreen';

describe('route crash screen', () => {
  it('names the failure and offers a reload', () => {
    const retry = vi.fn();
    render(<ErrorBoundary error={new Error('boom')} retry={retry} />);
    expect(screen.getByText('Something broke on screen')).toBeTruthy();
    expect(screen.getByText('boom')).toBeTruthy();
    fireEvent.click(screen.getByText('Reload'));
    expect(retry).toHaveBeenCalledTimes(1);
  });
});
