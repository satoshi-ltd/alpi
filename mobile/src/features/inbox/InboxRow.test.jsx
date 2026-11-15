import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, renderHook, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  push: vi.fn(),
  call: vi.fn(async () => ({ profiles: [] })),
  toast: vi.fn(),
  seed: vi.fn(),
  dismiss: vi.fn(),
  canAdmin: true,
  flat: (style) => {
    const resolved = typeof style === 'function' ? style({ pressed: false }) : style;
    return [resolved].flat(Infinity).filter(Boolean).reduce((acc, s) => ({ ...acc, ...s }), {});
  },
}));

vi.mock('react-native', () => {
  const View = ({ children, style, accessibilityLabel, ...p }) =>
    React.createElement(
      'div',
      {
        ...p,
        ...(accessibilityLabel ? { 'aria-label': accessibilityLabel } : {}),
        'data-style': JSON.stringify(h.flat(style)),
      },
      children,
    );
  const Text = ({ children, numberOfLines, style, ...p }) =>
    React.createElement('span', { ...p, 'data-style': JSON.stringify(h.flat(style)) }, children);
  const Pressable = ({ children, style, android_ripple, onPress, onLongPress, accessibilityLabel, accessibilityState, ...p }) =>
    React.createElement(
      'button',
      {
        type: 'button',
        onClick: onPress,
        'aria-selected': accessibilityState ? String(!!accessibilityState.selected) : undefined,
        ...(accessibilityLabel ? { 'aria-label': accessibilityLabel } : {}),
        'data-style': JSON.stringify(h.flat(style)),
        ...p,
      },
      children,
    );
  return { View, Text, Pressable, Keyboard: { dismiss: h.dismiss }, StyleSheet: { create: (s) => s } };
});

vi.mock('../../theme/ThemeContext', async () => {
  const tokens = await import('../../theme/tokens');
  return {
    useTheme: () => ({
      colors: {
        ink: '#000', ink2: '#333', ink3: '#666', ink4: '#999',
        accent: '#b8954a', bg: '#fff', bgPane: '#fafafa', danger: '#c14545', hover: '#eee', selected: '#eee',
      },
      fonts: {
        sans: {
          regular: 'Geist_400Regular',
          medium: 'Geist_500Medium',
          semibold: 'Geist_600SemiBold',
          bold: 'Geist_700Bold',
        },
        mono: 'GeistMono_400Regular',
        monoMedium: 'GeistMono_500Medium',
        monoSemibold: 'GeistMono_600SemiBold',
      },
      alpha: { muted: 0.55 },
      fontSizes: tokens.fontSizes,
    }),
  };
});

vi.mock('../../components/Dot', () => ({ Dot: () => React.createElement('span', { 'data-dot': 'true' }) }));
vi.mock('../../components/Glyph', () => ({
  Glyph: ({ kind, shape, active, state, needsProvider, working, paused, offline, rowState, unread, phase, phaseSlug, workgroup, ...rest }) =>
    React.createElement('span', {
      'data-glyph': kind,
      'data-size': rest.size ?? '',
      'data-active': String(!!active),
      'data-mark-state': state ?? '',
      'data-phase-slug': phaseSlug ?? '',
      'data-workgroup': workgroup?.id ?? '',
      'data-accents': JSON.stringify(rest.memberAccents ?? null),
      'data-row-state': rowState ?? '',
      'data-unread': String(!!unread),
      'data-phase': phase ?? '',
      'data-offline': String(!!offline),
      'data-shape': shape ?? '',
      'data-needs-provider': String(!!needsProvider),
      'data-working': String(!!working),
      'data-paused': String(!!paused),
    }),
}));
vi.mock('../../components/Icon', () => ({
  Icon: ({ name, color }) => React.createElement('span', { 'data-icon': name, 'data-color': color }),
}));
vi.mock('./Pip', () => ({ Pip: ({ kind }) => React.createElement('span', { 'data-pip': kind }) }));
vi.mock('./RowState', async (importOriginal) => ({
  ...(await importOriginal()),
  RowState: ({ state, phases, color }) => React.createElement('span', { 'data-state': state, 'data-color': color ?? '' }, phases ?? state),
}));

