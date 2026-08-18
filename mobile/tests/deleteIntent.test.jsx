import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  push: vi.fn(),
  back: vi.fn(),
  replace: vi.fn(),
  toast: vi.fn(),
  call: vi.fn(async () => ({})),
  params: {},
  profiles: {},
  wg: null,
}));

const sheet = vi.hoisted(() => ({ props: null }));

vi.mock('react-native', () => {
  const View = ({ children, style, accessibilityLabel, ...p }) =>
    React.createElement(
      'div',
      { ...p, ...(accessibilityLabel ? { 'aria-label': accessibilityLabel } : {}) },
      children,
    );
  const Text = ({ children, style, numberOfLines, ellipsizeMode, ...p }) =>
    React.createElement('span', p, children);
  const Pressable = ({ children, onPress, onLongPress, style, disabled, hitSlop, android_ripple, accessibilityLabel, ...p }) =>
    React.createElement(
      'button',
      {
        type: 'button',
        disabled: !!disabled,
        onClick: () => { if (!disabled) onPress?.(); },
        ...(accessibilityLabel ? { 'aria-label': accessibilityLabel } : {}),
        ...p,
      },
      children instanceof Function ? children({ pressed: false }) : children,
    );
  const TextInput = ({ value, onChangeText, placeholder, style, ...p }) =>
    React.createElement('input', {
      value: value ?? '',
      placeholder,
      onChange: (e) => onChangeText?.(e.target.value),
    });
  const Modal = ({ children, visible }) =>
    visible ? React.createElement('div', { 'data-dialog': 'true' }, children) : null;
  return {
    View,
    Text,
    Pressable,
    TextInput,
    Modal,
    ScrollView: View,
    ActivityIndicator: () => React.createElement('span', { 'data-testid': 'spinner' }),
    Platform: { OS: 'ios', select: (s) => s?.ios ?? s?.default },
    StyleSheet: { create: (s) => s },
  };
});

vi.mock('react-native-reanimated', () => ({
  default: { View: ({ children }) => React.createElement('div', {}, children) },
  Easing: { bezier: (...pts) => `bezier(${pts.join(',')})` },
  useAnimatedStyle: (fn) => fn(),
  useSharedValue: (initial) => React.useRef({ value: initial }).current,
  withTiming: (to) => to,
}));

vi.mock('react-native-safe-area-context', () => ({
  SafeAreaView: ({ children }) => React.createElement('div', {}, children),
}));

vi.mock('expo-router', () => ({
  useLocalSearchParams: () => h.params,
  useRouter: () => ({ push: h.push, back: h.back, replace: h.replace, canGoBack: () => true }),
  useFocusEffect: (fn) => { fn?.(); },
}));

vi.mock('../src/theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: {
      bg: '#fff', bgPane: '#fff', bgInput: '#f1f3f5', line: '#eee', line2: '#ddd',
      selected: '#eaeaea', hover: '#f4f4f4',
      ink: '#000', ink2: '#333', ink3: '#666', ink4: '#999',
      accent: '#c90', danger: '#c00', warning: '#dd0', success: '#0a0',
    },
    fonts: {
      sans: { regular: 'r', medium: 'm', semibold: 's', bold: 'b' },
      mono: 'mono', monoMedium: 'monoMedium', monoSemibold: 'monoSemibold',
    },
    fontSizes: { xxs: 9, xs: 11, sm: 12, base: 13, md: 14, lg: 15, xl: 18, '2xl': 22, display: 28 },
    lineHeights: { tight: 1, cozy: 1.3, normal: 1.5, relaxed: 1.65 },
    mobile: { tap: 44, inputH: 44 },
    alpha: { muted: 0.55 },
  }),
}));

