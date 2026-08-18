import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
  refresh: vi.fn(async () => {}),
  toggleProfile: vi.fn(),
  toast: vi.fn(),
  items: [],
  pinnedProfiles: [],
  role: 'admin',
  endpoint: { id: 'c1', name: 'casa', url: 'ws://casa:49200' },
  pathname: '/',
  unread: 0,
  edges: [],
  list: null,
}));

vi.mock('react-native', () => {
  const View = ({ children, style, accessibilityLabel, ...p }) =>
    React.createElement('div', { ...p, ...(accessibilityLabel ? { 'aria-label': accessibilityLabel } : {}) }, children);
  const Text = ({ children, style, numberOfLines, ...p }) => React.createElement('span', p, children);
  const Pressable = ({ children, style, onPress, onLongPress, android_ripple, hitSlop, accessibilityLabel, ...p }) =>
    React.createElement(
      'button',
      { type: 'button', onClick: onPress, onContextMenu: onLongPress, 'aria-label': accessibilityLabel, ...p },
      typeof children === 'function' ? children({ pressed: false }) : children,
    );
  const TextInput = ({ value, onChangeText, accessibilityLabel }) =>
    React.createElement('input', {
      value,
      onChange: (e) => onChangeText?.(e.target.value),
      'aria-label': accessibilityLabel,
    });
  const SectionList = (props) => {
    h.list = props;
    const { sections = [], renderItem, renderSectionHeader, keyExtractor, ListEmptyComponent, ListFooterComponent } = props;
    const el = (c) => (typeof c === 'function' ? React.createElement(c) : c);
    const rows = sections.flatMap((section) => [
      React.createElement('div', { key: `h-${section.key}` }, renderSectionHeader?.({ section })),
      ...section.data.map((item, index) =>
        React.createElement(
          'div',
          { key: keyExtractor(item, index), 'data-item': keyExtractor(item, index) },
          renderItem({ item, index, section }),
        )),
    ]);
    return React.createElement(
      'div',
      { 'data-testid': 'list' },
      rows.length ? rows : el(ListEmptyComponent),
      el(ListFooterComponent),
    );
  };
  return {
    View,
    Text,
    Pressable,
    TextInput,
    SectionList,
    ActivityIndicator: () => React.createElement('span', { 'data-testid': 'spinner' }),
    RefreshControl: () => null,
    Keyboard: { addListener: () => ({ remove: () => {} }) },
    StyleSheet: { create: (s) => s },
  };
});

vi.mock('expo-router', () => ({
  useRouter: () => ({ push: h.push, replace: h.replace }),
  usePathname: () => h.pathname,
  useFocusEffect: (cb) => React.useEffect(() => cb(), [cb]),
}));

vi.mock('react-native-safe-area-context', () => ({
  SafeAreaView: ({ children, edges }) => {
    h.edges = edges ?? [];
    return React.createElement('div', {}, children);
  },
}));

vi.mock('expo-constants', () => ({ default: { expoConfig: { version: '0.3.1' } } }));

vi.mock('react-native-gesture-handler', () => ({
  GestureDetector: ({ children }) => React.createElement('div', { 'data-gesture': 'true' }, children),
}));

