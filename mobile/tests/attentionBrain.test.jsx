import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  att: null,
  skills: { data: { skills: [] }, refresh: () => {} },
  mem: { data: {}, usage: {}, refresh: () => {} },
  editor: { loading: false, raw: '', editing: false, canEdit: false, dirty: false },
  detail: null,
  params: { id: 'abby' },
  push: vi.fn(),
}));

vi.mock('react-native', () => {
  const R = require('react');
  const Pressable = ({ children, accessibilityLabel, style, onPress }) =>
    R.createElement('button', { onClick: onPress, 'aria-label': accessibilityLabel, 'data-minheight': (typeof style === 'function' ? style({ pressed: false }) : style)?.minHeight }, typeof children === 'function' ? children({ pressed: false }) : children);
  const View = ({ children, accessibilityRole }) => R.createElement('div', { role: accessibilityRole }, children);
  return {
    View, Pressable,
    Text: ({ children }) => R.createElement('span', {}, children),
    ScrollView: ({ children }) => R.createElement('div', {}, children),
    RefreshControl: () => null,
    ActivityIndicator: () => null,
    TextInput: () => null,
    Alert: { alert: () => {} },
    StyleSheet: { create: (s) => s },
  };
});
vi.mock('expo-router', () => ({
  useLocalSearchParams: () => h.params,
  useRouter: () => ({ push: h.push }),
  useFocusEffect: () => {},
}));
vi.mock('react-native-safe-area-context', () => ({ SafeAreaView: ({ children }) => React.createElement('div', {}, children) }));
vi.mock('../src/theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { bg: '#fff', ink: '#000', ink2: '#222', ink3: '#666', ink4: '#999', danger: '#f00', dangerText: '#a00', hover: '#eee', selected: '#ddd', line: '#eee' },
    fonts: { sans: { regular: 'r', medium: 'm', semibold: 's' }, mono: 'mono' },
    fontSizes: { xs: 11, sm: 12, md: 14, lg: 15, xl: 18 },
  }),
}));
vi.mock('../src/components/Row', () => ({
  Row: ({ label }) => React.createElement('div', {}, label),
  RowGroup: ({ children }) => React.createElement('div', {}, children),
  RowSeparator: () => null,
  SectionHeader: ({ children }) => React.createElement('h2', {}, children),
}));
vi.mock('../src/components/Dot', () => ({ Dot: ({ color }) => React.createElement('i', { 'data-dot': color }) }));
vi.mock('../src/components/Icon', () => ({ Icon: () => null }));
vi.mock('../src/components/RichText', () => ({ RichText: ({ children }) => React.createElement('p', {}, children) }));
vi.mock('../src/components/LoadFailed', () => ({ LoadFailed: () => null }));
vi.mock('../src/components/AlertBanner', () => ({ AlertBanner: ({ lead, detail }) => React.createElement('div', { role: 'alert' }, `${lead} | ${detail}`) }));
vi.mock('../src/features/profile/PanelHeader', () => ({ PanelHeader: () => null }));
vi.mock('../src/features/profile/StatusWord', () => ({ StatusWord: ({ word }) => React.createElement('span', {}, word) }));
vi.mock('../src/hooks/useAttention', () => ({ useAttention: () => ({ att: h.att, refresh: () => {} }) }));
vi.mock('../src/hooks/useBack', () => ({ useBack: () => () => {} }));
vi.mock('../src/hooks/useDirtyBack', () => ({ useDirtyBack: () => () => {} }));
vi.mock('../src/hooks/usePullRefresh', () => ({ usePullRefresh: () => ({}) }));
vi.mock('../src/hooks/useMemoryEditor', () => ({ useMemoryEditor: () => h.editor }));
vi.mock('../src/hooks/useDaemonData', () => ({ useSkills: () => h.skills, useProfileMemory: () => h.mem }));
vi.mock('../src/lib/EndpointContext', () => ({ useEndpoint: () => ({ call: async (_m, params) => ({ skill: { ...h.detail, category: params.category } }) }) }));

import SkillsList from '../app/profile/[id]/brain/skills/index.jsx';
import SkillDetail from '../app/profile/[id]/brain/skills/[name].jsx';
import MemoryList from '../app/profile/[id]/brain/memory/index.jsx';
import MemoryDetail from '../app/profile/[id]/brain/memory/[name].jsx';

beforeEach(() => {
  h.att = null;
  h.push.mockClear();
  h.params = { id: 'abby' };
  h.skills = {
    data: { skills: [
      { name: 'alpha', category: 'research', description: 'does alpha' },
      { name: 'review-digest', category: 'research', description: 'summarises', status: 'invalid' },
      { name: 'zeta', category: null },
    ] },
    refresh: () => {},
  };
  h.mem = { data: { 'AGENT.md': 'a', 'MEMORY.md': 'm', 'USER.md': 'u' }, usage: { 'MEMORY.md': { used: 2400, limit: 2000, over: true } }, refresh: () => {} };
  h.editor = { loading: false, raw: 'x', editing: false, canEdit: false, dirty: false };
});

