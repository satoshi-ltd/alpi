import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  push: vi.fn(),
  call: vi.fn(async () => ({ profiles: [] })),
  toast: vi.fn(),
  seed: vi.fn(),
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
  const Pressable = ({ children, style, android_ripple, onPress, onLongPress, accessibilityLabel, ...p }) =>
    React.createElement(
      'button',
      {
        type: 'button',
        onClick: onPress,
        ...(accessibilityLabel ? { 'aria-label': accessibilityLabel } : {}),
        'data-style': JSON.stringify(h.flat(style)),
        ...p,
      },
      children,
    );
  return { View, Text, Pressable, StyleSheet: { create: (s) => s } };
});

vi.mock('../../theme/ThemeContext', async () => {
  const tokens = await import('../../theme/tokens');
  return {
    useTheme: () => ({
      colors: {
        ink: '#000', ink2: '#333', ink3: '#666', ink4: '#999',
        accent: '#b8954a', bg: '#fff', danger: '#c14545', hover: '#eee', selected: '#eee',
      },
      fonts: {
        sans: {
          regular: 'Inter_400Regular',
          medium: 'Inter_500Medium',
          semibold: 'Inter_600SemiBold',
          bold: 'Inter_700Bold',
        },
        mono: 'JetBrainsMono_400Regular',
        monoMedium: 'JetBrainsMono_500Medium',
        monoSemibold: 'JetBrainsMono_600SemiBold',
      },
      alpha: { muted: 0.55 },
      fontSizes: tokens.fontSizes,
    }),
  };
});

vi.mock('../../components/Dot', () => ({ Dot: () => React.createElement('span', { 'data-dot': 'true' }) }));
vi.mock('../../components/Glyph', () => ({
  Glyph: ({ kind }) => React.createElement('span', { 'data-glyph': kind }),
}));
vi.mock('../../components/Icon', () => ({
  Icon: ({ name, color }) => React.createElement('span', { 'data-icon': name, 'data-color': color }),
}));
vi.mock('./Pip', () => ({ Pip: ({ kind }) => React.createElement('span', { 'data-pip': kind }) }));

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
import { InboxRow } from './InboxRow';
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

  it('rounds the row into an inset pill so the selection reads as a nav item', () => {
    const { container } = sidebarRow({ item: WORKGROUP });
    const style = styleOf(pressable(container));
    expect(style.borderRadius).toBe(radii.md);
    expect(style.marginHorizontal).toBe(space.s5);
    expect(style.minHeight).toBe(mobile.tap);
  });

  it('paints the selection on the pill', () => {
    const { container } = sidebarRow({ item: WORKGROUP, selected: true });
    expect(styleOf(pressable(container)).backgroundColor).toBe('#eee');
  });

  it('keeps the phone row two-line, full-bleed and square', () => {
    const { container } = renderRow({ item: WORKGROUP });
    const style = styleOf(pressable(container));
    expect(container.textContent).toContain('status?');
    expect(style.borderRadius).toBeUndefined();
    expect(style.marginHorizontal).toBeUndefined();
    expect(style.minHeight).toBe(64);
  });
});

describe('InboxRow name weight ladder', () => {
  const nameFont = (props, pane) => {
    renderRow(props, pane);
    return styleOf(screen.getByText('alpha')).fontFamily;
  };

  it('steps resting → selected → unread in the sidebar', () => {
    const pane = { twoPane: true, side: 'list' };
    expect(nameFont({ item: WORKGROUP }, pane)).toBe('Inter_400Regular');
    cleanup();
    expect(nameFont({ item: WORKGROUP, selected: true }, pane)).toBe('Inter_500Medium');
    cleanup();
    expect(nameFont({ item: { ...WORKGROUP, unread: true } }, pane)).toBe('Inter_600SemiBold');
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
    expect(nameFont({ item: WORKGROUP })).toBe('Inter_600SemiBold');
    cleanup();
    expect(nameFont({ item: { ...WORKGROUP, unread: true } })).toBe('Inter_700Bold');
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
    expect(styleOf(screen.getByText('alpha')).fontFamily).toBe('Inter_700Bold');
    expect(styleOf(screen.getByText('3m')).fontFamily).toBe('JetBrainsMono_600SemiBold');
    expect(styleOf(screen.getByText('3m')).color).toBe('#000');
  });

  it('rests the timestamp on a read row', () => {
    renderRow({ item: WORKGROUP });
    expect(styleOf(screen.getByText('3m')).fontFamily).toBe('JetBrainsMono_500Medium');
    expect(styleOf(screen.getByText('3m')).color).toBe('#666');
  });

  it('holds the preview at one ink either way — unread no longer tints it', () => {
    renderRow({ item: WORKGROUP });
    expect(styleOf(screen.getByText('status?')).color).toBe('#666');
    cleanup();
    renderRow({ item: { ...WORKGROUP, unread: true } });
    expect(styleOf(screen.getByText('status?')).color).toBe('#666');
  });

  it('announces unread now that no dot carries the label', () => {
    renderRow({ item: { ...WORKGROUP, unread: true } });
    expect(screen.getByLabelText('alpha unread')).toBeTruthy();
    cleanup();
    const { container } = renderRow({ item: WORKGROUP });
    expect(container.querySelector('[aria-label]')).toBeNull();
  });
});

describe('RowContextSheet title', () => {
  it('keeps the hash so a workgroup reads apart from a same-named profile', () => {
    render(<RowContextSheet target={{ ...WORKGROUP }} />);
    expect(sheet.props.title).toBe('#alpha');
    expect(sheet.props.subtitle).toBe('WORKGROUP');
  });

  it('sigils a profile with @ under the same name', () => {
    render(<RowContextSheet target={{ kind: 'profile', id: 'alpha', name: 'alpha' }} />);
    expect(sheet.props.title).toBe('@alpha');
    expect(sheet.props.subtitle).toBe('PROFILE');
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
});