vi.mock('expo-router', () => ({ useRouter: () => ({ push: h.push }) }));
vi.mock('../../components/Toast', () => ({ useToast: () => h.toast }));
vi.mock('../../hooks/useActiveRole', () => ({ useCanAdminEarly: () => h.canAdmin }));
vi.mock('../../hooks/useDaemonData', () => ({ seedCache: h.seed }));
vi.mock('../../lib/EndpointContext', () => ({
  useEndpoint: () => ({ call: h.call, endpoint: { id: 'c1' } }),
}));

const sheet = vi.hoisted(() => ({ props: null }));
vi.mock('../../components/ActionSheet', () => ({
  ActionSheet: (props) => {
    sheet.props = props;
    return React.createElement('div', { 'data-sheet': String(props.open) }, props.title);
  },
}));

import { mobile, radii, space } from '../../theme/tokens';
import { PaneContext } from '../../nav/PaneContext';
import { FALLBACK_ACCENT } from '../../../../common/shapes.mjs';
import { MARK_SIZES } from '../../../../common/agentMarks.mjs';
import { GLYPH_SLOT, InboxRow, ROW_GUTTER } from './InboxRow';

const SELECTED = '#eee';
import { _resetSessionMarksForTests, sessionMarkKey, useSessionMark } from '../../lib/sessionMark';
import { RowContextSheet } from './RowContextSheet';

const WORKGROUP = {
  kind: 'workgroup',
  id: 'alpha',
  name: 'alpha',
  label: 'alpha',
  profile: 'agora',
  preview: 'status?',
  ts: '3m',
};

const PROFILE = { kind: 'profile', id: 'agora', name: 'agora', label: 'agora', preview: 'ready' };

function styleOf(el) {
  return JSON.parse(el.getAttribute('data-style'));
}

function renderRow(props, pane) {
  const row = <InboxRow {...props} />;
  return render(pane ? <PaneContext.Provider value={pane}>{row}</PaneContext.Provider> : row);
}

function sidebarRow(props) {
  return renderRow(props, { twoPane: true, side: 'list' });
}

function pressable(container) {
  return container.querySelector('button');
}

function actionIds() {
  return sheet.props.actions.map((a) => a.id);
}

function action(id) {
  return sheet.props.actions.find((a) => a.id === id);
}

beforeEach(() => {
  h.canAdmin = true;
  h.push.mockClear();
  h.call.mockClear();
  h.toast.mockClear();
  h.seed.mockClear();
  sheet.props = null;
});

describe('InboxRow name line', () => {
  it('names a workgroup with no hash prefix', () => {
    const { container } = renderRow({ item: WORKGROUP });
    expect(screen.getByText('alpha')).toBeTruthy();
    expect(container.textContent).not.toContain('#');
    expect(container.querySelector('[data-glyph]').getAttribute('data-glyph')).toBe('workgroup');
  });

  it('marks a pinned row with no trailing dot', () => {
    const { container } = renderRow({ item: { ...WORKGROUP, pinned: true } });
    expect(screen.getByText('alpha')).toBeTruthy();
    expect(container.textContent).not.toContain('·');
  });

  it('leaves a pinned profile row undecorated too', () => {
    const { container } = renderRow({ item: { ...PROFILE, pinned: true } });
    expect(container.textContent).not.toContain('#');
    expect(container.textContent).not.toContain('·');
  });
});

describe('InboxRow profile shape', () => {
  it('hands the profile shape to the glyph', () => {
    const { container } = renderRow({ item: { ...PROFILE, shape: 'bell' } });
    expect(container.querySelector('[data-glyph]').getAttribute('data-shape')).toBe('bell');
  });

  it('drops the stale working state of a row whose daemon is away', () => {
    const { container } = renderRow({ item: { ...PROFILE, state: 'working', activity: { state: 'working' } }, showState: true, offline: true });
    expect(container.querySelector('[data-glyph]').getAttribute('data-working')).toBe('false');
    expect(container.textContent).not.toMatch(/working/i);
  });

  it('unfolds the glyph while the daemon is away', () => {
    const { container } = renderRow({ item: { ...PROFILE, shape: 'bell' }, offline: true });
    expect(container.querySelector('[data-glyph]').getAttribute('data-offline')).toBe('true');
  });

  it('hands over no shape for a profile that never chose one', () => {
    const { container } = renderRow({ item: PROFILE });
    expect(container.querySelector('[data-glyph]').getAttribute('data-shape')).toBe('');
  });

  it('keeps the needs-a-model state with the shape', () => {
    const { container } = renderRow({ item: { ...PROFILE, shape: 'bell', needsProvider: true } });
    const glyph = container.querySelector('[data-glyph]');
    expect(glyph.getAttribute('data-shape')).toBe('bell');
    expect(glyph.getAttribute('data-needs-provider')).toBe('true');
  });
});

