import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  pathname: '/wg/alpha',
  canGoBack: vi.fn(() => true),
  flatStyle: (style) => Object.assign({}, ...[style].flat(Infinity).filter(Boolean)),
}));

vi.mock('expo-router', () => ({
  usePathname: () => h.pathname,
  useRouter: () => ({ canGoBack: h.canGoBack }),
}));

vi.mock('react-native', () => {
  const View = ({ children, style, accessibilityLabel, ...p }) =>
    React.createElement(
      'div',
      {
        ...p,
        ...(accessibilityLabel ? { 'aria-label': accessibilityLabel } : {}),
        'data-style': JSON.stringify(h.flatStyle(style)),
      },
      children,
    );
  const Text = ({ children, style, numberOfLines, ...p }) =>
    React.createElement('span', { ...p, 'data-style': JSON.stringify(h.flatStyle(style)) }, children);
  const Pressable = ({ children, onPress, hitSlop, style, accessibilityLabel, ...p }) => {
    const body = children instanceof Function ? children({ pressed: false }) : children;
    const resolved = style instanceof Function ? style({ pressed: false }) : style;
    return React.createElement(
      'button',
      {
        type: 'button',
        onClick: onPress,
        'aria-label': accessibilityLabel,
        'data-hitslop': hitSlop === undefined ? undefined : String(hitSlop),
        'data-style': JSON.stringify(h.flatStyle(resolved)),
        ...p,
      },
      body,
    );
  };
  const ScrollView = ({ children, horizontal, directionalLockEnabled, showsHorizontalScrollIndicator, style, contentContainerStyle, ...p }) =>
    React.createElement(
      'div',
      {
        ...p,
        'data-scroll': horizontal ? 'horizontal' : 'vertical',
        'data-locked': String(!!directionalLockEnabled),
        'data-indicator': String(showsHorizontalScrollIndicator !== false),
        'data-style': JSON.stringify(h.flatStyle(style)),
        'data-content-style': JSON.stringify(h.flatStyle(contentContainerStyle)),
      },
      children,
    );
  return { View, Text, Pressable, ScrollView };
});

vi.mock('../../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: {
      ink: '#000', ink2: '#333', ink3: '#666', ink4: '#999',
      bg: '#fff', line: '#eee', line2: '#ddd', selected: '#eee', accent: '#c90',
    },
    fonts: {
      sans: { regular: 'r', medium: 'm', semibold: 's' },
      mono: 'mono',
      monoMedium: 'monoMedium',
    },
    fontSizes: { xs: 11, md: 14, lg: 15, xl: 18, display: 28 },
  }),
}));

vi.mock('../../components/Diamond', () => ({ Diamond: () => React.createElement('span', { 'data-diamond': 'true' }) }));
vi.mock('../../components/Icon', () => ({ Icon: ({ name }) => React.createElement('span', {}, name) }));

import { PaneContext } from '../../nav/PaneContext';
import { CHROME_BTN, PANE_PAD_X, tapSlop } from '../../lib/panes';
import { mobile, space } from '../../theme/tokens';
import { ChatHeader, headerMenuActions } from './ChatHeader';

function inTwoPane(node) {
  return render(<PaneContext.Provider value={{ twoPane: true, side: 'detail' }}>{node}</PaneContext.Provider>);
}

function headerStyle(container) {
  return JSON.parse(container.firstChild.getAttribute('data-style'));
}

function styleOf(el) {
  return JSON.parse(el.getAttribute('data-style'));
}

function labels(actions) {
  return actions.filter((a) => !a.divider).map((a) => a.label);
}

beforeEach(() => {
  h.pathname = '/wg/alpha';
  h.canGoBack.mockClear().mockReturnValue(true);
});

describe('ChatHeader back chevron', () => {
  it('renders the chevron outside any pane provider', () => {
    render(<ChatHeader kind="workgroup" title="#alpha" onBack={() => {}} />);
    expect(screen.getByText('back')).toBeTruthy();
    expect(screen.getByText('#alpha')).toBeTruthy();
  });

  it('drops the chevron at a pane root in two-pane mode', () => {
    inTwoPane(<ChatHeader kind="workgroup" title="#alpha" onBack={() => {}} />);
    expect(screen.queryByText('back')).toBeNull();
    expect(screen.getByText('#alpha')).toBeTruthy();
  });

  it('keeps the chevron on a drilled screen in two-pane mode', () => {
    h.pathname = '/wg/alpha/settings';
    inTwoPane(<ChatHeader kind="workgroup" title="#alpha" onBack={() => {}} />);
    expect(screen.getByText('back')).toBeTruthy();
  });

  it('drops the chevron on a cold deep link with no history', () => {
    h.pathname = '/wg/alpha/settings';
    h.canGoBack.mockReturnValue(false);
    inTwoPane(<ChatHeader kind="workgroup" title="#alpha" onBack={() => {}} />);
    expect(screen.queryByText('back')).toBeNull();
  });

  it('fires onBack when the chevron is pressed on a phone', () => {
    const onBack = vi.fn();
    render(<ChatHeader kind="workgroup" title="#alpha" onBack={onBack} />);
    screen.getByText('back').parentElement.click();
    expect(onBack).toHaveBeenCalledTimes(1);
  });
});

