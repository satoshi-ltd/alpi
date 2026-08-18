import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  pathname: '/',
  push: vi.fn(),
  replace: vi.fn(),
  refresh: vi.fn(async () => {}),
  toast: vi.fn(),
  items: [],
  pinnedProfiles: [],
  role: 'admin',
  endpoint: { id: 'c1', name: 'casa', url: 'ws://casa:49200' },
  list: null,
  unread: 0,
  bgOf: (style) => [style].flat(Infinity).filter(Boolean).reduce((bg, s) => s.backgroundColor ?? bg, null),
  posOf: (style) => [style].flat(Infinity).filter(Boolean).reduce((pos, s) => s.position ?? pos, null),
}));

vi.mock('react-native', () => {
  const View = ({ children, style, accessibilityLabel, ...p }) =>
    React.createElement(
      'div',
      {
        ...p,
        ...(accessibilityLabel ? { 'aria-label': accessibilityLabel } : {}),
        ...(h.posOf(style) ? { 'data-pos': h.posOf(style) } : {}),
      },
      children,
    );
  const Text = ({ children, style, numberOfLines, ...p }) => React.createElement('span', p, children);
  const Pressable = ({ children, style, onPress, onLongPress, android_ripple, hitSlop, accessibilityLabel, ...p }) =>
    React.createElement(
      'button',
      {
        type: 'button',
        onClick: onPress,
        onContextMenu: onLongPress,
        'aria-label': accessibilityLabel,
        'data-bg': h.bgOf(typeof style === 'function' ? style({ pressed: false }) : style),
        ...p,
      },
      typeof children === 'function' ? children({ pressed: false }) : children,
    );
  const TextInput = ({ value, onChangeText, accessibilityLabel, style, ...p }) =>
    React.createElement('input', {
      value,
      onChange: (e) => onChangeText?.(e.target.value),
      'aria-label': accessibilityLabel,
    });
  const SectionList = (props) => {
    h.list = props;
    const { sections = [], renderItem, renderSectionHeader, keyExtractor, ListEmptyComponent } = props;
    const empty = typeof ListEmptyComponent === 'function' ? React.createElement(ListEmptyComponent) : ListEmptyComponent;
    const rows = sections.flatMap((section) => [
      React.createElement('div', { key: `h-${section.key}` }, renderSectionHeader?.({ section })),
      ...section.data.map((item, index) =>
        React.createElement(
          'div',
          { key: keyExtractor(item, index), 'data-item': keyExtractor(item, index) },
          renderItem({ item, index, section }),
        )),
    ]);
    return React.createElement('div', { 'data-testid': 'list' }, rows.length ? rows : empty);
  };
  return {
    View,
    Text,
    Pressable,
    TextInput,
    SectionList,
    ActivityIndicator: () => React.createElement('span', { 'data-testid': 'spinner' }),
    RefreshControl: () => null,
    AppState: { addEventListener: () => ({ remove: () => {} }) },
    Keyboard: { addListener: () => ({ remove: () => {} }) },
    StyleSheet: { create: (s) => s },
  };
});

vi.mock('expo-router', () => ({
  usePathname: () => h.pathname,
  useRouter: () => ({ push: h.push, replace: h.replace }),
}));

vi.mock('react-native-safe-area-context', () => ({
  SafeAreaView: ({ children }) => React.createElement('div', {}, children),
}));

vi.mock('../../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: {
      bg: '#fff', bgPane: '#fff', bgSide: '#f5f6f8', bgInput: '#f1f3f5',
      line: '#eee', line2: '#ddd', selected: '#eaeaea', hover: '#f4f4f4',
      ink: '#000', ink2: '#333', ink3: '#666', ink4: '#999', accent: '#c90', danger: '#c00',
    },
    fonts: {
      sans: { regular: 'r', medium: 'm', semibold: 's', bold: 'b' },
      mono: 'mono', monoMedium: 'monoMedium', monoSemibold: 'monoSemibold',
    },
    fontSizes: { xxs: 9, xs: 11, sm: 12, md: 14, lg: 15 },
    alpha: { muted: 0.55 },
    mobile: { inputH: 44 },
  }),
}));