describe('InboxRow motion and the open chat', () => {
  afterEach(() => _resetSessionMarksForTests());

  it('animates only the selected row', () => {
    const glyph = (props) => {
      const { container } = sidebarRow(props);
      const out = container.querySelector('[data-glyph]').getAttribute('data-active');
      cleanup();
      return out;
    };
    expect(glyph({ item: { ...PROFILE, activity: { state: 'working' } }, showState: true })).toBe('false');
    expect(glyph({ item: { ...PROFILE, activity: { state: 'working' } }, showState: true, selected: true })).toBe('true');
  });

  it('shows the open chat state on the selected row only', () => {
    const chat = renderHook(() => useSessionMark({ key: sessionMarkKey(PROFILE.id), working: true }));
    const selected = sidebarRow({ item: PROFILE, selected: true });
    expect(selected.container.querySelector('[data-glyph]').getAttribute('data-mark-state')).toBe('working');
    cleanup();
    const other = sidebarRow({ item: PROFILE });
    expect(other.container.querySelector('[data-glyph]').getAttribute('data-mark-state')).toBe('');
    cleanup();
    const away = sidebarRow({ item: PROFILE, selected: true, offline: true });
    expect(away.container.querySelector('[data-glyph]').getAttribute('data-mark-state')).toBe('');
    chat.unmount();
  });
});

describe('InboxRow working state', () => {
  it('pips a workgroup the daemon is posting into', () => {
    const { container } = sidebarRow({ item: { ...WORKGROUP, state: 'working' }, showState: true });
    expect(container.querySelector('[data-pip]').getAttribute('data-pip')).toBe('working');
    expect(screen.getByLabelText('alpha working')).toBeTruthy();
  });

  it('draws nothing for a state useInbox never emits', () => {
    const { container } = sidebarRow({ item: { ...WORKGROUP, state: 'error' }, showState: true });
    expect(container.querySelector('[data-pip]')).toBeNull();
    expect(container.querySelector('[data-dot]')).toBeNull();
  });

  it('marks unread with neither a pip nor a dot — typography carries it', () => {
    const { container } = sidebarRow({ item: { ...WORKGROUP, unread: true }, showState: true });
    expect(container.querySelector('[data-pip]')).toBeNull();
    expect(container.querySelector('[data-dot]')).toBeNull();
  });

  it('ripples the workgroup glyph while it works, even on the phone row', () => {
    const { container } = renderRow({ item: { ...WORKGROUP, state: 'working' } });
    expect(container.querySelector('[data-glyph]').getAttribute('data-working')).toBe('true');
  });

  it('ripples the glyph from the activity state too', () => {
    const { container } = renderRow({ item: { ...WORKGROUP, activity: { state: 'working', phases: '2/4' } } });
    expect(container.querySelector('[data-glyph]').getAttribute('data-working')).toBe('true');
  });

  it('hands the run progress, the current phase and the workgroup to the honeycomb, never member colours', () => {
    const raw = { id: 'alpha', pipeline_status: 'blocked', phase_map: { translate: { owner: '@Lingo' } } };
    const item = { ...WORKGROUP, raw, memberAccents: { lingo: '#e2558a' }, activity: { state: 'working', phases: '2/4', phase: 'translate' } };
    const glyph = renderRow({ item }).container.querySelector('[data-glyph]');
    expect(glyph.getAttribute('data-phase')).toBe('2/4');
    expect(glyph.getAttribute('data-phase-slug')).toBe('translate');
    expect(glyph.getAttribute('data-workgroup')).toBe('alpha');
    expect(JSON.parse(glyph.getAttribute('data-accents'))).toBeNull();
  });

  it('hands the row state and unread flag to a profile mark', () => {
    const glyph = renderRow({ item: { ...PROFILE, unread: true, activity: { state: 'needs-you' } } }).container.querySelector('[data-glyph]');
    expect(glyph.getAttribute('data-row-state')).toBe('needs-you');
    expect(glyph.getAttribute('data-unread')).toBe('true');
  });

  it('keeps an idle workgroup glyph still and hands the paused flag to it', () => {
    const idle = renderRow({ item: WORKGROUP }).container.querySelector('[data-glyph]');
    expect(idle.getAttribute('data-working')).toBe('false');
    expect(idle.getAttribute('data-paused')).toBe('false');
    cleanup();
    const paused = renderRow({ item: { ...WORKGROUP, paused: true } }).container.querySelector('[data-glyph]');
    expect(paused.getAttribute('data-paused')).toBe('true');
  });

  it('shows no pip on the phone row even while the workgroup works', () => {
    const { container } = renderRow({ item: { ...WORKGROUP, state: 'working' } });
    expect(container.querySelector('[data-pip]')).toBeNull();
  });
});

