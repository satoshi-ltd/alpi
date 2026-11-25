import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({ items: [], push: vi.fn(), replace: vi.fn(), twoPane: false, status: 'online', states: new Map() }));

vi.mock('react-native', () => {
  const View = ({ children }) => React.createElement('div', {}, children);
  const Text = ({ children }) => React.createElement('span', {}, children);
  const TextInput = ({ value, onChangeText, accessibilityLabel }) =>
    React.createElement('input', { value, 'aria-label': accessibilityLabel, onChange: (e) => onChangeText(e.target.value) });
  const SectionList = ({ sections, renderItem, renderSectionHeader, ListEmptyComponent }) =>
    React.createElement('div', { 'data-testid': 'list' }, sections.length
      ? sections.map((section) => React.createElement('section', { key: section.key, 'data-section': section.key }, renderSectionHeader({ section }), ...section.data.map((item) => React.createElement('div', { key: item.id }, renderItem({ item })))))
      : ListEmptyComponent);
  return { View, Text, TextInput, SectionList };
});
vi.mock('expo-router', () => ({
  useRouter: () => ({ push: h.push, replace: h.replace }),
  usePathname: () => '/workgroups',
  useFocusEffect: () => {},
}));
vi.mock('react-native-safe-area-context', () => ({ SafeAreaView: ({ children }) => React.createElement('div', {}, children) }));
vi.mock('../../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { bg: '#fff', ink: '#000', ink3: '#666', warningText: '#b3470e' },
    fonts: { sans: { regular: 'r' } },
    fontSizes: { md: 15 },
    mobile: { inputH: 48 },
  }),
}));
vi.mock('../../components/ScreenHeader', () => ({ ScreenHeader: ({ title, subtitle }) => React.createElement('header', {}, `${title} | ${subtitle}`) }));
vi.mock('../../components/Segmented', () => ({
  Segmented: ({ options, value, onChange }) => React.createElement('div', { role: 'radiogroup' }, options.map((o) =>
    React.createElement('button', { key: o.value, type: 'button', 'aria-label': o.spoken, 'aria-checked': String(o.value === value), disabled: !!o.disabled && o.value !== value, onClick: () => onChange(o.value) }, o.label))),
}));
vi.mock('../../components/Eyebrow', () => ({ Eyebrow: ({ children, color }) => React.createElement('h3', { 'data-color': color ?? '' }, children) }));
vi.mock('../../components/Icon', () => ({ Icon: () => null }));
vi.mock('../../components/Busy', () => ({ Busy: ({ label }) => React.createElement('span', {}, label) }));
vi.mock('../../components/LoadFailed', () => ({ LoadFailed: () => React.createElement('span', {}, 'failed') }));
vi.mock('../../components/well', () => ({ useWell: () => [{}, {}] }));
vi.mock('../inbox/InboxRow', () => ({
  InboxRow: ({ item, onPress, full, offline }) => React.createElement('button', { type: 'button', 'data-row': item.id, 'data-full': String(full), 'data-offline': String(offline), onClick: () => onPress(item) }, `${item.label}: ${item.preview}`),
}));
vi.mock('../../hooks/useInbox', () => ({ useInbox: () => ({ items: h.items, loading: false, refresh: vi.fn(), error: null }) }));
vi.mock('../../hooks/useActivity', () => ({ useActivity: () => ({ states: h.states, refresh: vi.fn() }), rowStateFor: (states, item) => states.get(item.id) ?? null }));
vi.mock('../../lib/EndpointContext', () => ({ useEndpoint: () => ({ endpoint: { id: 'c1' }, probeState: new Map([['c1', h.status]]) }) }));
vi.mock('../../components/DaemonBanner', () => ({ isDaemonDown: (status) => status === 'offline' }));
vi.mock('../../hooks/useBack', () => ({ useBack: () => vi.fn() }));
vi.mock('../../hooks/usePullRefresh', () => ({ usePullRefresh: () => ({ refreshing: false, onRefresh: vi.fn() }) }));
vi.mock('../../nav/PaneContext', () => ({ usePane: () => ({ twoPane: h.twoPane }) }));

import WorkgroupsScreen from '../../../app/workgroups.jsx';

const wg = (id, stateId, preview, sortKey) => ({ kind: 'workgroup', id, profile: 'mira', label: id, preview, stateId, sortKey, raw: {} });

describe('Workgroups page', () => {
  it('counts the whole set on the filter, groups All by state and opens a row', () => {
    h.items = [wg('idle-a', 'idle', 'last run done', 3), wg('build', 'active', 'Working · build', 2), wg('ship', 'needs', 'Needs you', 1), { kind: 'profile', id: 'doc', label: 'doc' }];
    render(<WorkgroupsScreen />);
    expect(screen.getByText('Workgroups | 3 · 2 working')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'All, 3' }).getAttribute('aria-checked')).toBe('true');
    expect(screen.getByRole('button', { name: 'Queued, 0' }).disabled).toBe(true);
    expect([...document.querySelectorAll('h3')].map((el) => el.textContent)).toEqual(['Needs you · 1', 'Working · 1', 'Idle · 1']);
    expect(document.querySelector('h3').getAttribute('data-color')).toBe('#b3470e');
    expect([...document.querySelectorAll('[data-row]')].map((el) => el.getAttribute('data-full'))).toEqual(['true', 'true', 'true']);
    fireEvent.click(screen.getByText('build: Working · build'));
    expect(h.push).toHaveBeenCalledWith('/wg/build');
  });

  it('filters to one unlabelled list and answers an empty search with one line', () => {
    h.items = [wg('idle-a', 'idle', 'x', 3), wg('build', 'active', 'Working', 2)];
    render(<WorkgroupsScreen />);
    fireEvent.click(screen.getByRole('button', { name: 'Working, 1' }));
    expect(document.querySelectorAll('h3')).toHaveLength(0);
    expect([...document.querySelectorAll('[data-row]')].map((el) => el.getAttribute('data-row'))).toEqual(['build']);
    fireEvent.change(screen.getByLabelText('Search workgroups'), { target: { value: 'deploy' } });
    expect(screen.getByText('No working workgroup matches deploy.')).toBeTruthy();
  });
});

describe('Workgroups page, live state', () => {
  it('files a workgroup the activity feed sees working under Working, and dims rows while the daemon is away', () => {
    h.items = [wg('quiet', 'idle', 'last run done', 3), wg('long', 'idle', 'last run done', 1)];
    h.states = new Map([['long', { state: 'working' }]]);
    h.status = 'offline';
    render(<WorkgroupsScreen />);
    expect(screen.getByRole('button', { name: 'Working, 1' })).toBeTruthy();
    expect([...document.querySelectorAll('h3')].map((el) => el.textContent)).toEqual(['Working · 1', 'Idle · 1']);
    expect([...document.querySelectorAll('[data-row]')].map((el) => el.getAttribute('data-offline'))).toEqual(['true', 'true']);
    h.states = new Map();
    h.status = 'online';
  });

  it('replaces the detail pane when a row opens on a fold', () => {
    h.items = [wg('build', 'active', 'Working', 2)];
    h.twoPane = true;
    render(<WorkgroupsScreen />);
    fireEvent.click(screen.getByText('build: Working'));
    expect(h.replace).toHaveBeenCalledWith('/wg/build');
    h.twoPane = false;
  });
});