vi.mock('../../components/Banner', () => ({ Banner: ({ children }) => React.createElement('div', {}, children) }));
vi.mock('../../components/Icon', () => ({ Icon: ({ name }) => React.createElement('span', { 'data-icon': name }) }));
vi.mock('../../components/Glyph', () => ({ Glyph: () => React.createElement('span', { 'data-glyph': 'true' }) }));
vi.mock('../../components/Dot', () => ({ Dot: () => React.createElement('span', { 'data-dot': 'true' }) }));
vi.mock('react-native-gesture-handler', () => ({
  GestureDetector: ({ children }) => React.createElement('div', { 'data-gesture': 'true' }, children),
}));

vi.mock('../inbox/ConnHeader', () => ({
  ConnHeader: ({ name, host, onBellPress, onGearPress, searchOpen, onToggleSearch }) =>
    React.createElement(
      'div',
      { 'data-conn': name, 'data-host': host },
      onBellPress ? React.createElement('button', { type: 'button', 'aria-label': 'Header bell' }) : null,
      onGearPress ? React.createElement('button', { type: 'button', 'aria-label': 'Header gear' }) : null,
      onToggleSearch
        ? React.createElement('button', {
            type: 'button',
            onClick: onToggleSearch,
            'aria-label': searchOpen ? 'Close filter' : 'Filter profiles and workgroups',
          })
        : null,
    ),
}));
vi.mock('../inbox/InboxSkeleton', () => ({ InboxSkeleton: () => React.createElement('div', { 'data-testid': 'skeleton' }) }));
vi.mock('expo-constants', () => ({ default: { expoConfig: { version: '0.3.1' } } }));
vi.mock('../inbox/Pip', () => ({
  Pip: ({ kind, count }) => React.createElement('span', { 'data-pip': kind, 'data-count': String(count ?? '') }),
}));
vi.mock('../inbox/RowContextSheet', () => ({
  RowContextSheet: ({ target }) => (target ? React.createElement('div', { 'data-ctx': target.id }) : null),
}));
vi.mock('../sheets/ConnectionSheet', () => ({ ConnectionSheet: () => null }));
vi.mock('../sheets/CreateProfileSheet', () => ({
  CreateProfileSheet: ({ open }) => (open ? React.createElement('div', { 'data-create': 'profile' }) : null),
}));
vi.mock('../sheets/CreateWorkgroupSheet', () => ({
  CreateWorkgroupSheet: ({ open }) => (open ? React.createElement('div', { 'data-create': 'workgroup' }) : null),
}));

vi.mock('../../components/Toast', () => ({ useToast: () => h.toast }));
vi.mock('../../hooks/useDebouncedCallback', () => ({ useDebouncedCallback: (fn) => fn }));
vi.mock('../../hooks/useEvents', () => ({ useEventEffect: () => {} }));
vi.mock('../../hooks/useInbox', () => ({ useInbox: () => ({ items: h.items, loading: false, refresh: h.refresh }) }));
vi.mock('../../hooks/useUnifiedOutputs', () => ({
  useUnifiedOutputs: () => ({ rows: Array.from({ length: h.unread }, (_, i) => ({ id: `o${i}` })) }),
}));
vi.mock('../../lib/EndpointContext', () => ({
  useEndpoint: () => ({ endpoint: h.endpoint, probeState: new Map([['c1', 'online']]), activeRole: h.role }),
}));
vi.mock('../../lib/pins', () => ({
  usePins: () => ({
    isProfilePinned: (name) => h.pinnedProfiles.includes(name),
    isWorkgroupPinned: () => false,
    toggleProfile: () => {},
    toggleWorkgroup: () => {},
  }),
}));


import { InboxRow } from '../inbox/InboxRow';
import { SidebarPane } from './SidebarPane';