vi.mock('../src/components/ActionSheet', () => ({
  ActionSheet: (props) => { sheet.props = props; return null; },
}));
vi.mock('../src/components/Diamond', () => ({ Diamond: () => React.createElement('span') }));
vi.mock('../src/components/Eyebrow', () => ({ Eyebrow: ({ children }) => React.createElement('span', {}, children) }));
vi.mock('../src/components/Icon', () => ({ Icon: ({ name }) => React.createElement('span', { 'data-icon': name }) }));
vi.mock('../src/components/OnOff', () => ({ OnOff: ({ on }) => React.createElement('span', {}, on ? 'on' : 'off') }));
vi.mock('../src/components/Pill', () => ({ Pill: ({ children }) => React.createElement('span', {}, children) }));
vi.mock('../src/components/ScreenHeader', () => ({
  ScreenHeader: ({ title, subtitle }) => React.createElement('header', { 'data-subtitle': subtitle }, title),
}));
vi.mock('../src/components/SyncBar', () => ({ SyncBar: () => null }));
vi.mock('../src/components/Toast', () => ({ useToast: () => h.toast }));
vi.mock('../src/components/Row', () => ({
  SectionHeader: ({ children }) => React.createElement('h2', {}, children),
  RowSeparator: () => React.createElement('hr'),
  Row: ({ label, helper, value, onPress }) =>
    React.createElement(
      'button',
      { type: 'button', 'data-row': typeof label === 'string' ? label : '', onClick: onPress },
      [
        React.createElement('span', { key: 'l' }, label),
        helper ? React.createElement('small', { key: 'h' }, helper) : null,
        value ? React.createElement('strong', { key: 'v' }, value) : null,
      ],
    ),
}));

vi.mock('../src/features/sheets/AccentSheet', () => ({ AccentSheet: () => null }));
vi.mock('../src/features/sheets/EditBudgetSheet', () => ({ EditBudgetSheet: () => null }));
vi.mock('../src/features/sheets/ProfileFieldSheets', () => ({
  BudgetSheet: () => null,
  CleanupSheet: () => null,
  ModelSheet: () => null,
  ReasoningEffortSheet: () => null,
  VoiceSheet: () => null,
  WorkspaceSheet: () => null,
}));
vi.mock('../src/features/workgroups/PipelinesSection', () => ({ PipelinesSection: () => null }));

vi.mock('../src/hooks/useActiveRole', () => ({
  useActiveRole: () => 'admin',
  useCanAdminEarly: () => true,
}));
vi.mock('../src/hooks/useDaemonData', () => ({
  seedCache: vi.fn(),
  useProfileSnapshot: () => ({ data: null, loading: false, unsupported: false, refresh: async () => null }),
  useEmailAccounts: () => ({ data: null, loading: false }),
  useProfileStorage: () => ({ data: null, loading: false }),
  useScheduleList: () => ({ data: null, loading: false }),
  useProfileSummaries: () => ({ data: { profiles: [] }, loading: false, refresh: vi.fn() }),
  useWorkgroupMembers: () => ({ data: { members: [] }, loading: false, refresh: vi.fn() }),
}));
vi.mock('../src/hooks/useSubject', () => ({
  useProfile: (name) => ({
    profile: h.profiles[name] ?? null,
    loading: false,
    refresh: vi.fn(),
    refreshDetail: vi.fn(),
  }),
  useWorkgroup: (id) => ({
    workgroup: h.wg?.id === id ? h.wg : null,
    loading: false,
    refresh: vi.fn(),
  }),
}));
vi.mock('../src/lib/EndpointContext', () => ({
  useEndpoint: () => ({ call: h.call, endpoint: { id: 'c1' } }),
}));

import { RowContextSheet } from '../src/features/inbox/RowContextSheet';
import ProfileSettings from '../app/profile/[id]/settings.jsx';
import WorkgroupSettings from '../app/wg/[id]/settings.jsx';

const PROFILE_ROW = { kind: 'profile', id: 'agora', name: 'agora', label: 'agora' };
const WORKGROUP_ROW = { kind: 'workgroup', id: 'alpha', name: 'alpha', label: 'alpha', profile: 'doc' };

const WG = { id: 'alpha', name: 'alpha', profile: 'doc', hub_id: 'doc', is_hub: true, members: 0 };

const DESTINATIONS = { '/profile/[id]/settings': ProfileSettings, '/wg/[id]/settings': WorkgroupSettings };

function followDelete(row) {
  const view = render(<RowContextSheet target={row} onOpenSettings={() => {}} />);
  sheet.props.actions.find((a) => a.id === 'delete').onPress();
  view.unmount();
  const [href] = h.push.mock.calls.at(-1);
  const [path, query] = href.split('?');
  const [, kind, id, leaf] = path.split('/');
  const Screen = DESTINATIONS[`/${kind}/[id]/${leaf}`];
  h.params = { id, ...Object.fromEntries(new URLSearchParams(query)) };
  return { path, Screen, render: () => render(<Screen />) };
}

