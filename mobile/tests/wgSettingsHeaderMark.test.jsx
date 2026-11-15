import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render } from '@testing-library/react';

const h = vi.hoisted(() => ({
  push: vi.fn(),
  back: vi.fn(),
  replace: vi.fn(),
  toast: vi.fn(),
  call: vi.fn(async () => ({})),
  params: {},
  profiles: {},
  wg: null,
  members: [],
  snap: null,
  usage: null,
  run: null,
}));

const sheet = vi.hoisted(() => ({ props: null }));

vi.mock('../src/features/sheets/ConnectionSheet', () => ({ ConnectionSheet: () => null }));
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
    Keyboard: { addListener: () => ({ remove() {} }) },
    ScrollView: ({ children, refreshControl, ...p }) => React.createElement(View, p, children),
    RefreshControl: () => null,
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
  usePathname: () => '/profile/doc/settings',
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
    shadow: { base: {} },
    lineHeights: { tight: 1, cozy: 1.3, normal: 1.5, relaxed: 1.65 },
    mobile: { tap: 44, inputH: 44 },
    alpha: { muted: 0.55 },
  }),
}));

vi.mock('../src/components/ActionSheet', () => ({
  ActionSheet: (props) => { sheet.props = props; return null; },
}));
vi.mock('../src/components/Diamond', () => ({ Diamond: () => React.createElement('span') }));
vi.mock('../src/components/Fold', () => ({ Fold: ({ shape, state, phase }) => React.createElement('span', { 'data-shape': shape ?? 'diamond', 'data-state': state ?? '', 'data-phase': phase ? phase.join('/') : '' }) }));
vi.mock('../src/components/Eyebrow', () => ({ Eyebrow: ({ children }) => React.createElement('span', {}, children) }));
vi.mock('../src/components/Icon', () => ({ Icon: ({ name }) => React.createElement('span', { 'data-icon': name }) }));
vi.mock('../src/components/OnOff', () => ({ OnOff: ({ on }) => React.createElement('span', {}, on ? 'on' : 'off') }));
vi.mock('../src/components/Toggle', () => ({ Toggle: ({ on, label }) => React.createElement('span', { 'aria-label': label }, on ? 'on' : 'off') }));
vi.mock('../src/features/settings/IdentityEditor', () => ({ IdentityEditor: () => null }));
vi.mock('../src/components/UsageSkeleton', () => ({ UsageSkeleton: () => React.createElement('div', { 'data-usage': 'bones' }) }));
vi.mock('../src/components/UsageChart', () => ({ UsageChart: ({ days }) => React.createElement('div', { 'data-usage': 'chart' }, String(days.length)) }));
vi.mock('../src/components/FadeIn', () => ({ FadeIn: ({ children, animate = true }) => React.createElement('div', { 'data-fade': String(animate) }, children) }));
vi.mock('../src/components/SkeletonBar', () => ({ STAGGER_MS: 90, SkeletonBar: () => null }));
vi.mock('../src/components/SettingsSkeleton', () => ({ SettingsSkeleton: () => null }));
vi.mock('../src/components/Pill', () => ({ Pill: ({ children }) => React.createElement('span', {}, children) }));
vi.mock('../src/components/ScreenHeader', () => ({
  ScreenHeader: ({ title, leadingGlyph }) => React.createElement('header', {}, leadingGlyph, title),
}));
vi.mock('../src/components/SyncBar', () => ({ SyncBar: () => null }));
vi.mock('../src/components/Toast', () => ({ useToast: () => h.toast }));
vi.mock('../src/components/Row', () => ({
  SectionHeader: ({ children }) => React.createElement('h2', {}, children),
  SettingsBand: ({ children }) => React.createElement('section', {}, children),
  RowGroup: ({ children }) => React.createElement('div', { 'data-row-group': '' }, children),
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

vi.mock('../src/features/sheets/AppearanceSheet', () => ({ AppearanceSheet: () => null }));
vi.mock('../src/features/sheets/EditBudgetSheet', () => ({ EditBudgetSheet: () => null }));
vi.mock('../src/features/sheets/FallbacksSheet', () => ({ FallbacksSheet: () => null }));
vi.mock('../src/features/sheets/ProfileFieldSheets', () => ({
  BudgetSheet: () => null,
  CleanupSheet: () => null,
  ModelSheet: () => null,
  ReasoningEffortSheet: () => null,
  VoiceSheet: () => null,
  WorkspaceSheet: () => null,
}));
vi.mock('../src/features/workgroups/PipelinesSection', () => ({ PipelinesSection: () => null }));

vi.mock('../src/hooks/useAttention', () => ({ useAttention: () => ({ att: null, refresh: () => {} }) }));
vi.mock('../src/hooks/useActiveRole', () => ({
  useActiveRole: () => 'admin',
  useCanAdminEarly: () => true,
}));
vi.mock('../src/hooks/useDaemonData', () => ({
  seedCache: vi.fn(),
  useProfileSnapshot: () => h.snap,
  useEmailAccounts: () => ({ data: null, loading: false }),
  useProfileStorage: () => ({ data: null, loading: false }),
  useScheduleList: () => ({ data: null, loading: false }),
  useProfileSummaries: () => ({ data: { profiles: [] }, loading: false, refresh: vi.fn() }),
  useWorkgroupMembers: () => ({ data: { members: h.members }, loading: false, refresh: vi.fn() }),
  useWorkgroupTasks: () => ({ data: h.run ? { pipeline_run: h.run } : null, loading: false, refresh: vi.fn() }),
  useWorkgroupUsage: () => h.usage,
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

import WorkgroupSettings from '../app/wg/[id]/settings.jsx';

const RUN = { status: 'running', current_phase: 'content', phases: [{ slug: 'intake', state: 'done' }, { slug: 'content', state: 'current' }, { slug: 'edit', state: 'pending' }] };
const glyph = (c) => c.querySelector('header [data-shape]');

beforeEach(() => {
  h.params = { id: 'alpha' };
  h.profiles = { doc: { name: 'doc', accent: '#3899e2', counts: {} } };
  h.wg = { id: 'alpha', name: 'alpha', profile: 'doc', hub_id: 'doc', is_hub: true, members: 0, pipelines: { intake: ['intake', 'content', 'edit'] }, launch_pipeline: 'intake' };
  h.usage = { data: null, loading: false, refresh: vi.fn() };
  h.run = null;
});
afterEach(cleanup);

describe('workgroup settings header mark', () => {
  it('draws the live pipeline run like the chat header', () => {
    h.run = RUN;
    const { container } = render(<WorkgroupSettings />);
    expect(glyph(container).dataset.state).toBe('running');
    expect(glyph(container).dataset.phase).toBe('1/3');
  });

  it('asks for attention while the run is blocked', () => {
    h.run = { ...RUN, status: 'blocked' };
    const { container } = render(<WorkgroupSettings />);
    expect(glyph(container).dataset.state).toBe('needs');
  });

  it('stays idle without a run and dashed when paused', () => {
    const { container, rerender } = render(<WorkgroupSettings />);
    expect(glyph(container).dataset.state).toBe('idle');
    h.wg = { ...h.wg, paused: true };
    h.run = RUN;
    rerender(<WorkgroupSettings />);
    expect(glyph(container).dataset.state).toBe('paused');
  });
});
