import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
  pathname: '/',
  profiles: [],
  peers: [],
  summariesLoading: false,
  order: [],
  call: vi.fn(),
  wgRefresh: vi.fn(),
  toast: vi.fn(),
}));

vi.mock('react-native', () => {
  const View = ({ children, style, ...p }) => React.createElement('div', p, children);
  const Text = ({ children, style, ...p }) => React.createElement('span', p, children);
  const Pressable = ({ children, onPress, style, hitSlop, accessibilityLabel, ...p }) =>
    React.createElement(
      'button',
      { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel, 'data-slop': String(hitSlop ?? '') },
      typeof children === 'function' ? children({ pressed: false }) : children,
    );
  const TextInput = ({ value, onChangeText, placeholder }) =>
    React.createElement('input', {
      value: value ?? '',
      placeholder,
      onChange: (e) => onChangeText?.(e.target.value),
    });
  const ScrollView = ({ children }) => React.createElement('div', {}, children);
  const Modal = ({ children, visible }) => (visible ? React.createElement('div', {}, children) : null);
  return { Keyboard: { addListener: () => ({ remove: () => {} }) }, Modal, Pressable, ScrollView, Text, TextInput, View, useWindowDimensions: () => ({ width: 390, height: 844 }) };
});

vi.mock('react-native-reanimated', () => ({
  default: {
    View: ({ children, style }) =>
      React.createElement('div', { 'data-style': JSON.stringify(Object.assign({}, ...[].concat(style))) }, children),
  },
}));
vi.mock('react-native-gesture-handler', () => ({
  GestureDetector: ({ children }) => React.createElement('div', {}, children),
}));
vi.mock('react-native-safe-area-context', () => ({ useSafeAreaInsets: () => ({ bottom: 0 }) }));
vi.mock('../../components/useSheetGesture', () => ({
  useSheetGesture: (open) => ({ gesture: {}, sheetStyle: {}, backdropStyle: {}, mounted: open }),
}));
vi.mock('../../components/Button', () => ({
  Button: ({ title, onPress, disabled }) =>
    React.createElement('button', { type: 'button', onClick: onPress, disabled: !!disabled }, title),
}));
vi.mock('../../components/ActionSheet', () => ({
  ActionSheet: ({ open, actions = [] }) =>
    open
      ? React.createElement(
          'div',
          { 'data-picker': 'hub' },
          actions.map((a) => React.createElement('button', { key: a.id, type: 'button', onClick: a.onPress }, a.label)),
        )
      : null,
}));
vi.mock('../../components/Diamond', () => ({ Diamond: () => React.createElement('span', { 'data-diamond': 'true' }) }));
vi.mock('../../components/Icon', () => ({ Icon: ({ name }) => React.createElement('span', { 'data-icon': name }) }));

vi.mock('../../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: {
      bgPane: '#ffffff', bgInput: '#f1f3f5', line2: '#dddddd', hover: '#f4f4f4', selected: '#eaeaea',
      ink: '#0b1117', ink2: '#3d4955', ink3: '#7c8896', ink4: '#b1bac4',
    },
    fonts: { sans: { regular: 'r', medium: 'm', semibold: 's' }, mono: 'mono' },
    fontSizes: { xs: 11, sm: 12, md: 14, lg: 15, xl: 18 },
    mobile: { inputH: 44 },
    shadow: { base: {} },
  }),
}));

vi.mock('expo-router', () => ({
  useRouter: () => ({
    push: (p) => { h.order.push(`push:${p}`); h.push(p); },
    replace: (p) => { h.order.push(`replace:${p}`); h.replace(p); },
  }),
  usePathname: () => h.pathname,
}));
vi.mock('../../components/Toast', () => ({ useToast: () => h.toast }));
vi.mock('../../hooks/useDaemonData', () => ({
  useProfileSummaries: () => ({ data: { profiles: h.profiles }, loading: h.summariesLoading, refresh: vi.fn() }),
  useWorkgroups: () => ({ data: { workgroups: [] }, loading: false, refresh: h.wgRefresh }),
}));
vi.mock('../../hooks/useSubject', () => ({ useProfile: (name) => ({ profile: name ? { peers: h.peers } : null }) }));
vi.mock('../../lib/EndpointContext', () => ({ useEndpoint: () => ({ call: h.call }) }));