const ITEMS = [
  { kind: 'profile', id: 'doc', name: 'doc', label: 'doc', preview: 'hi', ts: '2m' },
  { kind: 'profile', id: 'agora', name: 'agora', label: 'agora', preview: 'ok', ts: '5m' },
  { kind: 'workgroup', id: 'alpha', profile: 'doc', name: 'alpha', label: 'alpha', preview: 'go', ts: '1h', state: 'working' },
];

function row(label) {
  return screen.getByText(label).closest('button');
}

function itemRow(key) {
  return document.querySelector(`[data-item="${key}"]`).querySelector('button');
}

function header(label) {
  return screen.getByText(label).closest('div');
}

function openFilter() {
  fireEvent.click(screen.getByLabelText('Filter profiles and workgroups'));
}

function filter() {
  if (!screen.queryByLabelText('Filter list')) openFilter();
  return screen.getByLabelText('Filter list');
}

function type(value) {
  fireEvent.change(filter(), { target: { value } });
}

beforeEach(() => {
  h.pathname = '/';
  h.items = ITEMS;
  h.pinnedProfiles = [];
  h.role = 'admin';
  h.endpoint = { id: 'c1', name: 'casa', url: 'ws://casa:49200' };
  h.list = null;
  h.unread = 0;
  h.push.mockClear();
  h.replace.mockClear();
  h.toast.mockClear();
});

function settingsEntry() {
  return screen.getByLabelText('Settings');
}

function bellEntry() {
  return screen.getByLabelText(h.unread > 0 ? `Notifications · ${h.unread} unread` : 'Notifications');
}

describe('SidebarPane launch', () => {
  it('routes nowhere on its own — the pane root owns where a launch lands', () => {
    render(<SidebarPane />);
    expect(h.replace).not.toHaveBeenCalled();
    expect(h.push).not.toHaveBeenCalled();
  });

  it('routes nowhere when the roster lands after the first paint either', () => {
    h.items = [];
    const { rerender } = render(<SidebarPane />);
    h.items = ITEMS;
    rerender(<SidebarPane />);
    expect(h.replace).not.toHaveBeenCalled();
    expect(h.push).not.toHaveBeenCalled();
  });

  it('leaves a shell route the user is on alone when the roster lands', () => {
    h.pathname = '/settings';
    h.items = [];
    const { rerender } = render(<SidebarPane />);
    h.items = ITEMS;
    rerender(<SidebarPane />);
    expect(h.replace).not.toHaveBeenCalled();
    expect(h.push).not.toHaveBeenCalled();
  });
});

describe('SidebarPane connection identity', () => {
  it('shows a legacy ip/port connection as its address instead of claiming it is unpaired', () => {
    h.endpoint = { id: 'c1', name: 'casa', ip: '100.99.29.84', port: 49200 };
    render(<SidebarPane />);
    expect(document.querySelector('[data-conn]').getAttribute('data-host')).toBe('ws://100.99.29.84:49200');
  });

  it('says not paired only when there is no connection at all', () => {
    h.endpoint = null;
    render(<SidebarPane />);
    expect(document.querySelector('[data-conn]').getAttribute('data-host')).toBe('not paired');
  });

  it('survives a stored address it cannot parse, still without claiming a host', () => {
    h.endpoint = { id: 'c1', name: 'casa', url: 'not-a-url' };
    render(<SidebarPane />);
    expect(document.querySelector('[data-conn]').getAttribute('data-host')).toBe('not paired');
  });
});

