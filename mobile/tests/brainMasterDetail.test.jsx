import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  wide: false,
  params: { id: 'doc' },
  push: vi.fn(),
  replace: vi.fn(),
  skills: [],
  tools: [],
  att: null,
  loading: false,
}));

vi.mock('react-native', () => {
  const View = ({ children, testID }) => React.createElement('div', testID ? { testid: testID } : {}, children);
  const Pass = ({ children }) => React.createElement('div', {}, children);
  return { View, Text: ({ children }) => React.createElement('span', {}, children), Pressable: Pass, ScrollView: Pass, RefreshControl: () => null, StyleSheet: { create: (s) => s, absoluteFillObject: {} }, useWindowDimensions: () => ({ width: 390, height: 844 }) };
});
vi.mock('expo-router', () => ({ useLocalSearchParams: () => h.params, useRouter: () => ({ push: h.push, replace: h.replace }) }));
vi.mock('react-native-safe-area-context', () => ({ SafeAreaView: ({ children }) => React.createElement('div', {}, children) }));
vi.mock('../src/theme/ThemeContext', () => ({
  useTheme: () => ({ colors: { bg: '#fff', line: '#ddd', ink3: '#666' }, fonts: { sans: { regular: 'r' } }, fontSizes: { md: 14 } }),
}));
vi.mock('../src/hooks/useMasterDetail', () => ({ useMasterDetail: () => h.wide }));
vi.mock('../src/hooks/useBack', () => ({ useBack: () => () => {} }));
vi.mock('../src/hooks/useAttention', () => ({ useAttention: () => ({ att: h.att }) }));
vi.mock('../src/hooks/useDaemonData', () => ({
  useSkills: () => ({ data: { skills: h.skills }, loading: h.loading }),
  useTools: () => ({ data: { tools: h.tools }, loading: h.loading }),
}));
vi.mock('../src/features/profile/PanelHeader', () => ({ PanelHeader: ({ section, count }) => React.createElement('header', {}, `${section}·${count}`) }));
vi.mock('../src/features/brain/SkillsList', async (importOriginal) => ({
  ...(await importOriginal()),
  SkillsList: ({ selectedKey, onOpen }) => React.createElement('ul', {}, h.skills.map((s) => React.createElement('li', { key: s.name }, React.createElement('button', { type: 'button', 'data-selected': String(selectedKey === (s.path ?? `${s.category ?? ''}/${s.name}`)), onClick: () => onOpen({ ...s, rawCategory: s.category ?? '' }) }, s.name)))),
}));
vi.mock('../src/features/brain/ToolsList', async (importOriginal) => ({
  ...(await importOriginal()),
  ToolsList: ({ selectedName, onOpen }) => React.createElement('ul', {}, h.tools.map((t) => React.createElement('li', { key: t.name }, React.createElement('button', { type: 'button', 'data-selected': String(selectedName === t.name), onClick: () => onOpen(t) }, t.name)))),
}));
vi.mock('../src/features/brain/SkillDetail', () => ({ SkillDetail: ({ name, category, embedded }) => React.createElement('article', { 'data-detail': `skill:${name}:${category ?? ''}:${embedded ? 'embedded' : 'page'}` }) }));
vi.mock('../src/features/brain/ToolDetail', () => ({ ToolDetail: ({ name, embedded }) => React.createElement('article', { 'data-detail': `tool:${name}:${embedded ? 'embedded' : 'page'}` }) }));

import SkillsRoute from '../app/profile/[id]/brain/skills/index.jsx';
import SkillRoute from '../app/profile/[id]/brain/skills/[name].jsx';
import ToolsRoute from '../app/profile/[id]/brain/tools/index.jsx';
import ToolRoute from '../app/profile/[id]/brain/tools/[name].jsx';

const detail = () => document.querySelector('[data-detail]')?.getAttribute('data-detail');

beforeEach(() => {
  h.wide = false;
  h.params = { id: 'doc' };
  h.push.mockClear();
  h.replace.mockClear();
  h.skills = [
    { name: 'brief-writer', category: 'writing', path: 'writing/brief-writer' },
    { name: 'hotel-intake', category: 'research', path: 'research/hotel-intake' },
  ];
  h.tools = [{ name: 'web_fetch', category: 'Web' }, { name: 'read_file', category: 'Filesystem' }];
  h.att = null;
  h.loading = false;
});

