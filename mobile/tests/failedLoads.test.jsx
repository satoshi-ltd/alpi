import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  skills: null,
  tools: null,
  profile: null,
  call: vi.fn(),
}));

vi.mock('react-native', () => {
  const R = require('react');
  const host = (tag) => ({ children, onPress, accessibilityRole, accessibilityLabel, style, hitSlop, android_ripple, numberOfLines, ...rest }) =>
    R.createElement(tag, { role: accessibilityRole, 'aria-label': accessibilityLabel, onClick: onPress }, typeof children === 'function' ? children({ pressed: false }) : children);
  return {
    View: host('div'),
    Text: host('span'),
    Pressable: host('button'),
    ScrollView: ({ children }) => R.createElement('div', {}, children),
    RefreshControl: () => null,
  };
});
vi.mock('expo-router', () => ({
  useLocalSearchParams: () => ({ id: 'agora' }),
  usePathname: () => '/profile/agora',
  useRouter: () => ({ push: vi.fn(), back: vi.fn(), replace: vi.fn(), canGoBack: () => true }),
}));
vi.mock('react-native-safe-area-context', () => ({ SafeAreaView: ({ children }) => React.createElement('div', {}, children) }));
vi.mock('../src/theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { bg: '#fff', ink: '#000', ink2: '#222', ink3: '#666', dangerText: '#b73737', selected: '#eee' },
    fonts: { sans: { regular: 'r', medium: 'm', semibold: 's' }, mono: 'mono' },
    fontSizes: { xs: 11, sm: 12, md: 14, lg: 15 },
  }),
}));
vi.mock('../src/components/Button', () => ({ Button: ({ title, onPress }) => React.createElement('button', { type: 'button', onClick: onPress }, title) }));
vi.mock('../src/components/Pill', () => ({ Pill: ({ children }) => React.createElement('span', {}, children) }));
vi.mock('../src/components/Eyebrow', () => ({ Eyebrow: ({ children }) => React.createElement('span', {}, children) }));
vi.mock('../src/components/Row', () => ({
  Row: ({ label, helper }) => React.createElement('div', {}, label, helper ? ` ${helper}` : ''),
  RowGroup: ({ children }) => React.createElement('div', { 'data-row-group': '' }, children),
  RowSeparator: () => React.createElement('hr', {}),
  SectionHeader: ({ children }) => React.createElement('h3', {}, children),
}));
vi.mock('../src/components/SkeletonBar', () => ({ SkeletonBar: () => React.createElement('i', { 'data-bar': '' }) }));
vi.mock('../src/components/Sheet', () => ({ Sheet: ({ open, children }) => (open ? React.createElement('div', {}, children) : null) }));
vi.mock('../src/components/ScreenHeader', () => ({ ScreenHeader: ({ title }) => React.createElement('h1', {}, title) }));
vi.mock('../src/components/Toast', () => ({ useToast: () => vi.fn() }));
vi.mock('../src/components/TypedConfirm', () => ({ Bold: ({ children }) => children, Code: ({ children }) => children, TypedConfirm: () => null }));
vi.mock('../src/hooks/usePullRefresh', () => ({ usePullRefresh: () => ({ refreshing: false, onRefresh: () => {} }) }));
vi.mock('../src/hooks/useAttention', () => ({ useAttention: () => ({ att: null, refresh: () => {} }) }));
vi.mock('../src/hooks/useBack', () => ({ useBack: () => () => {} }));
vi.mock('../src/hooks/useDaemonData', () => ({ useSkills: () => h.skills, useTools: () => h.tools }));
vi.mock('../src/hooks/useSubject', () => ({ useProfile: () => h.profile }));
vi.mock('../src/lib/EndpointContext', () => ({ useEndpoint: () => ({ call: h.call }) }));

import SkillsList from '../app/profile/[id]/brain/skills/index.jsx';
import ToolsList from '../app/profile/[id]/brain/tools/index.jsx';
import McpList from '../app/profile/[id]/mcp/index.jsx';

const failed = () => ({ data: null, loading: false, error: new Error('timeout'), refresh: vi.fn() });

describe('failed loads never pose as empty lists', () => {
  it('skills', () => {
    h.skills = failed();
    render(<SkillsList />);
    expect(screen.getByRole('alert').textContent).toContain("Couldn't load skills");
    expect(screen.queryByText(/No skills/)).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(h.skills.refresh).toHaveBeenCalled();
  });

  it('tools', () => {
    h.tools = failed();
    render(<ToolsList />);
    expect(screen.getByRole('alert').textContent).toContain("Couldn't load tools");
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(h.tools.refresh).toHaveBeenCalled();
  });

  it('MCP servers', () => {
    h.profile = { profile: null, loading: false, error: new Error('timeout'), refresh: vi.fn() };
    render(<McpList />);
    expect(screen.getByRole('alert').textContent).toContain("Couldn't load MCP servers");
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(h.profile.refresh).toHaveBeenCalled();
  });

  it('a failed MCP handshake keeps its reason and retries the handshake', async () => {
    h.profile = { profile: { mcps: [{ name: 'atlassian', command: 'npx', args: [], env_keys: [] }] }, loading: false, error: null, refresh: vi.fn() };
    h.call.mockReset();
    h.call.mockRejectedValueOnce(new Error('spawn failed')).mockResolvedValueOnce({ tools: [{ name: 'search' }] });
    render(<McpList />);
    fireEvent.click(screen.getByText('atlassian').closest('button'));
    await waitFor(() => expect(screen.getByText(/spawn failed/)).toBeTruthy());
    expect(screen.getByRole('alert').textContent).toContain("Couldn't load tools");
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    await waitFor(() => expect(screen.getByText('search')).toBeTruthy());
    expect(h.call).toHaveBeenCalledTimes(2);
  });
});

describe('a list in flight draws its rows before they land', () => {
  const inFlight = () => ({ data: null, loading: true, error: null, refresh: vi.fn() });

  it.each([
    ['skills', () => { h.skills = inFlight(); return <SkillsList />; }, 'Loading skills'],
    ['tools', () => { h.tools = inFlight(); return <ToolsList />; }, 'Loading tools'],
    ['MCP servers', () => { h.profile = { profile: null, loading: true, error: null, refresh: vi.fn() }; return <McpList />; }, 'Loading MCP servers'],
  ])('%s show placeholder rows inside the card they will fill, with no word on screen', (_, screenOf, label) => {
    const { container } = render(screenOf());
    const wait = screen.getByRole('progressbar', { name: label });
    const card = wait.querySelector('[data-row-group]');
    expect(card).not.toBeNull();
    expect(card.querySelectorAll('[data-bar]').length).toBeGreaterThan(2);
    expect(container.textContent).not.toMatch(/Loading/);
  });
});