describe('SidebarPane selection', () => {
  it('lights the row that sidebarSelection(pathname) points at', () => {
    h.pathname = '/chat/agora';
    render(<SidebarPane />);
    expect(row('agora').getAttribute('data-bg')).toBe('#eaeaea');
    expect(row('doc').getAttribute('data-bg')).toBe('transparent');
    expect(row('alpha').getAttribute('data-bg')).toBe('transparent');
  });

  it('lights the workgroup row on a workgroup path, never a same-named profile', () => {
    h.pathname = '/wg/alpha';
    h.items = [...ITEMS, { kind: 'profile', id: 'alpha', name: 'alpha', label: 'alpha', preview: 'p', ts: '3m' }];
    render(<SidebarPane />);
    expect(itemRow('workgroup:doc/alpha').getAttribute('data-bg')).toBe('#eaeaea');
    expect(itemRow('profile:alpha').getAttribute('data-bg')).toBe('transparent');
  });

  it('keeps the row lit while a drilled screen of that subject is open', () => {
    h.pathname = '/profile/doc/settings';
    render(<SidebarPane />);
    expect(row('doc').getAttribute('data-bg')).toBe('#eaeaea');
  });

  it('lights nothing on a list-only path', () => {
    render(<SidebarPane />);
    for (const label of ['doc', 'agora', 'alpha']) {
      expect(row(label).getAttribute('data-bg')).toBe('transparent');
    }
  });
});

describe('SidebarPane filter', () => {
  it('narrows the list to matching rows as you type', () => {
    render(<SidebarPane />);
    expect(screen.getByText('doc')).toBeTruthy();
    type('ag');
    expect(screen.getByText('agora')).toBeTruthy();
    expect(screen.queryByText('doc')).toBeNull();
    expect(screen.queryByText('alpha')).toBeNull();
  });

  it('ignores a leading @ or # so a typed mention still matches', () => {
    render(<SidebarPane />);
    type('#alph');
    expect(screen.getByText('alpha')).toBeTruthy();
    expect(screen.queryByText('agora')).toBeNull();
    type('@ago');
    expect(screen.getByText('agora')).toBeTruthy();
    expect(screen.queryByText('alpha')).toBeNull();
  });

  it('says nothing matched instead of claiming an empty inbox', () => {
    render(<SidebarPane />);
    type('zzz');
    expect(screen.getByText('No matches')).toBeTruthy();
    expect(screen.getByText('Nothing matches “zzz”.')).toBeTruthy();
    expect(screen.queryByText('Empty inbox.')).toBeNull();
  });

  it('restores the whole list when the field is closed, leaving no hidden filter', () => {
    render(<SidebarPane />);
    type('ag');
    expect(screen.queryByText('doc')).toBeNull();
    fireEvent.click(screen.getByLabelText('Close filter'));
    expect(screen.queryByLabelText('Filter list')).toBeNull();
    expect(screen.getByText('doc')).toBeTruthy();
    expect(screen.getByText('alpha')).toBeTruthy();
    expect(filter().value).toBe('');
  });
});

describe('SidebarPane open verb', () => {
  it('replaces the detail pane at a pane root', () => {
    render(<SidebarPane />);
    fireEvent.click(row('doc'));
    expect(h.replace).toHaveBeenCalledWith('/chat/doc');
    expect(h.push).not.toHaveBeenCalled();
  });

  it('replaces when another subject already owns the detail pane', () => {
    h.pathname = '/chat/agora';
    render(<SidebarPane />);
    fireEvent.click(row('alpha'));
    expect(h.replace).toHaveBeenCalledWith('/wg/alpha');
    expect(h.push).not.toHaveBeenCalled();
  });

  it('pushes from a drilled screen so its back stack survives', () => {
    h.pathname = '/wg/alpha/settings';
    render(<SidebarPane />);
    fireEvent.click(row('doc'));
    expect(h.push).toHaveBeenCalledWith('/chat/doc');
    expect(h.replace).not.toHaveBeenCalled();
  });
});