describe('skills list', () => {
  const lint = { name: 'review-digest', category: 'research', problem: 'lint', message: 'bad' };

  it('lifts a flagged skill into a Needs you group with a danger dot and its word', () => {
    h.att = { skills: [lint] };
    const { container } = render(<SkillsList />);
    const headings = [...container.querySelectorAll('h2')].map((n) => n.textContent);
    expect(headings).toEqual(['Needs you · 1', 'Research', 'Uncategorized']);
    expect(screen.getAllByText('review-digest').length).toBe(1);
    expect(screen.getByText('lint')).toBeTruthy();
    expect(container.querySelector('[data-dot="#f00"]')).toBeTruthy();
    for (const b of container.querySelectorAll('button')) expect(Number(b.getAttribute('data-minheight'))).toBeGreaterThanOrEqual(44);
  });

  it('says missing for a missing requirement', () => {
    h.att = { skills: [{ ...lint, problem: 'missing' }] };
    render(<SkillsList />);
    expect(screen.getByText('missing')).toBeTruthy();
  });

  it('keeps today\'s list when nothing is flagged or the daemon has no verb', () => {
    const { container } = render(<SkillsList />);
    expect([...container.querySelectorAll('h2')].map((n) => n.textContent)).toEqual(['Research', 'Uncategorized']);
    expect(screen.getByText('invalid')).toBeTruthy();
    expect(container.querySelector('[data-dot]')).toBeNull();
  });
});

describe('skill route params', () => {
  it('pass the raw category to the page, empty for a root-level skill, and keep the formatted one for headings', () => {
    const { container } = render(<SkillsList />);
    expect([...container.querySelectorAll('h2')].map((n) => n.textContent)).toEqual(['Research', 'Uncategorized']);
    const buttons = [...container.querySelectorAll('button')];
    fireEvent.click(buttons[0]);
    fireEvent.click(buttons[2]);
    expect(h.push.mock.calls[0][0].params.category).toBe('research');
    expect(h.push.mock.calls[1][0].params.category).toBe('');
  });
});

describe('skill page', () => {
  beforeEach(() => {
    h.params = { id: 'abby', name: 'review-digest', category: 'research' };
    h.detail = { name: 'review-digest', category: 'research', status: 'invalid', reason: 'bad', body: 'body' };
  });

  it('opens on the skill banner when flagged', async () => {
    h.att = { skills: [{ name: 'review-digest', category: 'research', problem: 'lint', message: 'SKILL.md line 4' }] };
    render(<SkillDetail />);
    const banner = await screen.findByRole('alert');
    expect(banner.textContent).toBe('Does not pass lint | SKILL.md line 4. The skill is not offered to the model until it passes.');
  });

  it('matches the flag when the daemon echoes the raw route category', async () => {
    h.params = { id: 'abby', name: 'review-digest', category: 'research' };
    h.att = { skills: [{ name: 'review-digest', category: 'research', problem: 'lint', message: 'm' }] };
    render(<SkillDetail />);
    expect((await screen.findByRole('alert')).textContent).toMatch(/^Does not pass lint/);
  });

  it('matches a root-level skill whose category is empty or null', async () => {
    h.params = { id: 'abby', name: 'zeta', category: '' };
    h.att = { skills: [{ name: 'zeta', category: null, problem: 'missing', message: 'm' }] };
    render(<SkillDetail />);
    expect((await screen.findByRole('alert')).textContent).toMatch(/^Missing what it requires/);
  });

  it('shows no banner when the skill is not flagged', async () => {
    render(<SkillDetail />);
    await screen.findByText('body');
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.getByText('bad')).toBeTruthy();
  });
});

describe('memory list', () => {
  it('lifts an over-limit file into Needs you with a danger dot and the word over', () => {
    h.att = { memory: [{ file: 'MEMORY.md', used: 2400, limit: 2000, pct: 120, over: true }] };
    const { container } = render(<MemoryList />);
    expect([...container.querySelectorAll('h2')].map((n) => n.textContent)).toEqual(['Needs you · 1']);
    expect(screen.getByText('over')).toBeTruthy();
    expect(container.querySelector('[data-dot="#f00"]')).toBeTruthy();
    expect(screen.getByLabelText('Learned, MEMORY.md, over')).toBeTruthy();
    for (const b of container.querySelectorAll('button')) expect(Number(b.getAttribute('data-minheight'))).toBeGreaterThanOrEqual(44);
  });

  it('says full for a nearly full file and nothing for healthy lists', () => {
    h.att = { memory: [{ file: 'USER.md', used: 1900, limit: 2000, pct: 95, over: false }] };
    const { container, unmount } = render(<MemoryList />);
    expect(screen.getByText('full')).toBeTruthy();
    unmount();
    h.att = null;
    const again = render(<MemoryList />);
    expect(again.container.querySelector('h2')).toBeNull();
    expect(again.container.querySelector('[data-dot]')).toBeNull();
    expect(container).toBeTruthy();
  });
});

describe('memory page', () => {
  beforeEach(() => { h.params = { id: 'abby', name: 'MEMORY.md' }; });

  it('opens on the memory banner when flagged', () => {
    h.att = { memory: [{ file: 'MEMORY.md', used: 2400, limit: 2000, pct: 120, over: true }] };
    render(<MemoryDetail />);
    expect(screen.getByRole('alert').textContent).toMatch(/^Over its limit by 400 characters \| 2,400 \/ 2,000\./);
  });

  it('has no banner for a healthy file or another file\'s flag', () => {
    h.att = { memory: [{ file: 'USER.md', used: 1900, limit: 2000, pct: 95, over: false }] };
    render(<MemoryDetail />);
    expect(screen.queryByRole('alert')).toBeNull();
  });
});
