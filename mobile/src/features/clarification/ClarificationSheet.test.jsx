import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

const { fontOf } = vi.hoisted(() => ({
  fontOf: (style) => [style].flat(Infinity).filter(Boolean).reduce((f, s) => s.fontFamily ?? f, null),
}));

vi.mock('react-native', () => {
  const View = ({ children, style, ...p }) => React.createElement('div', p, children);
  const Text = ({ children, style, ...p }) =>
    React.createElement('span', { ...p, 'data-font': fontOf(style) }, children);
  const Pressable = ({ children, onPress, disabled, hitSlop, style, ...p }) =>
    React.createElement('button', { type: 'button', onClick: onPress, disabled, ...p }, children);
  const TextInput = ({ style, ...p }) => React.createElement('input', {});
  return { View, Text, TextInput, Pressable };
});

vi.mock('../../theme/ThemeContext', async () => {
  const tokens = await import('../../theme/tokens');
  return {
    useTheme: () => ({
      colors: { ink: '#000', ink2: '#333', ink3: '#666', line: '#ddd', bgInput: '#fafafa', danger: '#f00' },
      fonts: {
        sans: { regular: 'Inter_400Regular', medium: 'Inter_500Medium', bold: 'Inter_700Bold' },
        mono: 'JetBrainsMono_400Regular',
      },
      fontSizes: tokens.fontSizes,
    }),
  };
});

vi.mock('../../components/Icon', () => ({ Icon: ({ name }) => React.createElement('span', { 'data-icon': name }) }));
vi.mock('../../components/Sheet', () => ({
  Sheet: ({ open, children }) => (open ? React.createElement('div', { 'data-sheet': 'true' }, children) : null),
}));
vi.mock('./useClarificationQueue', () => ({
  useClarificationQueue: () => ({
    current: {
      request_id: 'r1',
      question: 'Which hotels ship first?',
      multi: true,
      choices: [{ label: 'roma' }, { label: 'lisboa' }],
    },
    busy: false,
    error: null,
    respond: vi.fn(),
    cancel: vi.fn(),
  }),
}));

import { ClarificationSheet } from './ClarificationSheet';

describe('ClarificationSheet typography', () => {
  it('draws the checked tick in a theme font', () => {
    render(<ClarificationSheet />);
    expect(screen.queryByText('✓')).toBeNull();
    fireEvent.click(screen.getByText('roma').closest('button'));
    expect(screen.getByText('✓').getAttribute('data-font')).toBe('Inter_400Regular');
  });

  it('keeps the question and its choices on their own tokens', () => {
    render(<ClarificationSheet />);
    expect(screen.getByText('Which hotels ship first?').getAttribute('data-font')).toBe('Inter_700Bold');
    expect(screen.getByText('lisboa').getAttribute('data-font')).toBe('Inter_400Regular');
  });
});

describe('ClarificationSheet dismissal contract', () => {
  it('words no Cancel in its header — the sheet close icon owns dismissal', () => {
    render(<ClarificationSheet />);
    expect(screen.queryByText('Cancel')).toBeNull();
  });

  it('keeps the choices as the only worded actions', () => {
    render(<ClarificationSheet />);
    expect(screen.getByText('roma')).toBeTruthy();
    expect(screen.getByText('lisboa')).toBeTruthy();
  });
});