describe('SidebarPane rows', () => {
  it('wraps no row in a swipe container — long-press owns row actions on both surfaces', () => {
    const { container } = render(<SidebarPane />);
    expect(container.querySelector('[data-gesture]')).toBeNull();
    expect(row('doc').parentElement.getAttribute('data-item')).toBe('profile:doc');
  });

  it('opens the row context sheet on long-press', () => {
    render(<SidebarPane />);
    fireEvent.contextMenu(row('doc'));
    expect(document.querySelector('[data-ctx]').getAttribute('data-ctx')).toBe('doc');
  });

  it('sizes no row itself — section headers make the heights non-uniform', () => {
    render(<SidebarPane />);
    expect(h.list.getItemLayout).toBeUndefined();
  });

  it('shows the working state useInbox derives from wg activity as a pip in the row meta', () => {
    render(<SidebarPane />);
    expect(row('alpha').querySelector('[data-pip="working"]')).toBeTruthy();
    expect(screen.getByLabelText('alpha working')).toBeTruthy();
    expect(row('doc').querySelector('[data-pip]')).toBeNull();
    expect(row('agora').querySelector('[data-pip]')).toBeNull();
  });

  it('leaves the phone row untouched — no pip, and unread carries no mark either', () => {
    const { container } = render(<InboxRow item={{ ...ITEMS[2], unread: true }} />);
    expect(container.querySelector('[data-pip]')).toBeNull();
    expect(container.querySelector('[data-dot]')).toBeNull();
  });
});