describe('InboxRow sidebar variant', () => {
  it('drops the preview line the conversation pane already shows', () => {
    const { container } = sidebarRow({ item: WORKGROUP });
    expect(screen.getByText('alpha')).toBeTruthy();
    expect(container.textContent).not.toContain('status?');
  });

  it('insets an idle fold row inside the 12 pt gutter at the control corner', () => {
    const { container } = sidebarRow({ item: WORKGROUP });
    const style = styleOf(pressable(container));
    expect(style.borderRadius).toBe(radii.control);
    expect(style.marginHorizontal).toBe(space.s5);
    expect(style.minHeight).toBe(mobile.tap);
  });

  it('draws the chosen fold row as the neutral selected fill inside the gutter, rounded, never edge to edge', () => {
    const { container } = sidebarRow({ item: WORKGROUP, selected: true });
    const style = styleOf(pressable(container));
    expect(style.backgroundColor).toBe(SELECTED);
    expect(style.marginHorizontal).toBe(space.s5);
    expect(style.borderRadius).toBe(radii.control);
  });

  it('keeps the phone row two-line and presses it with the selected fill inside an 8 pt gutter, text still 16 in', () => {
    const { container } = renderRow({ item: WORKGROUP });
    const style = styleOf(pressable(container));
    expect(container.textContent).toContain('status?');
    expect(style.borderRadius).toBe(radii.control);
    expect(style.marginHorizontal).toBe(ROW_GUTTER);
    expect(ROW_GUTTER).toBe(8);
    expect(style.marginHorizontal + style.paddingHorizontal).toBe(space.s7);
    expect(style.minHeight).toBe(64);
    expect(style.minHeight).toBeGreaterThanOrEqual(mobile.tap);
  });
});

describe('InboxRow selection and muting', () => {
  it('marks the chosen row with no accent bar and reports it as selected', () => {
    const { container } = sidebarRow({ item: WORKGROUP, selected: true });
    expect(container.querySelector('[testid="selected-bar"]')).toBeNull();
    expect(pressable(container).getAttribute('aria-selected')).toBe('true');
  });

  it('draws no bar on a resting row', () => {
    const { container } = sidebarRow({ item: WORKGROUP });
    expect(container.querySelector('[testid="selected-bar"]')).toBeNull();
  });

  it('never fades a paused row; it keeps opaque secondary ink and says paused', () => {
    const { container } = sidebarRow({ item: { ...WORKGROUP, paused: true } });
    expect(styleOf(pressable(container)).opacity).toBeUndefined();
    expect(styleOf(screen.getByText('alpha')).color).toBe('#666');
    expect(screen.getByText('paused')).toBeTruthy();
    expect(pressable(container).getAttribute('aria-label')).toContain('paused');
  });

  it('does not fade a needs-provider row either', () => {
    const { container } = renderRow({ item: { ...WORKGROUP, needsProvider: true } });
    expect(styleOf(pressable(container)).opacity).toBeUndefined();
  });
});

