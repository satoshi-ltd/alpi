import React from 'react';
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  layout: null,
  fontScale: 1,
  flat: (style) => [style].flat(Infinity).filter(Boolean).reduce((acc, s) => ({ ...acc, ...s }), {}),
}));

vi.mock('react-native', () => {
  const View = ({ children, style, onLayout, ...p }) => {
    if (onLayout) h.layout = onLayout;
    return React.createElement(
      'div',
      { ...p, 'data-style': JSON.stringify(h.flat(style)), ...(h.flat(style).position ? { 'data-pos': h.flat(style).position } : {}) },
      children,
    );
  };
  const Text = ({ children, style, ...p }) => React.createElement('span', { ...p, 'data-style': JSON.stringify(h.flat(style)) }, children);
  const Pressable = ({ children, style, onPress, accessibilityLabel, ...p }) =>
    React.createElement(
      'button',
      { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel, ...p },
      typeof children === 'function' ? children({ pressed: false }) : children,
    );
  return { View, Text, Pressable };
});

vi.mock('expo-constants', () => ({ default: { expoConfig: { version: '0.9.0' } } }));

vi.mock('../../components/Icon', () => ({ Icon: ({ name, color }) => React.createElement('span', { 'data-icon': name, 'data-color': color }) }));

vi.mock('../../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { ink2: '#333', ink3: '#666', ink4: '#999', line: '#eee', selected: '#eaeaea', danger: '#c00', warning: '#e08a3c', warningText: '#8a5a0a' },
    fonts: { sans: { medium: 'm', semibold: 's' }, mono: 'monoFace', monoMedium: 'monoMedium' },
    fontSizes: { xs: 11, sm: 12 },
    chromeScale: 1.3,
    fontScale: h.fontScale,
    pref: h.pref,
    setMode: h.setMode,
  }),
}));

import { CHROME_H } from '../../lib/panes';
import { dotScale, mobile } from '../../theme/tokens';
import { PaneContext } from '../../nav/PaneContext';
import { ICON_ROLES } from '../../../../common/iconRoles.mjs';
import { ENTRY_INSET_X, LABEL_ROOM, ShellFooter } from './ShellFooter';
import { space } from '../../theme/tokens';

const settings = () => screen.getByLabelText('Settings');
const bell = (unread = 0) => screen.getByLabelText(unread > 0 ? `Notifications · ${unread} unread` : 'Notifications');
const follows = (a, b) => Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);

const ROOT = join(import.meta.dirname, '..', '..', '..');
const source = (path) => readFileSync(join(ROOT, path), 'utf8');

describe('ShellFooter entries', () => {
  it('runs Settings, then notifications, and carries no version', () => {
    render(<ShellFooter unread={0} onNotificationsPress={() => {}} onSettingsPress={() => {}} />);
    expect(follows(settings(), bell())).toBe(true);
    expect(screen.queryByText(/^v\d/)).toBeNull();
    expect(screen.queryByText('0.9.0')).toBeNull();
  });

  it('fires the handler of the entry that was pressed', () => {
    const onSettingsPress = vi.fn();
    const onNotificationsPress = vi.fn();
    render(<ShellFooter unread={0} onNotificationsPress={onNotificationsPress} onSettingsPress={onSettingsPress} />);
    fireEvent.click(settings());
    expect(onSettingsPress).toHaveBeenCalledTimes(1);
    expect(onNotificationsPress).not.toHaveBeenCalled();
    fireEvent.click(bell());
    expect(onNotificationsPress).toHaveBeenCalledTimes(1);
  });

  it('marks unread on the bell glyph with a dot and no digits, keeping the exact count in the label', () => {
    const { rerender } = render(<ShellFooter unread={7} onNotificationsPress={() => {}} onSettingsPress={() => {}} />);
    const wrap = bell(7).querySelector('[data-pos="relative"]');
    expect(wrap.querySelector('[data-icon="bell"]')).toBeTruthy();
    const dot = wrap.querySelector('[testID="dot-anchor"]');
    expect(dot).toBeTruthy();
    expect(dot.textContent).toBe('');
    expect(bell(7).querySelector('[testID="badge-anchor"]')).toBeNull();

    rerender(<ShellFooter unread={150} onNotificationsPress={() => {}} onSettingsPress={() => {}} />);
    expect(bell(150).querySelector('[testID="dot-anchor"]')).toBeTruthy();
    expect(bell(150).textContent).toBe('Notifications');
    expect(bell(150).getAttribute('aria-label')).toBe('Notifications · 150 unread');
  });

  it('draws the dot flat in danger at the dotScale size, sitting clear of the bell shoulder at the glyph top-right corner without intercepting touches', () => {
    render(<ShellFooter unread={3} onNotificationsPress={() => {}} onSettingsPress={() => {}} />);
    const dot = bell(3).querySelector('[testID="dot-anchor"]');
    const at = JSON.parse(dot.getAttribute('data-style'));
    expect(dot.getAttribute('pointer-events')).toBe('none');
    expect(at.backgroundColor).toBe('#c00');
    expect(at.width).toBe(dotScale.md);
    expect(at.height).toBe(dotScale.md);
    expect(at.borderRadius).toBe(dotScale.md / 2);
    expect(at.position).toBe('absolute');
    expect(at.top).toBe(-4);
    expect(at.right).toBe(-4);
    expect(at.borderWidth).toBeUndefined();
    expect(at.shadowColor).toBeUndefined();
    expect(at.elevation).toBeUndefined();
  });

  it('draws no dot at zero unread', () => {
    render(<ShellFooter unread={0} onNotificationsPress={() => {}} onSettingsPress={() => {}} />);
    expect(bell().querySelector('[testID="dot-anchor"]')).toBeNull();
    expect(bell().querySelector('[data-pos="absolute"]')).toBeNull();
  });

  it('hides the bell from a reader with no notifications to open, leaving Settings live', () => {
    render(<ShellFooter unread={4} onNotificationsPress={null} onSettingsPress={() => {}} />);
    expect(screen.queryByLabelText('Notifications')).toBeNull();
    expect(screen.queryByLabelText('Notifications · 4 unread')).toBeNull();
    expect(settings()).toBeTruthy();
  });
});