import { PaneContext } from '../../nav/PaneContext';
import { CreateWorkgroupSheet } from './CreateWorkgroupSheet';

const NAME = 'team-alpha · roadmap · customers';

function renderSheet(twoPane = false) {
  return render(
    <PaneContext.Provider value={{ twoPane, side: twoPane ? 'detail' : 'full' }}>
      <CreateWorkgroupSheet open onClose={h.close} />
    </PaneContext.Provider>,
  );
}

const createButton = () => screen.getByRole('button', { name: 'Create' });
const sheetStyle = (container) =>
  JSON.parse([...container.querySelectorAll('[data-style]')].at(-1).getAttribute('data-style'));

function fillForm() {
  fireEvent.change(screen.getByPlaceholderText(NAME), { target: { value: 'launch' } });
  fireEvent.click(screen.getByLabelText('@scout'));
}

beforeEach(() => {
  h.pathname = '/';
  h.profiles = [
    { name: 'mira', counts: { peers: 2 }, model: 'deepseek-v4-flash' },
    { name: 'solo', counts: { peers: 0 } },
  ];
  h.peers = [{ id: 'scout', pubkey: 'pub-scout' }, { id: 'muse', pubkey: 'pub-muse' }];
  h.summariesLoading = false;
  h.order = [];
  h.call = vi.fn(async () => ({ wg_id: 'wg-1' }));
  h.wgRefresh = vi.fn(async () => { h.order.push('refresh'); });
  h.push.mockClear();
  h.replace.mockClear();
  h.toast.mockClear();
  h.close = vi.fn();
});

describe('CreateWorkgroupSheet hub', () => {
  it('offers only profiles that already have ALP peers, defaulting to the first', () => {
    renderSheet();
    expect(screen.getByText('@mira')).toBeTruthy();

    fireEvent.click(screen.getByLabelText('Pick hub profile'));
    expect(document.querySelector('[data-picker="hub"]')).toBeTruthy();
    expect(screen.queryByText('@solo')).toBeNull();
  });

  it('drops the chosen members when the hub changes', () => {
    renderSheet();
    fillForm();
    expect(createButton().disabled).toBe(false);

    h.profiles = [...h.profiles, { name: 'nova', counts: { peers: 1 } }];
    fireEvent.click(screen.getByLabelText('Pick hub profile'));
    fireEvent.click(screen.getByText('@nova'));
    expect(createButton().disabled).toBe(true);
  });
});