describe('InboxRow name weight ladder', () => {
  const nameFont = (props, pane) => {
    renderRow(props, pane);
    return styleOf(screen.getByText('alpha')).fontFamily;
  };

  it('steps resting → selected → unread in the sidebar', () => {
    const pane = { twoPane: true, side: 'list' };
    expect(nameFont({ item: WORKGROUP }, pane)).toBe('Geist_400Regular');
    cleanup();
    expect(nameFont({ item: WORKGROUP, selected: true }, pane)).toBe('Geist_500Medium');
    cleanup();
    expect(nameFont({ item: { ...WORKGROUP, unread: true } }, pane)).toBe('Geist_600SemiBold');
  });

  it('lifts the ink only off the resting step', () => {
    sidebarRow({ item: WORKGROUP });
    expect(styleOf(screen.getByText('alpha')).color).toBe('#333');
    cleanup();
    sidebarRow({ item: WORKGROUP, selected: true });
    expect(styleOf(screen.getByText('alpha')).color).toBe('#000');
    cleanup();
    sidebarRow({ item: { ...WORKGROUP, unread: true } });
    expect(styleOf(screen.getByText('alpha')).color).toBe('#000');
  });

  it('leaves the phone ladder as it was', () => {
    expect(nameFont({ item: WORKGROUP })).toBe('Geist_600SemiBold');
    cleanup();
    expect(nameFont({ item: { ...WORKGROUP, unread: true } })).toBe('Geist_700Bold');
  });
});

describe('InboxRow unread mark', () => {
  it('draws no dot on either surface', () => {
    const { container } = renderRow({ item: { ...WORKGROUP, unread: true } });
    expect(container.querySelector('[data-dot]')).toBeNull();
    cleanup();
    expect(sidebarRow({ item: { ...WORKGROUP, unread: true } }).container.querySelector('[data-dot]')).toBeNull();
  });

  it('anchors unread at both ends — name weight on the left, timestamp on the right', () => {
    renderRow({ item: { ...WORKGROUP, unread: true } });
    expect(styleOf(screen.getByText('alpha')).fontFamily).toBe('Geist_700Bold');
    expect(styleOf(screen.getByText('3m')).fontFamily).toBe('Geist_600SemiBold');
    expect(styleOf(screen.getByText('3m')).color).toBe('#000');
  });

  it('rests the timestamp on a read row', () => {
    renderRow({ item: WORKGROUP });
    expect(styleOf(screen.getByText('3m')).fontFamily).toBe('Geist_500Medium');
    expect(styleOf(screen.getByText('3m')).color).toBe('#666');
  });

  it('holds the preview at one ink2 line at 14 pt either way — unread no longer tints it', () => {
    renderRow({ item: WORKGROUP });
    expect(styleOf(screen.getByText('status?')).color).toBe('#333');
    expect(styleOf(screen.getByText('status?')).fontSize).toBe(14);
    cleanup();
    renderRow({ item: { ...WORKGROUP, unread: true } });
    expect(styleOf(screen.getByText('status?')).color).toBe('#333');
  });

  it('announces unread now that no dot carries the label', () => {
    renderRow({ item: { ...WORKGROUP, unread: true } });
    expect(screen.getByLabelText('alpha, unread, status?, 3m')).toBeTruthy();
    cleanup();
    renderRow({ item: WORKGROUP });
    expect(screen.getByLabelText('alpha, status?, 3m')).toBeTruthy();
  });

  it('speaks the row as one button: name, state, preview and time', () => {
    renderRow({ item: { ...PROFILE, ts: '4m', activity: { state: 'needs-you' } } });
    const row = screen.getByLabelText('agora, needs you, ready, 4m');
    expect(row.getAttribute('accessibilityRole')).toBe('button');
    cleanup();
    renderRow({ item: { ...WORKGROUP, activity: { state: 'working', phases: '2/4' } } });
    expect(screen.getByLabelText('alpha, working, phase 2 of 4, status?, 3m')).toBeTruthy();
  });

  it('shows the row state on the phone roster and in the sidebar, and leads a waiting row in bold', () => {
    const { container } = renderRow({ item: { ...PROFILE, activity: { state: 'needs-you' } } });
    expect(container.querySelector('[data-state="needs-you"]')).toBeTruthy();
    expect(styleOf(screen.getByText('agora')).fontFamily).toBe('Geist_700Bold');
    cleanup();
    const side = sidebarRow({ item: { ...WORKGROUP, state: 'working', activity: { state: 'working', phases: '2/4' } }, showState: true });
    expect(side.container.querySelector('[data-state="working"]').textContent).toBe('2/4');
    expect(side.container.querySelector('[data-pip]')).toBeNull();
  });

  it('hands the row state its profile colour', () => {
    const { container } = sidebarRow({ item: { ...WORKGROUP, accent: '#3ac9f3', activity: { state: 'working' } }, showState: true });
    expect(container.querySelector('[data-state="working"]').getAttribute('data-color')).toBe('#3ac9f3');
  });
});