describe('ChatHeader gutter', () => {
  it('keeps one edge whatever the pane mode', () => {
    const two = inTwoPane(<ChatHeader kind="workgroup" title="#alpha" />);
    const paneEdge = headerStyle(two.container).paddingHorizontal;
    two.unmount();
    const { container } = render(<ChatHeader kind="workgroup" title="#alpha" />);
    expect(headerStyle(container).paddingHorizontal).toBe(paneEdge);
    expect(paneEdge).toBe(PANE_PAD_X);
  });
});

describe('ChatHeader descenders', () => {
  it.each([
    ['two-pane', inTwoPane],
    ['the phone', render],
  ])('leaves the title room for a descender on %s — Android clips what web lets overflow', (_, mount) => {
    mount(<ChatHeader kind="profile" title="lingo" />);
    const style = JSON.parse(screen.getByText('lingo').getAttribute('data-style'));
    expect(style.lineHeight).toBeGreaterThan(style.fontSize);
  });
});

describe('ChatHeader title scale', () => {
  it('goes display-size under two panes', () => {
    const { container } = inTwoPane(<ChatHeader kind="workgroup" title="#alpha" />);
    expect(styleOf(screen.getByText('#alpha')).fontSize).toBe(28);
    expect(headerStyle(container).paddingTop).not.toBe(space.s11);
  });

  it('stays compact on the phone', () => {
    const { container } = render(<ChatHeader kind="workgroup" title="#alpha" />);
    expect(styleOf(screen.getByText('#alpha')).fontSize).toBe(18);
    expect(headerStyle(container).paddingTop).toBe(space.s2);
    expect(headerStyle(container).paddingBottom).toBe(space.s3);
  });
});

describe('ChatHeader box', () => {
  it('spends the same trimmed padding whatever the pane mode', () => {
    const two = inTwoPane(<ChatHeader kind="workgroup" title="#alpha" />);
    const tablet = headerStyle(two.container);
    two.unmount();
    const { container } = render(<ChatHeader kind="workgroup" title="#alpha" />);
    const phone = headerStyle(container);
    expect(phone.paddingTop).toBe(tablet.paddingTop);
    expect(phone.paddingBottom).toBe(tablet.paddingBottom);
    expect(phone.paddingTop).toBeLessThan(space.s3);
  });

  it('lets the title row set the height instead of a tap-sized control', () => {
    render(<ChatHeader kind="profile" title="doc" onBack={() => {}} onPickSession={() => {}} onMore={() => {}} />);
    for (const label of ['Back', 'Sessions', 'More']) {
      expect(styleOf(screen.getByLabelText(label)).height).toBeLessThan(mobile.tap);
    }
  });
});

describe('ChatHeader accent stripe', () => {
  it('pins a stripe to the bottom-left hairline under two panes', () => {
    const { container } = inTwoPane(<ChatHeader kind="workgroup" title="#alpha" accent="#abc123" />);
    const stripe = [...container.querySelectorAll('div')]
      .map(styleOf)
      .find((s) => s.position === 'absolute');
    expect(stripe).toBeTruthy();
    expect(stripe.backgroundColor).toBe('#abc123');
    expect(stripe.left).toBe(PANE_PAD_X);
    expect(stripe.bottom).toBe(-0.5);
    expect(stripe.width).toBe(space.s11);
  });

  it('draws the same accent notch on the phone, like the sidebar and desktop', () => {
    const { container } = render(<ChatHeader kind="workgroup" title="#alpha" accent="#abc123" />);
    const stripe = [...container.querySelectorAll('div')]
      .map(styleOf)
      .find((s) => s.position === 'absolute');
    expect(stripe.backgroundColor).toBe('#abc123');
    expect(stripe.left).toBe(PANE_PAD_X);
    expect(stripe.bottom).toBe(-0.5);
    expect(stripe.width).toBe(space.s11);
  });

  it('seats the session and more controls on the title line, so the meta strip keeps the full width', () => {
    const { container } = inTwoPane(
      <ChatHeader kind="profile" title="etxea" onPickSession={() => {}} onMore={() => {}} />,
    );
    const title = screen.getByText('etxea');
    const clock = screen.getByLabelText('Sessions');
    expect(title.parentElement.contains(clock)).toBe(true);
    expect(styleOf(container.firstChild).alignItems).toBe('flex-start');
  });
});