describe('skills on a wide pane', () => {
  beforeEach(() => { h.wide = true; });

  it('opens the first skill of the list beside it, in the order the list shows', () => {
    render(<SkillsRoute />);
    expect(detail()).toBe('skill:hotel-intake:research:embedded');
    expect(document.querySelector('[testid="master-list"]')).toBeTruthy();
  });

  it('puts a skill that needs the user first', () => {
    h.att = { skills: [{ name: 'brief-writer', category: 'writing', message: 'lint' }] };
    render(<SkillsRoute />);
    expect(detail()).toBe('skill:brief-writer:writing:embedded');
  });

  it('shows the skill tapped without pushing a page', () => {
    render(<SkillsRoute />);
    fireEvent.click(screen.getByText('brief-writer'));
    expect(detail()).toBe('skill:brief-writer:writing:embedded');
    expect(h.push).not.toHaveBeenCalled();
    expect(screen.getByText('brief-writer').getAttribute('data-selected')).toBe('true');
  });

  it('opens the skill the page it came from was showing', () => {
    h.params = { id: 'doc', name: 'brief-writer', category: 'writing' };
    render(<SkillsRoute />);
    expect(detail()).toBe('skill:brief-writer:writing:embedded');
  });

  it('keeps the empty line away while the list loads', () => {
    h.skills = [];
    h.loading = true;
    render(<SkillsRoute />);
    expect(document.querySelector('[testid="master-detail"]').textContent).not.toContain('No skills installed');
  });

  it('sends a skill page opened on a wide pane back to the list', () => {
    h.params = { id: 'doc', name: 'brief-writer', category: 'writing' };
    const { container } = render(<SkillRoute />);
    expect(container.firstChild).toBeNull();
    expect(h.replace).toHaveBeenCalledWith({ pathname: '/profile/doc/brain/skills', params: { name: 'brief-writer', category: 'writing' } });
  });
});

describe('skills on a phone', () => {
  it('keeps the list alone and pushes the page', () => {
    render(<SkillsRoute />);
    expect(document.querySelector('[testid="master-list"]')).toBeNull();
    fireEvent.click(screen.getByText('brief-writer'));
    expect(h.push).toHaveBeenCalledWith({ pathname: '/profile/doc/brain/skills/[name]', params: { name: 'brief-writer', path: 'writing/brief-writer', category: 'writing' } });
  });

  it('draws the page with its own header', () => {
    h.params = { id: 'doc', name: 'brief-writer', category: 'writing' };
    render(<SkillRoute />);
    expect(detail()).toBe('skill:brief-writer:writing:page');
  });
});

describe('tools on a wide pane', () => {
  beforeEach(() => { h.wide = true; });

  it('opens the first tool in category order, or the one a link names', () => {
    render(<ToolsRoute />);
    expect(detail()).toBe('tool:read_file:embedded');
    cleanup();
    h.params = { id: 'doc', name: 'web_fetch' };
    render(<ToolsRoute />);
    expect(detail()).toBe('tool:web_fetch:embedded');
  });

  it('shows the tool tapped and sends a tool page back to the list', () => {
    render(<ToolsRoute />);
    fireEvent.click(screen.getByText('web_fetch'));
    expect(detail()).toBe('tool:web_fetch:embedded');
    expect(h.push).not.toHaveBeenCalled();
    cleanup();
    h.params = { id: 'doc', name: 'web_fetch' };
    render(<ToolRoute />);
    expect(h.replace).toHaveBeenCalledWith({ pathname: '/profile/doc/brain/tools', params: { name: 'web_fetch' } });
  });
});

describe('tools that vanish or are still loading', () => {
  beforeEach(() => { h.wide = true; });

  it('falls back to the first tool when the one it showed is gone', () => {
    h.params = { id: 'doc', name: 'gone_tool' };
    render(<ToolsRoute />);
    expect(detail()).toBe('tool:read_file:embedded');
  });

  it('keeps the empty line away while the list loads', () => {
    h.tools = [];
    h.loading = true;
    render(<ToolsRoute />);
    expect(document.querySelector('[testid="master-detail"]').textContent).not.toContain('No tools registered');
  });
});

describe('tools on a phone', () => {
  it('pushes the tool page and draws it with its own header', () => {
    render(<ToolsRoute />);
    fireEvent.click(screen.getByText('web_fetch'));
    expect(h.push).toHaveBeenCalledWith({ pathname: '/profile/doc/brain/tools/[name]', params: { name: 'web_fetch' } });
    cleanup();
    h.params = { id: 'doc', name: 'web_fetch' };
    render(<ToolRoute />);
    expect(detail()).toBe('tool:web_fetch:page');
  });
});