describe('InboxRow row with copy but no timestamp', () => {
  const metaColumns = (container) =>
    [...container.querySelectorAll('div')].filter((el) => styleOf(el).alignItems === 'flex-end');

  it('shows the invitation on a sessionless profile', () => {
    renderRow({ item: { ...PROFILE, preview: 'tap to start a thread', ts: null } });
    expect(screen.getByText('tap to start a thread')).toBeTruthy();
  });

  it('leaves out the meta column entirely so no empty gap trails the row', () => {
    const { container } = renderRow({ item: { ...PROFILE, preview: 'tap to start a thread', ts: null } });
    expect(metaColumns(container)).toHaveLength(0);
    expect(pressable(container).children).toHaveLength(2);
  });

  it('still hangs the timestamp on its own column when there is one', () => {
    const { container } = renderRow({ item: WORKGROUP });
    expect(metaColumns(container)).toHaveLength(1);
    expect(metaColumns(container)[0].textContent).toBe('3m');
    expect(pressable(container).children).toHaveLength(3);
  });

  it('keeps the working pip on a workgroup that has no timestamp yet', () => {
    const { container } = sidebarRow({ item: { ...WORKGROUP, ts: null, state: 'working' }, showState: true });
    expect(container.querySelector('[data-pip]')).toBeTruthy();
    expect(metaColumns(container)).toHaveLength(1);
  });
});

describe('RowContextSheet title', () => {
  it('keeps the hash so a workgroup reads apart from a same-named profile', () => {
    render(<RowContextSheet target={{ ...WORKGROUP }} />);
    expect(sheet.props.title).toBe('#alpha');
    expect(sheet.props.subtitle).toBe('workgroup');
  });

  it('sigils a profile with @ under the same name', () => {
    render(<RowContextSheet target={{ kind: 'profile', id: 'alpha', name: 'alpha' }} />);
    expect(sheet.props.title).toBe('@alpha');
    expect(sheet.props.subtitle).toBe('profile');
  });
});

describe('RowContextSheet default profile', () => {
  it('titles the default profile with its display name, not the raw id', () => {
    render(<RowContextSheet target={{ kind: 'profile', id: 'default', name: 'default' }} />);
    expect(sheet.props.title).toBe('@alpi');
  });
});

describe('RowContextSheet profile actions', () => {
  it('offers pin, pause, settings and delete like the desktop row menu', () => {
    render(<RowContextSheet target={PROFILE} onOpenSettings={() => {}} />);
    expect(actionIds()).toEqual(['pin', 'sep-actions', 'pause', 'settings', 'sep-danger', 'delete']);
    expect(action('pause').label).toBe('Pause profile');
    expect(action('settings').label).toBe('Open settings');
    expect(action('delete').label).toBe('Delete profile…');
  });

  it('offers resume for a paused profile', () => {
    render(<RowContextSheet target={{ ...PROFILE, paused: true }} onOpenSettings={() => {}} />);
    expect(action('pause').label).toBe('Resume profile');
    expect(action('pause').icon.props.name).toBe('power');
  });

  it('pauses through the daemon and reseeds the roster', async () => {
    render(<RowContextSheet target={PROFILE} onOpenSettings={() => {}} />);
    await action('pause').onPress();
    expect(h.call).toHaveBeenCalledWith('host.config.set_field', {
      profile: 'agora',
      key: 'paused',
      value: 'true',
    });
    expect(h.call).toHaveBeenCalledWith('host.profile.summaries', {});
    expect(h.seed).toHaveBeenCalledWith('c1', 'host.profile.summaries', {}, { profiles: [] });
    expect(h.toast).toHaveBeenCalledWith({ title: 'Paused', message: '@agora' });
  });

  it('resumes a paused profile instead of pausing it again', async () => {
    render(<RowContextSheet target={{ ...PROFILE, paused: true }} onOpenSettings={() => {}} />);
    await action('pause').onPress();
    expect(h.call).toHaveBeenCalledWith('host.config.set_field', {
      profile: 'agora',
      key: 'paused',
      value: 'false',
    });
  });

  it('says so instead of lying when the daemon refuses', async () => {
    h.call.mockRejectedValueOnce(new Error('forbidden'));
    render(<RowContextSheet target={PROFILE} onOpenSettings={() => {}} />);
    await action('pause').onPress();
    expect(h.toast).toHaveBeenCalledWith({ title: 'Pause failed', message: 'Error: forbidden' });
  });

  it('routes delete to the settings surface with a delete intent, never deleting inline', () => {
    render(<RowContextSheet target={PROFILE} onOpenSettings={() => {}} />);
    action('delete').onPress();
    expect(h.push).toHaveBeenCalledWith('/profile/agora/settings?intent=delete');
    expect(h.call).not.toHaveBeenCalled();
  });

  it('styles delete as the only danger entry', () => {
    render(<RowContextSheet target={PROFILE} onOpenSettings={() => {}} />);
    expect(action('delete').danger).toBe(true);
    expect(action('delete').icon.props.color).toBe('#c14545');
    expect(action('pause').danger).toBeUndefined();
    expect(action('pin').danger).toBeUndefined();
  });
});

