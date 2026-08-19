import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  fontOf: (style) => [style].flat(Infinity).filter(Boolean).reduce((f, s) => s.fontFamily ?? f, null),
  call: vi.fn(),
}));

vi.mock('react-native', () => {
  const View = ({ children, style, ...p }) => React.createElement('div', p, children);
  const Text = ({ children, style, numberOfLines, ellipsizeMode, ...p }) =>
    React.createElement('span', { ...p, 'data-font': h.fontOf(style) }, children);
  const Pressable = ({ children, onPress, android_ripple, style, ...p }) =>
    React.createElement('button', { type: 'button', onClick: onPress, ...p }, children);
  return {
    View,
    Text,
    Pressable,
    ScrollView: ({ children }) => React.createElement('div', {}, children),
    ActivityIndicator: () => React.createElement('span', { 'data-testid': 'spinner' }),
  };
});

vi.mock('expo-router', () => ({
  useLocalSearchParams: () => ({ id: 'agora' }),
  usePathname: () => '/profile/agora/mcp',
  useRouter: () => ({ push: vi.fn(), back: vi.fn(), replace: vi.fn(), canGoBack: () => true }),
}));

vi.mock('react-native-safe-area-context', () => ({
  SafeAreaView: ({ children }) => React.createElement('div', {}, children),
}));

vi.mock('../src/theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { bg: '#fff', ink: '#000', ink3: '#666', danger: '#f00', selected: '#eee' },
    fonts: { sans: { regular: 'Inter_400Regular', semibold: 'Inter_600SemiBold' }, mono: 'JetBrainsMono_400Regular' },
    fontSizes: { xs: 11, sm: 12, lg: 15 },
  }),
}));

vi.mock('../src/components/Button', () => ({ Button: ({ title }) => React.createElement('button', { type: 'button' }, title) }));
vi.mock('../src/components/Pill', () => ({ Pill: ({ children }) => React.createElement('span', {}, children) }));
vi.mock('../src/components/Row', () => ({
  Row: ({ label }) => React.createElement('div', {}, label),
  RowSeparator: () => React.createElement('hr', {}),
  SectionHeader: ({ children }) => React.createElement('h3', {}, children),
}));
vi.mock('../src/components/Sheet', () => ({
  Sheet: ({ open, children }) => (open ? React.createElement('div', { 'data-sheet': 'true' }, children) : null),
}));
vi.mock('../src/components/ScreenHeader', () => ({ ScreenHeader: ({ title }) => React.createElement('h1', {}, title) }));
vi.mock('../src/components/Toast', () => ({ useToast: () => vi.fn() }));
vi.mock('../src/components/TypedConfirm', () => ({
  Bold: ({ children }) => React.createElement('b', {}, children),
  Code: ({ children }) => React.createElement('code', {}, children),
  TypedConfirm: () => null,
}));
vi.mock('../src/hooks/useSubject', () => ({
  useProfile: () => ({
    profile: { mcps: [{ name: 'atlassian', command: 'npx', args: ['-y', 'mcp-atlassian'], env_keys: [] }] },
    loading: false,
    refresh: vi.fn(),
  }),
}));
vi.mock('../src/lib/EndpointContext', () => ({ useEndpoint: () => ({ call: h.call }) }));

import McpList from '../app/profile/[id]/mcp/index.jsx';

function openServer() {
  render(<McpList />);
  fireEvent.click(screen.getByText('atlassian').closest('button'));
}

describe('MCP server sheet typography', () => {
  it('renders the handshake notice in a theme font', () => {
    h.call.mockReturnValue(new Promise(() => {}));
    openServer();
    expect(screen.getByText('handshaking with server…').getAttribute('data-font')).toBe('Inter_400Regular');
  });

  it('renders the handshake failure in a theme font', async () => {
    h.call.mockRejectedValue(new Error('spawn failed'));
    openServer();
    await waitFor(() => expect(screen.getByText(/spawn failed/)).toBeTruthy());
    expect(screen.getByText(/spawn failed/).getAttribute('data-font')).toBe('Inter_400Regular');
  });

  it('renders the empty-tools notice in a theme font', async () => {
    h.call.mockResolvedValue({ tools: [] });
    openServer();
    await waitFor(() => expect(screen.getByText('no tools')).toBeTruthy());
    expect(screen.getByText('no tools').getAttribute('data-font')).toBe('Inter_400Regular');
  });

  it('renders a tool name in mono and its description in the sans token', async () => {
    h.call.mockResolvedValue({ tools: [{ name: 'search', description: 'find a page' }] });
    openServer();
    await waitFor(() => expect(screen.getByText('find a page')).toBeTruthy());
    expect(screen.getByText('search').getAttribute('data-font')).toBe('JetBrainsMono_400Regular');
    expect(screen.getByText('find a page').getAttribute('data-font')).toBe('Inter_400Regular');
  });
});