describe('CreateWorkgroupSheet validation', () => {
  it('needs a hub, a name and at least one member', () => {
    renderSheet();
    expect(createButton().disabled).toBe(true);

    fireEvent.change(screen.getByPlaceholderText(NAME), { target: { value: 'launch' } });
    expect(createButton().disabled).toBe(true);

    fireEvent.click(screen.getByLabelText('@scout'));
    expect(createButton().disabled).toBe(false);
  });

  it('masks characters a workgroup name can never hold', () => {
    renderSheet();
    fireEvent.change(screen.getByPlaceholderText(NAME), { target: { value: 'Launch day!' } });
    expect(screen.getByPlaceholderText(NAME).value).toBe('Launchday');
  });

  it('lifts each member chip to the touch floor', () => {
    renderSheet();
    expect(screen.getByLabelText('@scout').getAttribute('data-slop')).toBe('6');
  });

  it('says so when no profile has a peer to invite', () => {
    h.profiles = [{ name: 'solo', counts: { peers: 0 } }];
    renderSheet();
    expect(screen.getByText(/No profile has any ALP peers yet/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Create' })).toBeNull();
  });

  it('leaves dismissal to the header icon instead of a footer button worded Close', () => {
    h.profiles = [{ name: 'solo', counts: { peers: 0 } }];
    renderSheet();
    const close = screen.getByRole('button', { name: 'Close' });
    expect(close.querySelector('[data-icon]').getAttribute('data-icon')).toBe('x');
    expect(screen.queryByText('Close')).toBeNull();
  });
});

describe('CreateWorkgroupSheet creation', () => {
  it('creates on the hub, then opens the new workgroup', async () => {
    renderSheet();
    fillForm();
    fireEvent.click(createButton());

    await waitFor(() => expect(h.call).toHaveBeenCalledWith('host.workgroup.create', {
      profile: 'mira',
      name: 'launch',
      members: ['scout'],
      briefing: undefined,
    }));
    await waitFor(() => expect(h.push).toHaveBeenCalledWith('/wg/wg-1'));
    expect(h.close).toHaveBeenCalled();
    expect(h.toast).toHaveBeenCalledWith({ title: 'Workgroup created', message: '#launch' });
  });

  it('sends the briefing when one was typed', async () => {
    renderSheet();
    fillForm();
    fireEvent.change(screen.getByPlaceholderText('what is this workgroup about? who does what?'), {
      target: { value: '  ship the launch  ' },
    });
    fireEvent.click(createButton());

    await waitFor(() => expect(h.call).toHaveBeenCalledWith(
      'host.workgroup.create',
      expect.objectContaining({ briefing: 'ship the launch' }),
    ));
  });

  it('refreshes the workgroup list before it navigates onto the fresh id', async () => {
    renderSheet();
    fillForm();
    fireEvent.click(createButton());

    await waitFor(() => expect(h.order).toEqual(['refresh', 'push:/wg/wg-1']));
  });

  it('replaces instead of stacking on top of the sidebar selection', async () => {
    h.pathname = '/';
    renderSheet(true);
    fillForm();
    fireEvent.click(createButton());

    await waitFor(() => expect(h.replace).toHaveBeenCalledWith('/wg/wg-1'));
    expect(h.push).not.toHaveBeenCalled();
  });

  it('pushes when two panes already show a drilled screen', async () => {
    h.pathname = '/wg/wg-0/settings';
    renderSheet(true);
    fillForm();
    fireEvent.click(createButton());

    await waitFor(() => expect(h.push).toHaveBeenCalledWith('/wg/wg-1'));
    expect(h.replace).not.toHaveBeenCalled();
  });

  it('falls back to the root when the daemon returns no id', async () => {
    h.call = vi.fn(async () => ({}));
    renderSheet();
    fillForm();
    fireEvent.click(createButton());

    await waitFor(() => expect(h.push).toHaveBeenCalledWith('/'));
  });

  it('leaves the sheet usable when the daemon rejects the create', async () => {
    h.call = vi.fn(async () => { throw new Error('nope'); });
    renderSheet();
    fillForm();
    fireEvent.click(createButton());

    await waitFor(() => expect(h.toast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Create failed' })));
    expect(h.push).not.toHaveBeenCalled();
    expect(h.close).not.toHaveBeenCalled();
    await waitFor(() => expect(createButton().disabled).toBe(false));
  });
});

describe('CreateWorkgroupSheet pane modes', () => {
  it('rides the phone bottom sheet on one pane', () => {
    const { container } = renderSheet();
    expect(sheetStyle(container).maxWidth).toBeUndefined();
    expect(screen.getByPlaceholderText(NAME)).toBeTruthy();
  });

  it('becomes a centred capped dialog on two panes', () => {
    const { container } = renderSheet(true);
    expect(sheetStyle(container).maxWidth).toBe(560);
    expect(screen.getByPlaceholderText(NAME)).toBeTruthy();
  });
});
