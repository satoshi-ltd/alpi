import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => {
  const R = require('react');
  return {
    StyleSheet: { create: (s) => s },
    Text: ({ children }) => R.createElement('span', null, children),
    View: ({ children }) => R.createElement('div', null, children),
  };
});
vi.mock('../../components/Sheet', () => {
  const R = require('react');
  return {
    Sheet: ({ open, children, primaryAction, footer, dismissible }) => (open
      ? R.createElement('div', { 'data-dismissible': String(dismissible ?? true) },
        children,
        (Array.isArray(primaryAction) ? primaryAction : [primaryAction]).filter(Boolean).map((a) =>
          R.createElement('button', { key: a.label, type: 'button', onClick: a.onPress, 'data-variant': a.variant ?? 'primary' }, a.label)),
        footer)
      : null),
  };
});
vi.mock('../../theme/ThemeContext', () => ({
  useTheme: () => ({ colors: { ink2: '#333', ink3: '#666' }, fonts: { sans: { regular: 'r', medium: 'm' } }, fontSizes: { sm: 12, md: 15 } }),
}));

import { NotificationPrimer } from './NotificationPrimer';

describe('NotificationPrimer', () => {
  it('offers Not now beside Enable and never closes on a stray gesture', () => {
    const onEnable = vi.fn();
    const onDecline = vi.fn();
    const { container } = render(<NotificationPrimer open onEnable={onEnable} onDecline={onDecline} />);
    expect(container.firstChild.getAttribute('data-dismissible')).toBe('false');
    const later = screen.getByRole('button', { name: 'Not now' });
    expect(later.getAttribute('data-variant')).toBe('ghost');
    fireEvent.click(later);
    expect(onDecline).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole('button', { name: 'Enable notifications' }));
    expect(onEnable).toHaveBeenCalledTimes(1);
  });
});