describe('SidebarPane creation', () => {
  it('floats no compose button — creation lives on the headings', () => {
    render(<SidebarPane />);
    expect(screen.queryByLabelText('Compose')).toBeNull();
  });

  it('gives an admin a + on the profiles and workgroups headings only', () => {
    h.pinnedProfiles = ['doc'];
    render(<SidebarPane />);
    expect(header('PROFILES').querySelector('[aria-label="New profile"]')).toBeTruthy();
    expect(header('WORKGROUPS').querySelector('[aria-label="New workgroup"]')).toBeTruthy();
    expect(header('PINNED').querySelector('button')).toBeNull();
  });

  it('gives a non-admin no + at all', () => {
    h.role = 'member';
    render(<SidebarPane />);
    expect(screen.queryByLabelText('New profile')).toBeNull();
    expect(screen.queryByLabelText('New workgroup')).toBeNull();
  });

  it('opens the create sheet from each + and never navigates to a create route', () => {
    render(<SidebarPane />);
    h.push.mockClear();
    h.replace.mockClear();
    fireEvent.click(screen.getByLabelText('New profile'));
    expect(document.querySelector('[data-create="profile"]')).toBeTruthy();

    fireEvent.click(screen.getByLabelText('New workgroup'));
    expect(document.querySelector('[data-create="workgroup"]')).toBeTruthy();
    expect(document.querySelector('[data-create="profile"]')).toBeNull();

    expect(h.push).not.toHaveBeenCalled();
    expect(h.replace).not.toHaveBeenCalled();
  });

  it('mounts no create sheet for a non-admin', () => {
    h.role = 'member';
    render(<SidebarPane />);
    expect(document.querySelector('[data-create]')).toBeNull();
  });

  it('offers no + while the role probe is still out', () => {
    h.role = null;
    render(<SidebarPane />);
    expect(screen.queryByLabelText('New profile')).toBeNull();
    expect(screen.queryByLabelText('New workgroup')).toBeNull();
    expect(document.querySelector('[data-create]')).toBeNull();
  });

  it('grows the + once the probe confirms the device is an admin', () => {
    h.role = null;
    const { rerender } = render(<SidebarPane />);
    h.role = 'admin';
    rerender(<SidebarPane />);
    expect(screen.getByLabelText('New profile')).toBeTruthy();
    expect(h.toast).not.toHaveBeenCalled();
  });

  it('takes back an open create form when the daemon demotes the device, and says why', () => {
    const { rerender } = render(<SidebarPane />);
    fireEvent.click(screen.getByLabelText('New profile'));
    expect(document.querySelector('[data-create="profile"]')).toBeTruthy();

    h.role = 'member';
    rerender(<SidebarPane />);
    expect(document.querySelector('[data-create]')).toBeNull();
    expect(h.toast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Admin only' }));
  });

  it('leaves the create form alone while the device is still an admin', () => {
    const { rerender } = render(<SidebarPane />);
    fireEvent.click(screen.getByLabelText('New workgroup'));
    rerender(<SidebarPane />);
    expect(document.querySelector('[data-create="workgroup"]')).toBeTruthy();
    expect(h.toast).not.toHaveBeenCalled();
  });
});

describe('SidebarPane footer', () => {
  it('puts Settings before the bell, like desktop', () => {
    render(<SidebarPane />);
    const order = settingsEntry().compareDocumentPosition(bellEntry());
    expect(order & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('keeps the version on the trailing edge after the spacer', () => {
    render(<SidebarPane />);
    const version = screen.getByText('v0.3.1');
    expect(bellEntry().compareDocumentPosition(version) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('overlays the unread count on the bell glyph instead of setting it beside it', () => {
    h.unread = 7;
    render(<SidebarPane />);
    const wrap = bellEntry().querySelector('[data-pos="relative"]');
    expect(wrap.querySelector('[data-icon="bell"]')).toBeTruthy();
    const badge = wrap.querySelector('[data-pos="absolute"]');
    expect(badge.textContent).toBe('7');
  });

  it('caps the badge at 99+', () => {
    h.unread = 150;
    render(<SidebarPane />);
    expect(bellEntry().querySelector('[data-pos="absolute"]').textContent).toBe('99+');
  });

  it('draws no badge at zero unread', () => {
    render(<SidebarPane />);
    expect(bellEntry().querySelector('[data-pos="absolute"]')).toBeNull();
  });

  it('cycles no theme — the tablet keeps theme as a labelled row in Settings', () => {
    render(<SidebarPane />);
    expect(screen.queryByLabelText('Theme')).toBeNull();
    expect(document.querySelector('[data-icon="sun"]')).toBeNull();
    expect(document.querySelector('[data-icon="moon"]')).toBeNull();
  });

  it('hides the bell from a non-admin and keeps Settings', () => {
    h.role = 'member';
    render(<SidebarPane />);
    expect(screen.queryByLabelText('Notifications')).toBeNull();
    expect(settingsEntry()).toBeTruthy();
  });
});

describe('SidebarPane pane and overlay registers', () => {
  it('sends notifications to the detail pane, replacing what the pane held', () => {
    h.pathname = '/chat/agora';
    render(<SidebarPane />);
    fireEvent.click(bellEntry());
    expect(h.replace).toHaveBeenCalledWith('/outputs');
    expect(h.push).not.toHaveBeenCalled();
    expect(document.querySelector('[data-sheet]')).toBeNull();
  });

  it('pushes notifications from a drilled screen so its back stack survives', () => {
    h.pathname = '/wg/alpha/settings';
    render(<SidebarPane />);
    fireEvent.click(bellEntry());
    expect(h.push).toHaveBeenCalledWith('/outputs');
    expect(h.replace).not.toHaveBeenCalled();
  });

  it('sends settings to the detail pane, replacing what the pane held', () => {
    h.pathname = '/chat/agora';
    render(<SidebarPane />);
    fireEvent.click(settingsEntry());
    expect(h.replace).toHaveBeenCalledWith('/settings');
  });

  it('pushes settings from a drilled screen so its back stack survives', () => {
    h.pathname = '/wg/alpha/settings';
    render(<SidebarPane />);
    fireEvent.click(settingsEntry());
    expect(h.push).toHaveBeenCalledWith('/settings');
    expect(h.replace).not.toHaveBeenCalled();
  });

  it('hands the header no bell and no gear — the footer is the only way in', () => {
    render(<SidebarPane />);
    expect(screen.queryByLabelText('Header bell')).toBeNull();
    expect(screen.queryByLabelText('Header gear')).toBeNull();
    expect(settingsEntry()).toBeTruthy();
  });

  it('sends a member to the settings route too — it is personal, not admin', () => {
    h.role = 'member';
    render(<SidebarPane />);
    fireEvent.click(settingsEntry());
    expect(h.replace).toHaveBeenCalledWith('/settings');
  });

  it('routes both shell entries through the detail pane, stacking no overlay', () => {
    render(<SidebarPane />);
    h.replace.mockClear();
    fireEvent.click(bellEntry());
    fireEvent.click(settingsEntry());
    expect(document.querySelector('[data-sheet]')).toBeNull();
    expect(h.replace.mock.calls).toEqual([['/outputs'], ['/settings']]);
  });
});