describe('ChatHeader session trigger', () => {
  it('keeps the same icon-only trigger under two panes, never a labelled control', () => {
    inTwoPane(<ChatHeader kind="profile" title="doc" onPickSession={() => {}} />);
    expect(screen.getByText('clock')).toBeTruthy();
    expect(screen.queryByText('Sessions')).toBeNull();
    expect(screen.getByLabelText('Sessions')).toBeTruthy();
  });

  it('keeps the icon-only trigger on the phone', () => {
    render(<ChatHeader kind="profile" title="doc" onPickSession={() => {}} />);
    expect(screen.queryByText('Sessions')).toBeNull();
    expect(screen.getByText('clock')).toBeTruthy();
    expect(screen.getByLabelText('Sessions')).toBeTruthy();
  });

  it('fires onPickSession from either trigger', () => {
    const onPickSession = vi.fn();
    const phone = render(<ChatHeader kind="profile" title="doc" onPickSession={onPickSession} />);
    screen.getByLabelText('Sessions').click();
    phone.unmount();
    inTwoPane(<ChatHeader kind="profile" title="doc" onPickSession={onPickSession} />);
    screen.getByLabelText('Sessions').click();
    expect(onPickSession).toHaveBeenCalledTimes(2);
  });
});

describe('ChatHeader button size', () => {
  const slopped = (label) => {
    const el = screen.getByLabelText(label);
    const style = styleOf(el);
    const slop = Number(el.getAttribute('data-hitslop'));
    return { style, slop };
  };

  it('draws every header control at the chrome size with 44pt of touch around it', () => {
    render(
      <ChatHeader kind="profile" title="doc" onBack={() => {}} onPickSession={() => {}} onMore={() => {}} />,
    );
    for (const label of ['Back', 'Sessions', 'More']) {
      const { style, slop } = slopped(label);
      expect(style.width).toBe(CHROME_BTN);
      expect(style.height).toBe(CHROME_BTN);
      expect(slop).toBe(tapSlop(CHROME_BTN));
      expect(style.height + slop * 2).toBeGreaterThanOrEqual(mobile.tap);
    }
  });

  it('keeps the two-pane controls on the very same box', () => {
    inTwoPane(<ChatHeader kind="profile" title="doc" onPickSession={() => {}} onMore={() => {}} />);
    for (const label of ['Sessions', 'More']) {
      const { style, slop } = slopped(label);
      expect(style.height).toBe(CHROME_BTN);
      expect(style.height + slop * 2).toBeGreaterThanOrEqual(mobile.tap);
    }
  });
});

describe('ChatHeader meta row', () => {
  const meta = (
    <>
      <span data-meta="model">deepseek-v4-flash-0731</span>
      <span data-meta="context">20K/200K</span>
      <span data-meta="cost">$0.50/$2.00</span>
    </>
  );

  function scroller() {
    return document.querySelector('[data-scroll]');
  }

  it('scrolls the meters horizontally with no visible indicator', () => {
    render(<ChatHeader kind="profile" title="doc" meta={meta} />);
    expect(scroller().getAttribute('data-scroll')).toBe('horizontal');
    expect(scroller().getAttribute('data-indicator')).toBe('false');
    expect(scroller().querySelectorAll('[data-meta]').length).toBe(3);
  });

  it('locks the pan to one axis so the transcript keeps its vertical scroll', () => {
    render(<ChatHeader kind="profile" title="doc" meta={meta} />);
    expect(scroller().getAttribute('data-locked')).toBe('true');
  });

  it('neither stretches nor centres when the meters are narrower than the pane', () => {
    inTwoPane(<ChatHeader kind="profile" title="doc" meta={meta} />);
    const outer = JSON.parse(scroller().getAttribute('data-style'));
    const content = JSON.parse(scroller().getAttribute('data-content-style'));
    expect(outer.flexGrow).toBe(0);
    expect(content.flexGrow).toBeUndefined();
    expect(content.justifyContent).toBeUndefined();
    expect(content.flexDirection).toBe('row');
    expect(content.gap).toBe(space.s6);
  });

  it('leaves a plain string meta unscrolled', () => {
    render(<ChatHeader kind="profile" title="doc" meta="profile · not found" />);
    expect(scroller()).toBeNull();
    expect(screen.getByText('profile · not found')).toBeTruthy();
  });

  it('keeps Sessions and the menu out of the scroller on the phone', () => {
    const onPickSession = vi.fn();
    const onMore = vi.fn();
    render(
      <ChatHeader kind="profile" title="doc" meta={meta} onPickSession={onPickSession} onMore={onMore} />,
    );
    expect(scroller().querySelector('[aria-label="Sessions"]')).toBeNull();
    expect(scroller().querySelector('[aria-label="More"]')).toBeNull();
    screen.getByLabelText('Sessions').click();
    screen.getByLabelText('More').click();
    expect(onPickSession).toHaveBeenCalledTimes(1);
    expect(onMore).toHaveBeenCalledTimes(1);
  });

  it('keeps Sessions and the menu out of the scroller under two panes', () => {
    const onPickSession = vi.fn();
    const onMore = vi.fn();
    inTwoPane(
      <ChatHeader kind="profile" title="doc" meta={meta} onPickSession={onPickSession} onMore={onMore} />,
    );
    expect(scroller().querySelector('[aria-label="Sessions"]')).toBeNull();
    expect(scroller().querySelector('[aria-label="More"]')).toBeNull();
    screen.getByLabelText('Sessions').click();
    screen.getByLabelText('More').click();
    expect(onPickSession).toHaveBeenCalledTimes(1);
    expect(onMore).toHaveBeenCalledTimes(1);
  });

  it('lets the controls keep their width while the meters take the rest', () => {
    const { container } = render(
      <ChatHeader kind="profile" title="doc" meta={meta} onPickSession={() => {}} onMore={() => {}} />,
    );
    const actions = [...container.querySelectorAll('div')]
      .find((el) => el.querySelector('[aria-label="More"]') && styleOf(el).flexShrink === 0);
    expect(actions).toBeTruthy();
    expect(actions.querySelector('[data-scroll]')).toBeNull();
  });
});