describe('RowContextSheet default profile', () => {
  const HOST = { kind: 'profile', id: 'default', name: 'default', label: 'alpi', pinned: true, raw: { name: 'default', is_default: true } };

  it('offers no pin and no delete for the default profile, which the daemon never removes', () => {
    render(<RowContextSheet target={HOST} onOpenSettings={() => {}} />);
    expect(actionIds()).toEqual(['pause', 'settings']);
  });

  it('stays closed for a member and lets go of the long-pressed row', () => {
    h.canAdmin = false;
    const onClose = vi.fn();
    render(<RowContextSheet target={HOST} onClose={onClose} />);
    expect(actionIds()).toEqual([]);
    expect(sheet.props.open).toBe(false);
    expect(onClose).toHaveBeenCalled();
  });
});

describe('RowContextSheet workgroup actions', () => {
  it('offers no pause — only the hub profile pauses, like desktop', () => {
    render(<RowContextSheet target={WORKGROUP} onOpenSettings={() => {}} />);
    expect(actionIds()).toEqual(['pin', 'sep-actions', 'settings', 'sep-danger', 'delete']);
    expect(action('delete').label).toBe('Delete workgroup…');
  });

  it('routes delete to the workgroup settings surface', () => {
    render(<RowContextSheet target={WORKGROUP} onOpenSettings={() => {}} />);
    action('delete').onPress();
    expect(h.push).toHaveBeenCalledWith('/wg/alpha/settings?intent=delete');
  });
});

describe('RowContextSheet member view', () => {
  it('leaves a non-admin pin as the only entry', () => {
    h.canAdmin = false;
    render(<RowContextSheet target={PROFILE} />);
    expect(actionIds()).toEqual(['pin']);
  });

  it('pins from the sheet without touching the daemon', () => {
    const onPin = vi.fn();
    render(<RowContextSheet target={PROFILE} onPin={onPin} />);
    action('pin').onPress();
    expect(onPin).toHaveBeenCalledWith(PROFILE);
    expect(h.call).not.toHaveBeenCalled();
  });
});

describe('InboxRow press contract', () => {
  it('hands the item to onPress so a memo()d row keeps its stable callbacks', () => {
    const onPress = vi.fn();
    const { container } = sidebarRow({ item: WORKGROUP, onPress });
    fireEvent.click(pressable(container));
    expect(onPress).toHaveBeenCalledWith(WORKGROUP);
  });

  it('closes the keyboard a search left open before it opens the row', () => {
    h.dismiss.mockClear();
    let dismissedFirst = null;
    const onPress = vi.fn(() => { dismissedFirst = h.dismiss.mock.calls.length === 1; });
    const { container } = sidebarRow({ item: WORKGROUP, onPress });
    fireEvent.click(pressable(container));
    expect(dismissedFirst).toBe(true);
  });
});

