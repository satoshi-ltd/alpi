import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({ tools: null, profile: null }));

vi.mock('react-native', () => {
  const R = require('react');
  const host = (tag) => ({ children, onPress, accessibilityRole, accessibilityLabel }) =>
    R.createElement(tag, { role: accessibilityRole, 'aria-label': accessibilityLabel, onClick: onPress }, typeof children === 'function' ? children({ pressed: false }) : children);
  return {
    View: host('div'),
    Text: host('span'),
    Pressable: host('button'),
    ScrollView: ({ children }) => R.createElement('div', {}, children),
    RefreshControl: () => null,
    ActivityIndicator: () => R.createElement('span', { 'data-testid': 'spinner' }),
  };
});
vi.mock('expo-router', () => ({
  useLocalSearchParams: () => ({ id: 'agora' }),
  useRouter: () => ({ push: vi.fn(), back: vi.fn(), replace: vi.fn() }),
}));
vi.mock('react-native-safe-area-context', () => ({ SafeAreaView: ({ children }) => React.createElement('div', {}, children) }));
vi.mock('../src/theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { bg: '#fff', ink: '#000', ink3: '#666', warning: '#c60', selected: '#eee' },
    fonts: { sans: { regular: 'r', semibold: 's' }, mono: 'mono', monoMedium: 'mm' },
    fontSizes: { xs: 11, sm: 12, md: 14, lg: 15 },
  }),
}));
vi.mock('../src/components/Button', () => ({ Button: () => null }));
vi.mock('../src/components/Pill', () => ({ Pill: ({ children }) => React.createElement('span', {}, children) }));
vi.mock('../src/components/Eyebrow', () => ({ Eyebrow: ({ children }) => React.createElement('span', {}, children) }));
vi.mock('../src/components/Row', () => ({
  Row: ({ label }) => React.createElement('div', {}, label),
  RowGroup: ({ children }) => React.createElement('div', { 'data-row-group': '' }, children),
  RowSeparator: () => React.createElement('hr', {}),
  SectionHeader: ({ children }) => React.createElement('h3', {}, children),
}));
vi.mock('../src/components/Sheet', () => ({ Sheet: () => null }));
vi.mock('../src/components/ScreenHeader', () => ({ ScreenHeader: ({ title }) => React.createElement('h1', {}, title) }));
vi.mock('../src/components/Toast', () => ({ useToast: () => vi.fn() }));
vi.mock('../src/components/TypedConfirm', () => ({ Bold: ({ children }) => children, Code: ({ children }) => children, TypedConfirm: () => null }));
vi.mock('../src/hooks/usePullRefresh', () => ({ usePullRefresh: () => ({ refreshing: false, onRefresh: () => {} }) }));
vi.mock('../src/hooks/useBack', () => ({ useBack: () => () => {} }));
vi.mock('../src/hooks/useDaemonData', () => ({ useTools: () => h.tools }));
vi.mock('../src/hooks/useSubject', () => ({ useProfile: () => h.profile }));
vi.mock('../src/lib/EndpointContext', () => ({ useEndpoint: () => ({ call: vi.fn() }) }));

import { EMPTY } from '../../common/emptyCopy.mjs';
import ToolsList from '../app/profile/[id]/brain/tools/index.jsx';
import McpList from '../app/profile/[id]/mcp/index.jsx';

const groupOf = (text) => screen.getByText(text).closest('[data-row-group]');

describe('custom settings lists sit in row groups', () => {
  it('groups the tools of one category together and keeps the header outside', () => {
    h.tools = {
      data: { tools: [
        { name: 'read_file', category: 'Filesystem' },
        { name: 'write_file', category: 'Filesystem' },
        { name: 'web_fetch', category: 'Web' },
      ] },
      loading: false,
      error: null,
    };
    render(<ToolsList />);
    expect(groupOf('read_file')).not.toBeNull();
    expect(groupOf('read_file')).toBe(groupOf('write_file'));
    expect(groupOf('web_fetch')).not.toBe(groupOf('read_file'));
    expect(screen.getByText('Filesystem').closest('[data-row-group]')).toBeNull();
  });

  it('puts the empty tools row in a group', () => {
    h.tools = { data: { tools: [] }, loading: false, error: null };
    render(<ToolsList />);
    expect(groupOf(EMPTY.tools.title)).not.toBeNull();
  });

  it('groups every MCP server in one list', () => {
    h.profile = {
      profile: { mcps: [
        { name: 'atlassian', command: 'npx', args: [], env_keys: [] },
        { name: 'github', command: 'npx', args: [], env_keys: [] },
      ] },
      loading: false,
      error: null,
      refresh: vi.fn(),
    };
    render(<McpList />);
    expect(groupOf('atlassian')).not.toBeNull();
    expect(groupOf('atlassian')).toBe(groupOf('github'));
  });
});