describe('headerMenuActions', () => {
  const ALL = {
    onOpenSettings: vi.fn(),
    onTogglePause: vi.fn(),
    onToggleAutoRead: vi.fn(),
    onOpenSkills: vi.fn(),
    onOpenMemory: vi.fn(),
    onOpenTools: vi.fn(),
    onOpenSchedule: vi.fn(),
    onRefresh: vi.fn(),
  };

  it('builds the eight desktop entries in order', () => {
    expect(labels(headerMenuActions(ALL))).toEqual([
      'Profile settings',
      'Pause profile',
      'Auto-read replies',
      'Skills',
      'Memory',
      'Tools',
      'Schedule',
      'Refresh thread',
    ]);
  });

  it('carries no keyboard-shortcut hints', () => {
    const serialized = JSON.stringify(headerMenuActions(ALL).map((a) => a.label ?? ''));
    expect(serialized).not.toMatch(/⌘|⇧|Kbd|kbd/);
  });

  it('separates the brain group and the refresh tail', () => {
    const shape = headerMenuActions(ALL).map((a) => (a.divider ? '—' : a.id));
    expect(shape).toEqual([
      'settings', 'pause', 'auto-read',
      '—', 'skills', 'memory', 'tools', 'schedule',
      '—', 'refresh',
    ]);
  });

  it('offers Resume with a play glyph once paused', () => {
    const paused = headerMenuActions({ ...ALL, paused: true });
    const entry = paused.find((a) => a.id === 'pause');
    expect(entry.label).toBe('Resume profile');
    expect(entry.icon.props.name).toBe('play');
    expect(labels(paused)).toContain('Resume profile');
  });

  it('offers Pause with a pause glyph while running', () => {
    const entry = headerMenuActions(ALL).find((a) => a.id === 'pause');
    expect(entry.label).toBe('Pause profile');
    expect(entry.icon.props.name).toBe('pause');
  });

  it('shows the auto-read state as on or off', () => {
    expect(headerMenuActions({ ...ALL, autoRead: true }).find((a) => a.id === 'auto-read').detail).toBe('on');
    expect(headerMenuActions({ ...ALL, autoRead: false }).find((a) => a.id === 'auto-read').detail).toBe('off');
  });

  it('names the workgroup noun and drops the brain group', () => {
    const actions = headerMenuActions({
      noun: 'workgroup',
      paused: true,
      onOpenSettings: ALL.onOpenSettings,
      onTogglePause: ALL.onTogglePause,
      onToggleAutoRead: ALL.onToggleAutoRead,
      onRefresh: ALL.onRefresh,
    });
    expect(labels(actions)).toEqual([
      'Workgroup settings',
      'Resume workgroup',
      'Auto-read replies',
      'Refresh thread',
    ]);
  });

  it('never opens with a divider when the head group is gone', () => {
    const actions = headerMenuActions({ onRefresh: ALL.onRefresh });
    expect(actions.map((a) => a.id)).toEqual(['refresh']);
  });

  it('wires each entry to the handler it was given', () => {
    const actions = headerMenuActions(ALL);
    for (const a of actions.filter((x) => !x.divider)) a.onPress();
    for (const fn of Object.values(ALL)) expect(fn).toHaveBeenCalledTimes(1);
  });
});