describe('InboxRow Twin on whole pixels', () => {
  const TWIN = { ...PROFILE, shape: 'twin' };
  const drawn = MARK_SIZES.list;
  const sidebarDrawn = MARK_SIZES.row;

  function geometry(container) {
    const row = styleOf(pressable(container));
    const slot = styleOf(container.querySelector('[data-glyph]').parentElement);
    const lines = [...container.querySelectorAll('span[data-style]')].map(styleOf).filter((s) => s.lineHeight);
    const padding = (row.paddingVertical ?? 0) * 2;
    const body = lines.reduce((sum, s) => sum + s.lineHeight, 0) + (lines.length - 1) * space.s1;
    const height = Math.max(row.minHeight, padding + body);
    return { slot, height, lines };
  }

  it('draws the phone row mark at the 40 pt list size and the sidebar row mark at the 24 pt row size', () => {
    expect(drawn).toBe(40);
    expect(sidebarDrawn).toBe(24);
    expect(Number(renderRow({ item: TWIN }).container.querySelector('[data-glyph]').getAttribute('data-size'))).toBe(40);
    cleanup();
    expect(Number(sidebarRow({ item: TWIN }).container.querySelector('[data-glyph]').getAttribute('data-size'))).toBe(24);
  });

  it('centres it on whole x in the glyph column of both rows', () => {
    for (const [container, mark] of [[renderRow({ item: TWIN }).container, drawn], [sidebarRow({ item: TWIN }).container, sidebarDrawn]]) {
      const { slot } = geometry(container);
      expect(slot.width).toBe(mark);
      expect(Number.isInteger((slot.width - mark) / 2)).toBe(true);
    }
    expect(GLYPH_SLOT).toBe(drawn);
  });

  it('centres it on whole y: the phone row is 64 pt and both rows have whole heights', () => {
    for (const [container, mark] of [[renderRow({ item: TWIN }).container, drawn], [sidebarRow({ item: TWIN }).container, sidebarDrawn]]) {
      const { height, lines } = geometry(container);
      for (const line of lines) expect(Number.isInteger(line.lineHeight)).toBe(true);
      expect(Number.isInteger(height)).toBe(true);
      expect(Number.isInteger((height - mark) / 2)).toBe(true);
    }
    expect(geometry(renderRow({ item: TWIN }).container).height).toBe(64);
  });

  it('keeps the sidebar row at the 44 pt tap height', () => {
    const { height } = geometry(sidebarRow({ item: TWIN }).container);
    expect(height).toBe(mobile.tap);
  });
});

describe('InboxRow as a pinned tile', () => {
  it('stacks the 48 pt mark over the name in the name face, with no preview or timestamp', () => {
    const { container } = renderRow({ item: { ...PROFILE, accent: '#3899e2', ts: '4m' }, tile: true });
    expect(container.querySelector('[data-glyph]').getAttribute('data-size')).toBe('48');
    const name = styleOf(screen.getByText('agora'));
    expect(name.fontFamily).toBe('BricolageGrotesque_800ExtraBold');
    expect(name.fontSize).toBe(14);
    expect(screen.queryByText('ready')).toBeNull();
    expect(screen.queryByText('4m')).toBeNull();
    const tile = styleOf(pressable(container));
    expect(tile.alignItems).toBe('center');
    expect(tile.width).toBeUndefined();
    expect(tile.alignSelf).toBe('stretch');
  });

  it('selects with the neutral fill only and keeps the row a labelled button', () => {
    const { container } = renderRow({ item: PROFILE, tile: true, selected: true });
    const tile = pressable(container);
    expect(styleOf(tile).backgroundColor).toBe('#eee');
    expect(styleOf(tile).borderWidth).toBeUndefined();
    expect(tile.getAttribute('aria-label') ?? tile.getAttribute('accessibilityLabel')).toContain('agora');
  });

  it('puts a warning pip on a tile that needs you', () => {
    const { container } = renderRow({ item: { ...PROFILE, activity: { state: 'needs-you' } }, tile: true });
    const pip = container.querySelector('[testid="tile-pip"]') ?? container.querySelector('[data-testid="tile-pip"]');
    expect(pip).toBeTruthy();
    expect(pip.parentElement).not.toBe(pressable(container));
    expect(pip.parentElement.parentElement).toBe(pressable(container));
  });
});
