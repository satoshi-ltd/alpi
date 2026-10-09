import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  att: null,
  skills: { data: { skills: [] }, refresh: () => {} },
  mem: { data: {}, usage: {}, refresh: () => {} },
  editor: { loading: false, raw: '', editing: false, canEdit: false, dirty: false },
  detail: null,
  params: { id: 'abby' },
  push: vi.fn(),
  alert: vi.fn(),
  editorArgs: [],
}));

vi.mock('react-native', () => {
  const R = require('react');
  const Pressable = ({ children, accessibilityLabel, accessibilityState, style, onPress }) =>
    R.createElement('button', { onClick: onPress, 'aria-label': accessibilityLabel, 'data-selected': String(!!accessibilityState?.selected), 'data-minheight': (typeof style === 'function' ? style({ pressed: false }) : style)?.minHeight }, typeof children === 'function' ? children({ pressed: false }) : children);
  const View = ({ children, accessibilityRole }) => R.createElement('div', { role: accessibilityRole }, children);
  return {
    View, Pressable,
    Text: ({ children }) => R.createElement('span', {}, children),
    ScrollView: ({ children }) => R.createElement('div', {}, children),
    RefreshControl: () => null,
    TextInput: () => React.createElement('textarea', { 'data-editor': 'true' }),
    Alert: { alert: (...args) => h.alert(...args) },
    StyleSheet: { create: (s) => s },
    useWindowDimensions: () => ({ width: 390, height: 844 }),
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
vi.mock('../src/components/KeyboardPane', () => ({ KeyboardPane: ({ children }) => React.createElement('section', { 'data-keyboard-pane': 'true' }, children) }));
vi.mock('../src/hooks/useMemoryEditor', () => ({ useMemoryEditor: (id, name) => { h.editorArgs.push(name); return h.editor; } }));
vi.mock('../src/hooks/useMasterDetail', () => ({ useMasterDetail: () => globalThis.__wide === true }));
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

  it('rides the keyboard while editing so the lower half of the text stays visible', () => {
    h.att = null;
    h.editor = { loading: false, raw: 'x', draft: 'x', setDraft: () => {}, editing: true, canEdit: true, dirty: false, startEdit: () => {}, loadError: null };
    const { container } = render(<MemoryDetail />);
    const pane = container.querySelector('[data-keyboard-pane]');
    expect(pane).toBeTruthy();
    expect(pane.querySelector('textarea')).toBeTruthy();
  });
});

describe('memory page beside the list', () => {
  const rowFor = (file) => screen.getByLabelText(new RegExp(`${file.replace('.', '\\.')}`));

  beforeEach(() => {
    globalThis.__wide = true;
    h.params = { id: 'abby' };
    h.att = null;
    h.alert.mockClear();
    h.editorArgs.length = 0;
    h.editor = { loading: false, raw: 'x', draft: 'x', setDraft: () => {}, editing: false, canEdit: true, dirty: false, startEdit: () => {}, loadError: null };
  });

  afterEach(() => { globalThis.__wide = false; });

  it('opens the first file on arrival and marks its row selected', () => {
    render(<MemoryList />);
    expect(h.editorArgs.at(-1)).toBe('AGENT.md');
    expect(rowFor('AGENT.md').getAttribute('data-selected')).toBe('true');
    expect(h.push).not.toHaveBeenCalled();
  });

  it('shows another file beside the list when its row is tapped', () => {
    render(<MemoryList />);
    fireEvent.click(rowFor('MEMORY.md'));
    expect(h.editorArgs.at(-1)).toBe('MEMORY.md');
    expect(h.push).not.toHaveBeenCalled();
  });

  it('asks before an unsaved edit is replaced by another file, and keeps it on Keep editing', () => {
    h.editor = { ...h.editor, editing: true, dirty: true };
    render(<MemoryList />);
    fireEvent.click(rowFor('USER.md'));
    expect(h.alert).toHaveBeenCalledTimes(1);
    expect(h.editorArgs.at(-1)).toBe('AGENT.md');
    const buttons = h.alert.mock.calls[0][2];
    expect(buttons.map((b) => b.text)).toEqual(['Keep editing', 'Discard']);
  });

  it('switches once the edit is discarded', () => {
    h.editor = { ...h.editor, editing: true, dirty: true };
    render(<MemoryList />);
    fireEvent.click(rowFor('USER.md'));
    act(() => { h.alert.mock.calls[0][2][1].onPress(); });
    expect(h.editorArgs.at(-1)).toBe('USER.md');
  });

  it('pushes the page on a narrow pane as before', () => {
    globalThis.__wide = false;
    render(<MemoryList />);
    fireEvent.click(rowFor('USER.md'));
    expect(h.push).toHaveBeenCalledWith({ pathname: '/profile/abby/brain/memory/[name]', params: { name: 'USER.md' } });
  });

  it('keeps an unsaved edit on screen when the pane narrows instead of dropping it, and returns to the list once it is done', () => {
    h.editor = { ...h.editor, editing: true, dirty: true };
    const { rerender } = render(<MemoryList />);
    expect(document.querySelector('textarea')).toBeTruthy();
    globalThis.__wide = false;
    rerender(<MemoryList />);
    expect(document.querySelector('textarea')).toBeTruthy();
    h.editor = { ...h.editor, editing: false, dirty: false };
    rerender(<MemoryList />);
    expect(document.querySelector('textarea')).toBeNull();
  });

  it('refreshes the list after a save so counts and meters are not stale', async () => {
    h.mem = { ...h.mem, refresh: vi.fn() };
    h.editor = { ...h.editor, editing: true, dirty: true, save: vi.fn(async () => ({ ok: true })) };
    render(<MemoryList />);
    h.mem.refresh.mockClear();
    await act(async () => { fireEvent.click(screen.getByLabelText('Save')); });
    expect(h.editor.save).toHaveBeenCalledTimes(1);
    expect(h.mem.refresh).toHaveBeenCalled();
  });
});