vi.mock('../src/theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: {
      bg: '#fff', bgPane: '#fff', bgInput: '#f1f3f5', line: '#eee', line2: '#ddd',
      selected: '#eaeaea', hover: '#f4f4f4',
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

vi.mock('../src/components/ActionSheet', () => ({
  ActionSheet: ({ open, title, actions = [] }) =>
    open
      ? React.createElement(
          'div',
          { 'data-sheet': title },
          actions.map((a) =>
            React.createElement(
              'button',
              { key: a.id, type: 'button', onClick: a.onPress },
              React.createElement('span', { key: 'icon' }, a.icon),
              a.label,
            )),
        )
      : null,
}));
vi.mock('../src/components/Banner', () => ({ Banner: ({ children }) => React.createElement('div', {}, children) }));
vi.mock('../src/components/Icon', () => ({ Icon: ({ name }) => React.createElement('span', { 'data-icon': name }) }));
vi.mock('../src/components/Glyph', () => ({ Glyph: () => React.createElement('span', { 'data-glyph': 'true' }) }));
vi.mock('../src/components/Dot', () => ({ Dot: () => React.createElement('span', { 'data-dot': 'true' }) }));
vi.mock('../src/features/inbox/ConnHeader', () => ({
  ConnHeader: ({ name, host, onBellPress, onGearPress }) =>
    React.createElement(
      'div',
      { 'data-conn': name, 'data-host': host },
      onBellPress ? React.createElement('button', { type: 'button', 'aria-label': 'Header bell' }) : null,
      onGearPress ? React.createElement('button', { type: 'button', 'aria-label': 'Header gear' }) : null,
    ),
}));
vi.mock('../src/features/inbox/InboxSkeleton', () => ({
  InboxSkeleton: () => React.createElement('div', { 'data-testid': 'skeleton' }),
}));
vi.mock('../src/features/inbox/Pip', () => ({ Pip: ({ kind }) => React.createElement('span', { 'data-pip': kind }) }));
vi.mock('../src/features/sheets/ConnectionSheet', () => ({ ConnectionSheet: () => null }));
vi.mock('../src/features/sheets/CreateProfileSheet', () => ({
  CreateProfileSheet: ({ open }) => (open ? React.createElement('div', { 'data-create': 'profile' }) : null),
}));
vi.mock('../src/features/sheets/CreateWorkgroupSheet', () => ({
  CreateWorkgroupSheet: ({ open }) => (open ? React.createElement('div', { 'data-create': 'workgroup' }) : null),
}));
vi.mock('../src/features/shell/HomePane', () => ({ HomePane: () => React.createElement('div', { 'data-home': 'true' }) }));

vi.mock('../src/components/Toast', () => ({ useToast: () => h.toast }));
vi.mock('../src/hooks/useDebouncedCallback', () => ({ useDebouncedCallback: (fn) => fn }));
vi.mock('../src/hooks/useEvents', () => ({ useEventEffect: () => {} }));
vi.mock('../src/hooks/useInbox', () => ({
  useInbox: () => ({ items: h.items, loading: false, refresh: h.refresh }),
}));
vi.mock('../src/hooks/useUnifiedOutputs', () => ({
  useUnifiedOutputs: () => ({ rows: Array.from({ length: h.unread }, (_, i) => ({ id: `o${i}` })) }),
}));
vi.mock('../src/lib/EndpointContext', () => ({
  useEndpoint: () => ({ endpoint: h.endpoint, probeState: new Map([['c1', 'online']]), activeRole: h.role }),
}));
vi.mock('../src/lib/pins', () => ({
  usePins: () => ({
    isProfilePinned: (name) => h.pinnedProfiles.includes(name),
    isWorkgroupPinned: () => false,
    toggleProfile: h.toggleProfile,
    toggleWorkgroup: () => {},
  }),
}));
import { space } from '../src/theme/tokens';
import { _resetLaunchRestore } from '../src/features/shell/launchRestore';
import Index from '../app/index.jsx';

const ITEMS = [
  { kind: 'profile', id: 'doc', name: 'doc', label: 'doc', preview: 'hi', ts: '2m' },
  { kind: 'profile', id: 'agora', name: 'agora', label: 'agora', preview: 'ok', ts: '5m' },
  { kind: 'workgroup', id: 'alpha', profile: 'doc', name: 'alpha', label: 'alpha', preview: 'go', ts: '1h' },
];

function row(label) {
  return screen.getByText(label).closest('button');
}

function header(label) {
  return screen.getByText(label).closest('div');
}

beforeEach(() => {
  _resetLaunchRestore();
  h.items = ITEMS;
  h.pinnedProfiles = [];
  h.role = 'admin';
  h.endpoint = { id: 'c1', name: 'casa', url: 'ws://casa:49200' };
  h.pathname = '/';
  h.unread = 0;
  h.edges = [];
  h.list = null;
  h.push.mockClear();
  h.replace.mockClear();
  h.toggleProfile.mockClear();
  h.toast.mockClear();
});

function settingsEntry() {
  return screen.getByLabelText('Settings');
}

function bellEntry(unread = 0) {
  return screen.getByLabelText(unread > 0 ? `Notifications · ${unread} unread` : 'Notifications');
}

describe('Inbox screen launch', () => {
  it('lands on the roster and opens no chat, unlike the two-pane sidebar', () => {
    h.items = ITEMS;
    render(<Index />);
    expect(screen.getByText('doc')).toBeTruthy();
    expect(h.replace).not.toHaveBeenCalled();
    expect(h.push).not.toHaveBeenCalled();
  });
});

describe('Inbox screen footer', () => {
  it('carries Settings, notifications and the version, in that order', () => {
    render(<Index />);
    const version = screen.getByText('v0.3.1');
    expect(settingsEntry().compareDocumentPosition(bellEntry()) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(bellEntry().compareDocumentPosition(version) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('leaves the header with the connection and the search toggle alone', () => {
    render(<Index />);
    expect(screen.queryByLabelText('Header bell')).toBeNull();
    expect(screen.queryByLabelText('Header gear')).toBeNull();
    expect(document.querySelector('[data-conn="casa"]')).toBeTruthy();
  });

  it('opens settings as the route the tablet already uses', () => {
    render(<Index />);
    fireEvent.click(settingsEntry());
    expect(h.push).toHaveBeenCalledWith('/settings');
  });

  it('sends the bell to the /outputs route, keeping its own back affordance', () => {
    h.unread = 3;
    render(<Index />);
    fireEvent.click(bellEntry(3));
    expect(h.push).toHaveBeenCalledWith('/outputs');
    expect(h.replace).not.toHaveBeenCalled();
    expect(document.querySelector('[data-sheet]')).toBeNull();
  });

  it('gives a member Settings and the version but no bell', () => {
    h.role = 'member';
    h.unread = 2;
    render(<Index />);
    expect(settingsEntry()).toBeTruthy();
    expect(screen.getByText('v0.3.1')).toBeTruthy();
    expect(screen.queryByLabelText('Notifications')).toBeNull();
    expect(screen.queryByLabelText('Notifications · 2 unread')).toBeNull();
  });
});

describe('Inbox screen footer seating', () => {
  it('takes the bottom safe-area inset on the container, so the footer clears the gesture bar', () => {
    render(<Index />);
    expect(h.edges).toContain('bottom');
    expect(h.edges).toContain('top');
  });

  it('sits below the list in flow and pads the scroll by a gutter, so the last row stays reachable', () => {
    render(<Index />);
    const list = screen.getByTestId('list');
    expect(list.compareDocumentPosition(settingsEntry()) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(h.list.contentContainerStyle.paddingBottom).toBe(space.s9);
  });
});

describe('Inbox screen creation', () => {
  it('floats no compose button — creation lives on the headings', () => {
    render(<Index />);
    expect(screen.queryByLabelText('Compose')).toBeNull();
  });

  it('gives an admin a + on the profiles and workgroups headings only', () => {
    h.pinnedProfiles = ['doc'];
    render(<Index />);
    expect(header('PROFILES').querySelector('[aria-label="New profile"]')).toBeTruthy();
    expect(header('WORKGROUPS').querySelector('[aria-label="New workgroup"]')).toBeTruthy();
    expect(header('PINNED').querySelector('button')).toBeNull();
  });

  it('gives a non-admin no + at all', () => {
    h.role = 'member';
    render(<Index />);
    expect(screen.queryByLabelText('New profile')).toBeNull();
    expect(screen.queryByLabelText('New workgroup')).toBeNull();
  });

  it('opens the create sheet from each + and never navigates to a create route', () => {
    render(<Index />);
    fireEvent.click(screen.getByLabelText('New profile'));
    expect(document.querySelector('[data-create="profile"]')).toBeTruthy();

    fireEvent.click(screen.getByLabelText('New workgroup'));
    expect(document.querySelector('[data-create="workgroup"]')).toBeTruthy();
    expect(document.querySelector('[data-create="profile"]')).toBeNull();

    expect(h.push).not.toHaveBeenCalled();
  });

  it('creates the first workgroup on a daemon that has none', () => {
    h.items = ITEMS.filter((it) => it.kind === 'profile');
    render(<Index />);
    expect(screen.queryByText('alpha')).toBeNull();
    fireEvent.click(screen.getByLabelText('New workgroup'));
    expect(document.querySelector('[data-create="workgroup"]')).toBeTruthy();
  });

  it('keeps both + reachable when every row sits under PINNED', () => {
    h.items = ITEMS.filter((it) => it.kind === 'profile');
    h.pinnedProfiles = ['doc', 'agora'];
    render(<Index />);
    expect(header('PINNED')).toBeTruthy();
    fireEvent.click(screen.getByLabelText('New profile'));
    expect(document.querySelector('[data-create="profile"]')).toBeTruthy();
    fireEvent.click(screen.getByLabelText('New workgroup'));
    expect(document.querySelector('[data-create="workgroup"]')).toBeTruthy();
  });

  it('offers the first profile and the first workgroup on a daemon with nothing at all', () => {
    h.items = [];
    render(<Index />);
    expect(screen.getByText('Nothing here yet')).toBeTruthy();
    fireEvent.click(screen.getByLabelText('New profile'));
    expect(document.querySelector('[data-create="profile"]')).toBeTruthy();
  });

  it('leaves a non-admin the empty verdict with no + to press', () => {
    h.items = [];
    h.role = 'member';
    render(<Index />);
    expect(screen.getByText('Nothing here yet')).toBeTruthy();
    expect(screen.queryByLabelText('New profile')).toBeNull();
    expect(screen.queryByLabelText('New workgroup')).toBeNull();
  });

  it('mounts no create sheet for a non-admin', () => {
    h.role = 'member';
    render(<Index />);
    expect(document.querySelector('[data-create]')).toBeNull();
  });

  it('offers no + while the role probe is still out', () => {
    h.role = null;
    render(<Index />);
    expect(screen.queryByLabelText('New profile')).toBeNull();
    expect(screen.queryByLabelText('New workgroup')).toBeNull();
    expect(document.querySelector('[data-create]')).toBeNull();
  });

  it('takes back an open create form when the daemon demotes the device, and says why', () => {
    const { rerender } = render(<Index />);
    fireEvent.click(screen.getByLabelText('New workgroup'));
    expect(document.querySelector('[data-create="workgroup"]')).toBeTruthy();

    h.role = 'member';
    rerender(<Index />);
    expect(document.querySelector('[data-create]')).toBeNull();
    expect(h.toast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Admin only' }));
  });
});

describe('Inbox screen rows', () => {
  it('wraps no row in a swipe container — long-press owns row actions', () => {
    const { container } = render(<Index />);
    expect(container.querySelector('[data-gesture]')).toBeNull();
    expect(row('doc').parentElement.getAttribute('data-item')).toBe('profile:doc');
  });

  it('keeps long-press opening the context sheet with Pin', () => {
    render(<Index />);
    fireEvent.contextMenu(row('doc'));
    expect(document.querySelector('[data-sheet]').getAttribute('data-sheet')).toBe('@doc');
    expect(screen.getByText('Pin').querySelector('[data-icon="pin"]')).toBeTruthy();
    fireEvent.click(screen.getByText('Pin'));
    expect(h.toggleProfile).toHaveBeenCalledWith('doc');
  });

  it('offers Unpin from the context sheet of a pinned row', () => {
    h.pinnedProfiles = ['doc'];
    render(<Index />);
    fireEvent.contextMenu(row('doc'));
    expect(screen.getByText('Unpin')).toBeTruthy();
    expect(screen.queryByText('Pin')).toBeNull();
  });

  it('opens the row it was tapped on', () => {
    render(<Index />);
    fireEvent.click(row('doc'));
    expect(h.push).toHaveBeenCalledWith('/chat/doc');
    fireEvent.click(row('alpha'));
    expect(h.push).toHaveBeenCalledWith('/wg/alpha');
  });
});

const WITH_HISTORY = ITEMS.map((it, i) => ({ ...it, sortKey: 300 - i }));

describe('Inbox screen arrival', () => {
  it('holds the roster on launch, however recent the last chat is', () => {
    h.items = WITH_HISTORY;
    render(<Index />);
    expect(h.push).not.toHaveBeenCalled();
    expect(h.replace).not.toHaveBeenCalled();
    expect(row('agora')).toBeTruthy();
  });

  it('opens only what the user taps, however the roster refreshes after', () => {
    h.items = WITH_HISTORY;
    const { rerender } = render(<Index />);

    fireEvent.click(row('agora'));
    h.pathname = '/chat/agora';
    expect(h.push).toHaveBeenCalledWith('/chat/agora');

    h.items = WITH_HISTORY.map((it) => ({ ...it, sortKey: it.sortKey + 100 }));
    rerender(<Index />);
    expect(h.push).toHaveBeenCalledTimes(1);
  });
});

describe('Inbox screen connection identity', () => {
  it('shows a legacy ip/port connection as its address instead of claiming it is unpaired', () => {
    h.endpoint = { id: 'c1', name: 'casa', ip: '100.99.29.84', port: 49200 };
    render(<Index />);
    expect(document.querySelector('[data-conn]').getAttribute('data-host')).toBe('ws://100.99.29.84:49200');
  });

  it('says not paired only when there is no connection at all', () => {
    h.endpoint = null;
    render(<Index />);
    expect(document.querySelector('[data-conn]').getAttribute('data-host')).toBe('not paired');
  });
});
