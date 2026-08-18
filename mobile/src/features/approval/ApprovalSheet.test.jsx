import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({ respond: vi.fn() }));

vi.mock('react-native', () => {
  const View = ({ children, style, ...p }) => React.createElement('div', p, children);
  const Text = ({ children, style, ...p }) => React.createElement('span', p, children);
  const Pressable = ({ children, onPress, disabled, hitSlop, style, ...p }) =>
    React.createElement(
      'button',
      { type: 'button', onClick: onPress, disabled },
      typeof children === 'function' ? children({ pressed: false }) : children,
    );
  const ScrollView = ({ children }) => React.createElement('div', {}, children);
  return { View, Text, Pressable, ScrollView };
});

vi.mock('../../components/Diamond', () => ({ Diamond: () => React.createElement('span', { 'data-diamond': 'true' }) }));
vi.mock('../../components/Sheet', () => ({
  Sheet: ({ open, children }) => (open ? React.createElement('div', { 'data-sheet': 'true' }, children) : null),
}));
vi.mock('../../theme/ThemeContext', async () => {
  const tokens = await import('../../theme/tokens');
  return {
    useTheme: () => ({
      colors: { ink: '#000', ink2: '#333', ink3: '#666', ink4: '#999', bgPane: '#fff', bgInput: '#fafafa', line2: '#eee', hover: '#f4f4f4', danger: '#f00', warning: '#fc0' },
      fonts: { sans: { regular: 'r', medium: 'm', semibold: 's', bold: 'b' }, mono: 'mono' },
      fontSizes: tokens.fontSizes,
    }),
  };
});
vi.mock('./useApprovalQueue', () => ({
  useApprovalQueue: () => ({
    current: { request_id: 'a1', command: 'rm -rf build', severity: 'dangerous', profile: 'doc', cwd: '/git/alf' },
    busy: false,
    error: null,
    respond: h.respond,
  }),
}));

import { ApprovalSheet } from './ApprovalSheet';

describe('ApprovalSheet dismissal contract', () => {
  it('words no Cancel — the sheet close icon owns dismissal', () => {
    render(<ApprovalSheet />);
    expect(screen.queryByText('Cancel')).toBeNull();
  });

  it('keeps Deny as a worded action because it is a decision, not a dismissal', () => {
    h.respond.mockClear();
    render(<ApprovalSheet />);
    fireEvent.click(screen.getByText('Deny').closest('button'));
    expect(h.respond).toHaveBeenCalledWith('deny');
  });

  it('keeps every allow choice worded alongside it', () => {
    render(<ApprovalSheet />);
    expect(screen.getByText('Allow once')).toBeTruthy();
    expect(screen.getByText('Allow this session')).toBeTruthy();
    expect(screen.getByText('Always allow')).toBeTruthy();
  });
});