describe('ShellFooter activity entry', () => {
  const activity = (n = 0) => screen.getByLabelText(n > 0 ? `Activity · ${n} need you` : 'Activity');

  it('sits after notifications and opens the activity screen', () => {
    const onActivityPress = vi.fn();
    render(<ShellFooter unread={0} onNotificationsPress={() => {}} onSettingsPress={() => {}} onActivityPress={onActivityPress} />);
    expect(follows(bell(), activity())).toBe(true);
    fireEvent.click(activity());
    expect(onActivityPress).toHaveBeenCalledTimes(1);
  });

  it('marks needs-you on Activity with the same digitless dot as the bell, ink-2 glyphs', () => {
    render(<ShellFooter unread={3} needsYou={2} onNotificationsPress={() => {}} onSettingsPress={() => {}} onActivityPress={() => {}} />);
    const dot = activity(2).querySelector('[testID="dot-anchor"]');
    expect(dot.textContent).toBe('');
    expect(dot.getAttribute('pointer-events')).toBe('none');
    expect(activity(2).querySelector('[testID="badge-anchor"]')).toBeNull();
    const at = JSON.parse(dot.getAttribute('data-style'));
    expect(at).toMatchObject({ position: 'absolute', top: -4, right: -4, backgroundColor: '#c00', width: dotScale.md, height: dotScale.md });
    expect(dot.parentElement.querySelector('[data-icon]')).toBeTruthy();
    expect(activity(2).getAttribute('aria-label')).toBe('Activity · 2 need you');
    expect(activity(2).querySelector('[data-icon]').getAttribute('data-color')).toBe('#333');
  });

  it('draws no Activity dot at zero and caps nothing: the count lives in the label', () => {
    const { rerender } = render(<ShellFooter needsYou={0} onSettingsPress={() => {}} onActivityPress={() => {}} />);
    expect(activity().querySelector('[testID="dot-anchor"]')).toBeNull();
    rerender(<ShellFooter needsYou={250} onSettingsPress={() => {}} onActivityPress={() => {}} />);
    expect(activity(250).querySelector('[testID="dot-anchor"]')).toBeTruthy();
    expect(activity(250).textContent).toBe('Activity');
  });

  it('stays out of the footer on a daemon without the activity verb', () => {
    render(<ShellFooter onSettingsPress={() => {}} onActivityPress={null} needsYou={4} />);
    expect(screen.queryByLabelText(/^Activity/)).toBeNull();
  });

  it('gives every entry a 44 pt target and a button role, and caps its text at the chrome scale', () => {
    render(<ShellFooter unread={1} onNotificationsPress={() => {}} onSettingsPress={() => {}} onActivityPress={() => {}} />);
    for (const entry of [settings(), bell(1), activity()]) {
      expect(entry.getAttribute('accessibilityRole')).toBe('button');
      expect(Number(entry.getAttribute('hitSlop')) * 2 + 36).toBe(mobile.tap);
    }
    expect(screen.getByText('Settings').getAttribute('maxFontSizeMultiplier')).toBe('1.3');
  });
});