function dialog() {
  return document.querySelector('[data-dialog]');
}

function pressDialogButton(label) {
  fireEvent.click(within(dialog()).getByText(label).closest('button'));
}

function typeConfirmation(text) {
  fireEvent.change(dialog().querySelector('input'), { target: { value: text } });
}

beforeEach(() => {
  h.push.mockClear();
  h.replace.mockClear();
  h.toast.mockClear();
  h.call.mockClear().mockResolvedValue({});
  h.params = {};
  h.profiles = { agora: { name: 'agora', counts: {} } };
  h.wg = { ...WG };
  sheet.props = null;
});

describe('row-menu delete lands on the destination confirmation', () => {
  it('opens the profile delete confirmation the menu entry promised', () => {
    const trip = followDelete(PROFILE_ROW);
    expect(trip.path).toBe('/profile/agora/settings');
    trip.render();
    expect(within(dialog()).getByText('Delete profile @agora')).toBeTruthy();
  });

  it('opens the workgroup delete confirmation the menu entry promised', () => {
    const trip = followDelete(WORKGROUP_ROW);
    expect(trip.path).toBe('/wg/alpha/settings');
    trip.render();
    expect(within(dialog()).getByText('Delete workgroup #alpha')).toBeTruthy();
  });

  it('deletes nothing on arrival — the tap buys a confirmation, not a deletion', () => {
    followDelete(PROFILE_ROW).render();
    expect(dialog()).toBeTruthy();
    expect(h.call).not.toHaveBeenCalled();
    expect(h.replace).not.toHaveBeenCalled();
    cleanup();
    followDelete(WORKGROUP_ROW).render();
    expect(dialog()).toBeTruthy();
    expect(h.call).not.toHaveBeenCalled();
    expect(h.replace).not.toHaveBeenCalled();
  });

  it('keeps the confirm button inert until the profile name is typed exactly', async () => {
    followDelete(PROFILE_ROW).render();
    pressDialogButton('Delete profile');
    expect(h.call).not.toHaveBeenCalled();
    typeConfirmation('agor');
    pressDialogButton('Delete profile');
    expect(h.call).not.toHaveBeenCalled();
    typeConfirmation('agora');
    pressDialogButton('Delete profile');
    await waitFor(() => expect(h.call).toHaveBeenCalledWith('host.profile.delete', { name: 'agora' }));
  });

  it('keeps the confirm button inert until the workgroup id is typed exactly', async () => {
    followDelete(WORKGROUP_ROW).render();
    pressDialogButton('Delete workgroup');
    expect(h.call).not.toHaveBeenCalled();
    typeConfirmation('alpha');
    pressDialogButton('Delete workgroup');
    await waitFor(() =>
      expect(h.call).toHaveBeenCalledWith('host.workgroup.remove', { profile: 'doc', wg_id: 'alpha' }));
  });
});

describe('settings screens without a delete intent', () => {
  it('leaves the profile danger zone closed', () => {
    h.params = { id: 'agora' };
    render(<ProfileSettings />);
    expect(dialog()).toBeNull();
    expect(document.querySelector('[data-row="Delete profile"]')).toBeTruthy();
  });

  it('leaves the workgroup danger zone closed', () => {
    h.params = { id: 'alpha' };
    render(<WorkgroupSettings />);
    expect(dialog()).toBeNull();
    expect(document.querySelector('[data-row="Delete workgroup"]')).toBeTruthy();
  });

  it('ignores an intent the screen has no flow for', () => {
    h.params = { id: 'agora', intent: 'archive' };
    render(<ProfileSettings />);
    expect(dialog()).toBeNull();
  });
});

describe('delete intent on a workgroup this profile does not hub', () => {
  it('opens no confirmation, because a member can only leave', () => {
    h.wg = { ...WG, is_hub: false };
    h.params = { id: 'alpha', intent: 'delete' };
    render(<WorkgroupSettings />);
    expect(dialog()).toBeNull();
    expect(document.querySelector('[data-row="Delete workgroup"]')).toBeNull();
    expect(document.querySelector('[data-row="Leave workgroup"]')).toBeTruthy();
    expect(h.call).not.toHaveBeenCalled();
  });
});
