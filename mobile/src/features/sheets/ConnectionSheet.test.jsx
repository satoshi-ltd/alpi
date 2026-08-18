import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

afterEach(cleanup);

const { fontOf } = vi.hoisted(() => ({
  fontOf: (style) => [style].flat(Infinity).filter(Boolean).reduce((f, s) => s.fontFamily ?? f, null),
}));

vi.mock('react-native', () => {
  const View = ({ children, style, ...p }) => React.createElement('div', p, children);
  const Text = ({ children, style, ...p }) =>
    React.createElement('span', { ...p, 'data-font': fontOf(style) }, children);
  return { View, Text, ScrollView: ({ children }) => React.createElement('div', {}, children) };
});

vi.mock('../../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { ink: '#000', ink2: '#333', ink3: '#666', success: '#0a0', warning: '#c80', danger: '#c00' },
    fonts: { sans: { regular: 'Inter_400Regular' }, mono: 'JetBrainsMono_400Regular' },
    fontSizes: { xs: 11 },
  }),
}));

vi.mock('../../components/ActionSheet', () => ({ ActionSheet: () => null }));
vi.mock('../../components/Dot', () => ({ Dot: () => React.createElement('span', { 'data-dot': 'true' }) }));
vi.mock('../../components/Icon', () => ({ Icon: ({ name }) => React.createElement('span', { 'data-icon': name }) }));
vi.mock('../../components/Row', () => ({
  Row: ({ label }) => React.createElement('div', {}, label),
  RowSeparator: () => React.createElement('hr', {}),
}));
vi.mock('../../components/Sheet', () => ({
  Sheet: ({ open, children }) => (open ? React.createElement('div', { 'data-sheet': 'true' }, children) : null),
}));
vi.mock('../../components/Toast', () => ({ useToast: () => vi.fn() }));
vi.mock('../../components/TypedConfirm', () => ({
  Bold: ({ children }) => React.createElement('b', {}, children),
  Code: ({ children }) => React.createElement('code', {}, children),
  TypedConfirm: () => null,
}));
vi.mock('../../lib/rpc', () => ({ call: vi.fn(async () => ({})) }));
vi.mock('../../lib/EndpointContext', () => ({
  useEndpoint: () => ({
    connections: [],
    activeId: null,
    probeState: new Map(),
    versionState: new Map(),
    updateState: new Map(),
    roleState: new Map(),
    setActive: vi.fn(),
    forget: vi.fn(),
    probeAll: vi.fn(async () => {}),
  }),
}));

import { ConnectionSheet } from './ConnectionSheet';

describe('ConnectionSheet typography', () => {
  it('renders the unpaired notice in a theme font', () => {
    render(<ConnectionSheet open onClose={() => {}} />);
    expect(screen.getByText('Not paired yet — tap below to scan a QR.').getAttribute('data-font')).toBe('Inter_400Regular');
  });
});
