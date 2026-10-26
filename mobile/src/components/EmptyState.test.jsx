import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => ({
  View: ({ children, style, accessibilityRole }) => React.createElement('div', { role: accessibilityRole, 'data-style': JSON.stringify(style) }, children),
  Text: ({ children }) => React.createElement('span', null, children),
}));
vi.mock('./Button', () => ({
  Button: ({ title, variant, onPress }) => React.createElement('button', { type: 'button', 'data-variant': variant, onClick: onPress }, title),
}));
vi.mock('../theme/ThemeContext', async () => {
  const tokens = await import('../theme/tokens');
  return {
    useTheme: () => ({
      colors: { ink: '#000', ink3: '#666' },
      fonts: { sans: { semibold: 's', regular: 'r' }, mono: 'm' },
      fontSizes: tokens.fontSizes,
    }),
  };
});

import { EmptyState } from './EmptyState';

describe('EmptyState', () => {
  it('centres a title and one sentence in the free space', () => {
    const { container } = render(<EmptyState title="Nothing running" detail="Turns show up here." />);
    const root = JSON.parse(container.firstChild.getAttribute('data-style'));
    expect([root.flex, root.alignItems, root.justifyContent]).toEqual([1, 'center', 'center']);
    expect(screen.getByText('Nothing running')).toBeTruthy();
    expect(screen.getByText('Turns show up here.')).toBeTruthy();
  });

  it('draws its action as the shared secondary button', () => {
    const onPress = vi.fn();
    render(<EmptyState title="Couldn't load schedule" action={{ label: 'Retry', onPress }} />);
    const retry = screen.getByText('Retry');
    expect(retry.getAttribute('data-variant')).toBe('secondary');
    fireEvent.click(retry);
    expect(onPress).toHaveBeenCalledTimes(1);
  });

  it('draws no button and no sentence when none is given, and announces an alert on request', () => {
    const { container } = render(<EmptyState alert title="Couldn't load" />);
    expect(screen.queryByRole('button')).toBeNull();
    expect(container.querySelector('[role="alert"]')).toBeTruthy();
  });
});
