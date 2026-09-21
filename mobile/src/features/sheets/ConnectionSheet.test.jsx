import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
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
    fonts: { sans: { regular: 'Geist_400Regular' }, mono: 'GeistMono_400Regular' },
    fontSizes: { xs: 11 },
  }),
}));

vi.mock('../../components/ActionSheet', () => ({ ActionSheet: () => null }));
vi.mock('../../components/Dot', () => ({ Dot: () => React.createElement('span', { 'data-dot': 'true' }) }));
vi.mock('../../components/Icon', () => ({ Icon: ({ name }) => React.createElement('span', { 'data-icon': name }) }));
vi.mock('../../components/Row', () => ({
  Row: ({ label, value }) => React.createElement('div', {}, label, value),
  RowSeparator: () => React.createElement('hr', {}),
}));
vi.mock('../../components/Sheet', () => ({
  Sheet: ({ open, children }) => (open ? React.createElement('div', { 'data-sheet': 'true' }, children) : null),
}));
vi.mock('../../components/Toast', () => ({ useToast: () => vi.fn() }));
vi.mock('../../components/TextPrompt', () => ({ TextPrompt: () => null }));
vi.mock('../../components/TypedConfirm', () => ({
  Bold: ({ children }) => React.createElement('b', {}, children),
  Code: ({ children }) => React.createElement('code', {}, children),
  TypedConfirm: () => null,
}));
vi.mock('../../lib/rpc', () => ({ call: vi.fn(async () => ({})) }));
const endpoint = vi.hoisted(() => ({ state: null }));
const emptyEndpoint = () => ({
  connections: [],
  activeId: null,
  probeState: new Map(),
  versionState: new Map(),
  updateState: new Map(),
  roleState: new Map(),
  setActive: vi.fn(),
  rename: vi.fn(),
  forget: vi.fn(),
  probeAll: vi.fn(async () => {}),
});
vi.mock('../../lib/EndpointContext', () => ({ useEndpoint: () => endpoint.state }));
beforeEach(() => {
  endpoint.state = emptyEndpoint();
});

import { ConnectionSheet } from './ConnectionSheet';

describe('ConnectionSheet typography', () => {
  it('renders the unpaired notice in a theme font', () => {
    render(<ConnectionSheet open onClose={() => {}} />);
    expect(screen.getByText('Not paired yet — tap below to scan a QR.').getAttribute('data-font')).toBe('Geist_400Regular');
  });
});

describe('ConnectionSheet list', () => {
  it('does not flag an available update on the row; the long-press action carries it', () => {
    const casa = { id: 'c1', kind: 'remote', name: 'casa', url: 'ws://casa:49200', lastUsed: 1 };
    endpoint.state = {
      ...emptyEndpoint(),
      connections: [casa],
      activeId: 'c1',
      probeState: new Map([['c1', 'online']]),
      versionState: new Map([['c1', '0.15.0']]),
      updateState: new Map([['c1', '0.15.2']]),
    };
    render(<ConnectionSheet open onClose={() => {}} />);
    expect(screen.getByText('current')).toBeTruthy();
    expect(screen.queryByText('update')).toBeNull();
  });
});