describe('ShellFooter box', () => {
  it('stands one touch target tall', () => {
    const { container } = render(<ShellFooter onSettingsPress={() => {}} />);
    expect(CHROME_H).toBe(mobile.tap);
    expect(JSON.parse(container.firstChild.getAttribute('data-style')).height).toBe(mobile.tap);
  });

  it('takes its height from the shared chrome metric the composer reads too', () => {
    const text = source('src/features/shell/ShellFooter.jsx');
    expect(text).toMatch(/import \{ CHROME_H \} from '.*lib\/panes'/);
    expect(text).toMatch(/height: CHROME_H/);
    expect(text).not.toMatch(/FOOTER_H/);
  });

  it('adds no bottom inset of its own — the container SafeAreaView supplies it', () => {
    const { container } = render(<ShellFooter onSettingsPress={() => {}} />);
    const style = JSON.parse(container.firstChild.getAttribute('data-style'));
    expect(style.paddingBottom).toBeUndefined();
    expect(style.paddingVertical).toBeUndefined();
    expect(source('src/features/shell/ShellFooter.jsx')).not.toMatch(/safe-area|SafeArea|useSafeAreaInsets/);
  });
});

const SURFACES = ['app/index.jsx', 'src/features/shell/SidebarPane.jsx'];

describe('one footer, two surfaces', () => {
  it.each(SURFACES)('%s renders the shared footer instead of its own', (path) => {
    const text = source(path);
    expect(text).toMatch(/import \{ ShellFooter \} from '.*ShellFooter'/);
    expect(text).toMatch(/<ShellFooter\b/);
    expect(text).not.toMatch(/function \w*Footer\s*\(/);
  });

  it.each(SURFACES)('%s wires the same three entries into it', (path) => {
    const text = source(path);
    expect(text).toMatch(/unread=\{unreadCount\}/);
    expect(text).toMatch(/onNotificationsPress=\{canAdmin \?/);
    expect(text).toMatch(/onSettingsPress=\{openSettings\}/);
  });
});

describe('one notifications destination', () => {
  it.each(SURFACES)('%s sends the bell to the route through openVerb, never to a sheet', (path) => {
    const text = source(path);
    expect(text).toMatch(/openVerb\(\{ twoPane[^)]*\}\)\]\(OUTPUTS_PATH\)/);
    expect(text).toMatch(/onNotificationsPress=\{canAdmin \? openNotifications : null\}/);
    expect(text).not.toContain('NotificationsSheet');
    expect(text).not.toMatch(/['"]\/outputs['"]/);
  });

  it('keeps no notifications sheet in the tree', () => {
    expect(existsSync(join(ROOT, 'src/features/shell/NotificationsSheet.jsx'))).toBe(false);
    expect(existsSync(join(ROOT, 'src/features/shell/NotificationsSheet.test.jsx'))).toBe(false);
  });
});

describe('ShellFooter icon roles', () => {
  it('draws settings, notifications and activity from the shared icon roles', () => {
    render(<ShellFooter unread={1} needsYou={1} onNotificationsPress={() => {}} onSettingsPress={() => {}} onActivityPress={() => {}} />);
    expect(ICON_ROLES).toMatchObject({ settings: 'settings', notifications: 'bell', activity: 'activity' });
    expect(settings().querySelector('[data-icon]').getAttribute('data-icon')).toBe(ICON_ROLES.settings);
    expect(bell(1).querySelector('[data-icon]').getAttribute('data-icon')).toBe(ICON_ROLES.notifications);
    expect(screen.getByLabelText('Activity · 1 need you').querySelector('[data-icon]').getAttribute('data-icon')).toBe(ICON_ROLES.activity);
  });

  it.each(['src/features/shell/ShellFooter.jsx', 'src/features/shell/ActivityList.jsx'])('%s names no role icon by hand', (path) => {
    const text = source(path);
    expect(text).toMatch(/ICON_ROLES/);
    expect(text).not.toMatch(/name="(gear|settings|bell|activity)"|icon: '(gear|settings|bell|activity)'/);
  });
});

describe('ShellFooter labels', () => {
  it('names every entry in words under its glyph', () => {
    render(<ShellFooter unread={1} needsYou={1} onNotificationsPress={() => {}} onSettingsPress={() => {}} onActivityPress={() => {}} />);
    for (const word of ['Settings', 'Notifications', 'Activity']) expect(screen.getByText(word)).toBeTruthy();
  });

  it('cycles the theme through setMode, shows the mode and announces it', () => {
    h.setMode = vi.fn();
    h.pref = 'system';
    const { rerender } = render(<ShellFooter onSettingsPress={() => {}} />);
    const entry = () => screen.getByLabelText(/^Theme:/);
    expect(entry().getAttribute('aria-label')).toBe('Theme: System. Switch to Light');
    expect(entry().querySelector('[data-icon]').getAttribute('data-icon')).toBe('sun-moon');
    fireEvent.click(entry());
    expect(h.setMode).toHaveBeenLastCalledWith('light');
    h.pref = 'light';
    rerender(<ShellFooter onSettingsPress={() => {}} />);
    expect(entry().querySelector('[data-icon]').getAttribute('data-icon')).toBe('sun');
    expect(screen.getByText('Light')).toBeTruthy();
    fireEvent.click(entry());
    expect(h.setMode).toHaveBeenLastCalledWith('dark');
    h.pref = 'dark';
    rerender(<ShellFooter onSettingsPress={() => {}} />);
    expect(entry().querySelector('[data-icon]').getAttribute('data-icon')).toBe('moon');
    fireEvent.click(entry());
    expect(h.setMode).toHaveBeenLastCalledWith('system');
  });

  it('keeps the theme entry on the two-pane layout too', () => {
    h.pref = 'dark';
    render(
      <PaneContext.Provider value={{ twoPane: true, side: 'list', sidebarOpen: true, toggleSidebar() {} }}>
        <ShellFooter onSettingsPress={() => {}} />
      </PaneContext.Provider>,
    );
    expect(screen.getByLabelText(/^Theme: Dark/).getAttribute('hitSlop')).toBeTruthy();
  });
});

describe('ShellFooter two panes', () => {
  const pane = { twoPane: true, side: 'list', sidebarOpen: true, toggleSidebar() {} };
  const FULL = { unread: 1, needsYou: 2, onNotificationsPress: () => {}, onSettingsPress: () => {}, onActivityPress: () => {} };

  it('draws icon-only entries at the 300 pt list width, keeping labels, targets and dots', () => {
    h.layout = null;
    render(
      <PaneContext.Provider value={pane}>
        <ShellFooter {...FULL} />
      </PaneContext.Provider>,
    );
    act(() => h.layout({ nativeEvent: { layout: { width: 300, height: 44 } } }));
    for (const word of ['Settings', 'Notifications', 'Activity']) expect(screen.queryByText(word)).toBeNull();
    expect(settings().textContent).toBe('');
    expect(bell(1).querySelector('[testID="dot-anchor"]')).toBeTruthy();
    expect(screen.getByLabelText('Activity · 2 need you').querySelector('[testID="dot-anchor"]')).toBeTruthy();
    for (const entry of [settings(), bell(1), screen.getByLabelText('Activity · 2 need you'), screen.getByLabelText(/^Theme:/)]) {
      expect(Number(entry.getAttribute('hitSlop')) * 2 + 36).toBe(mobile.tap);
    }
  });

  it('shows the bare version as plain mono ink3 text at the right, not focusable, one inset from the edge like the first icon', () => {
    h.layout = null;
    render(
      <PaneContext.Provider value={pane}>
        <ShellFooter {...FULL} />
      </PaneContext.Provider>,
    );
    act(() => h.layout({ nativeEvent: { layout: { width: 300, height: 44 } } }));
    const version = screen.getByText('0.9.0');
    expect(version.tagName).toBe('SPAN');
    expect(version.closest('button')).toBeNull();
    expect(version.getAttribute('accessibilityRole')).toBe('text');
    expect(version.getAttribute('numberOfLines')).toBe('1');
    expect(version.getAttribute('maxFontSizeMultiplier')).toBe('1.3');
    const at = JSON.parse(version.getAttribute('data-style'));
    expect(at).toMatchObject({ fontFamily: 'monoFace', fontSize: 11, color: '#666', flexShrink: 0 });
    const box = JSON.parse(version.parentElement.getAttribute('data-style'));
    expect(box.paddingRight).toBe((mobile.tap - 16) / 2);
  });

  it.each([280, 300])('fits four 44 pt targets and the version at %i pt, even at the largest text size', (width) => {
    h.fontScale = 1.3;
    h.layout = null;
    render(
      <PaneContext.Provider value={pane}>
        <ShellFooter {...FULL} />
      </PaneContext.Provider>,
    );
    act(() => h.layout({ nativeEvent: { layout: { width, height: 44 } } }));
    expect(screen.getByText('0.9.0')).toBeTruthy();
    expect(width - 2 * space.s5 - 4 * mobile.tap).toBeGreaterThanOrEqual(0.6 * 11 * 1.3 * 5 + 14 + space.s5);
    h.fontScale = 1;
  });

  it('hides the version before it would crowd the targets', () => {
    h.layout = null;
    render(
      <PaneContext.Provider value={pane}>
        <ShellFooter {...FULL} />
      </PaneContext.Provider>,
    );
    act(() => h.layout({ nativeEvent: { layout: { width: 240, height: 44 } } }));
    expect(screen.queryByText('0.9.0')).toBeNull();
    expect(settings()).toBeTruthy();
  });

  it('keeps the labels on the single-pane phone', () => {
    render(<ShellFooter {...FULL} />);
    for (const word of ['Settings', 'Notifications', 'Activity']) expect(screen.getByText(word)).toBeTruthy();
    expect(screen.queryByText('0.9.0')).toBeNull();
  });
});

describe('ShellFooter label room', () => {
  const NOTIFICATIONS_W_AT_11 = 56.85;
  const FULL = { onNotificationsPress: () => {}, onSettingsPress: () => {}, onActivityPress: () => {} };
  const mountAt = (width, props = FULL) => {
    h.layout = null;
    const view = render(<ShellFooter {...props} />);
    act(() => h.layout({ nativeEvent: { layout: { width, height: 44 } } }));
    return view;
  };
  const labelsShown = () => screen.queryByText('Notifications') !== null;
  const slot = (width, entries = 4) => (width - 2 * space.s5) / entries;
  const label = (fontSize, scale) => NOTIFICATIONS_W_AT_11 * ((fontSize * scale) / 11);

  afterEach(() => {
    h.fontScale = 1;
  });

  it('keeps no inner inset and shares the full width between the four entries', () => {
    expect(ENTRY_INSET_X).toBe(0);
    expect(slot(360)).toBe(84);
    expect(slot(360)).toBeGreaterThanOrEqual(label(11, 1.3));
    expect(slot(390)).toBeGreaterThanOrEqual(label(11, 1.3));
  });

  it.each([320, 360, 390, 430])('shows no clipped label at %i pt: labels only when the slot holds the widest one', (width) => {
    mountAt(width);
    expect(labelsShown()).toBe(slot(width) >= label(11, 1) + LABEL_ROOM);
    expect(labelsShown()).toBe(true);
  });

  it('keeps the labels at 360, 390 and 430 pt at the largest text size', () => {
    h.fontScale = 1.3;
    for (const width of [360, 390, 430]) {
      mountAt(width);
      expect(labelsShown()).toBe(true);
      cleanup();
    }
  });

  it('drops the labels at 320 pt at the largest text size and keeps every accessibility label and 44 pt target', () => {
    h.fontScale = 1.3;
    mountAt(320);
    expect(slot(320)).toBeLessThan(label(11, 1.3) + LABEL_ROOM);
    expect(labelsShown()).toBe(false);
    expect(screen.queryByText('Settings')).toBeNull();
    for (const entry of [settings(), bell(), screen.getByLabelText('Activity'), screen.getByLabelText(/^Theme:/)]) {
      expect(Number(entry.getAttribute('hitSlop')) * 2 + 36).toBe(mobile.tap);
    }
  });

  it('keeps the labels at 320 pt on the default text size', () => {
    mountAt(320);
    expect(labelsShown()).toBe(true);
  });

  it('measures the footer itself, so the 280 pt fold sidebar drops labels only when they would not fit', () => {
    mountAt(280);
    expect(labelsShown()).toBe(true);
    cleanup();
    h.fontScale = 1.3;
    mountAt(280);
    expect(labelsShown()).toBe(false);
  });

  it('applies a zero min width to every entry', () => {
    expect(source('src/features/shell/ShellFooter.jsx')).toMatch(/minWidth: 0,\s+paddingHorizontal: ENTRY_INSET_X/);
  });
});
