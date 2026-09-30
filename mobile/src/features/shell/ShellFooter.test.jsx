import React from 'react';
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  flat: (style) => [style].flat(Infinity).filter(Boolean).reduce((acc, s) => ({ ...acc, ...s }), {}),
}));

vi.mock('react-native', () => {
  const View = ({ children, style, ...p }) =>
    React.createElement(
      'div',
      { ...p, 'data-style': JSON.stringify(h.flat(style)), ...(h.flat(style).position ? { 'data-pos': h.flat(style).position } : {}) },
      children,
    );
  const Text = ({ children, style, ...p }) => React.createElement('span', p, children);
  const Pressable = ({ children, style, onPress, accessibilityLabel, ...p }) =>
    React.createElement(
      'button',
      { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel, ...p },
      typeof children === 'function' ? children({ pressed: false }) : children,
    );
  return { View, Text, Pressable };
});

vi.mock('expo-constants', () => ({ default: { expoConfig: { version: '0.3.1' } } }));

vi.mock('../../components/Icon', () => ({ Icon: ({ name }) => React.createElement('span', { 'data-icon': name }) }));

vi.mock('../../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { ink2: '#333', ink4: '#999', line: '#eee', selected: '#eaeaea', danger: '#c00', warning: '#e08a3c', warningText: '#8a5a0a' },
    fonts: { sans: { medium: 'm', semibold: 's' }, monoMedium: 'monoMedium' },
    fontSizes: { xs: 11, sm: 12 },
    chromeScale: 1.3,
    pref: h.pref,
    setMode: h.setMode,
  }),
}));

import { CHROME_H } from '../../lib/panes';
import { mobile } from '../../theme/tokens';
import { PaneContext } from '../../nav/PaneContext';
import { ShellFooter, nextThemePref } from './ShellFooter';

const settings = () => screen.getByLabelText('Settings');
const bell = (unread = 0) => screen.getByLabelText(unread > 0 ? `Notifications · ${unread} unread` : 'Notifications');
const follows = (a, b) => Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);

const ROOT = join(import.meta.dirname, '..', '..', '..');
const source = (path) => readFileSync(join(ROOT, path), 'utf8');

describe('ShellFooter entries', () => {
  it('runs Settings, then notifications, then the version', () => {
    render(<ShellFooter unread={0} onNotificationsPress={() => {}} onSettingsPress={() => {}} />);
    expect(follows(settings(), bell())).toBe(true);
    expect(follows(bell(), screen.getByText('v0.3.1'))).toBe(true);
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

  it('overlays the unread count on the bell glyph and caps it at 99+', () => {
    const { rerender } = render(<ShellFooter unread={7} onNotificationsPress={() => {}} onSettingsPress={() => {}} />);
    const wrap = bell(7).querySelector('[data-pos="relative"]');
    expect(wrap.querySelector('[data-icon="bell"]')).toBeTruthy();
    expect(wrap.querySelector('[data-pos="absolute"]').textContent).toBe('7');

    rerender(<ShellFooter unread={13} onNotificationsPress={() => {}} onSettingsPress={() => {}} />);
    const two = bell(13).querySelector('[data-pos="absolute"]');
    expect(two.textContent).toBe('13');
    expect(two.querySelector('[data-lines="1"]') ?? two.querySelector('span')).toBeTruthy();

    rerender(<ShellFooter unread={150} onNotificationsPress={() => {}} onSettingsPress={() => {}} />);
    expect(bell(150).querySelector('[data-pos="absolute"]').textContent).toBe('99+');
  });

  it('draws no badge at zero unread', () => {
    render(<ShellFooter unread={0} onNotificationsPress={() => {}} onSettingsPress={() => {}} />);
    expect(bell().querySelector('[data-pos="absolute"]')).toBeNull();
  });

  it('hides the bell from a reader with no notifications to open, leaving Settings and the version live', () => {
    render(<ShellFooter unread={4} onNotificationsPress={null} onSettingsPress={() => {}} />);
    expect(screen.queryByLabelText('Notifications')).toBeNull();
    expect(screen.queryByLabelText('Notifications · 4 unread')).toBeNull();
    expect(settings()).toBeTruthy();
    expect(screen.getByText('v0.3.1')).toBeTruthy();
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

  it('counts what needs the user in the warning tone, apart from the unread badge', () => {
    render(<ShellFooter unread={3} needsYou={2} onNotificationsPress={() => {}} onSettingsPress={() => {}} onActivityPress={() => {}} />);
    const badge = activity(2).querySelector('[data-pos="absolute"]');
    expect(badge.textContent).toBe('2');
    expect(JSON.parse(badge.getAttribute('data-style')).backgroundColor).toBe('#e08a3c');
    expect(JSON.parse(bell(3).querySelector('[data-pos="absolute"]').getAttribute('data-style')).backgroundColor).toBe('#c00');
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

describe('ShellFooter theme toggle', () => {
  it('cycles light → dark → system from the footer on two panes, like the desktop', () => {
    h.pref = 'light';
    h.setMode = vi.fn();
    render(
      <PaneContext.Provider value={{ twoPane: true, side: 'list', sidebarOpen: true, toggleSidebar() {} }}>
        <ShellFooter onSettingsPress={() => {}} />
      </PaneContext.Provider>,
    );
    const toggle = screen.getByLabelText('Theme: Light');
    expect(toggle.querySelector('[data-icon]').getAttribute('data-icon')).toBe('sun');
    fireEvent.click(toggle);
    expect(h.setMode).toHaveBeenCalledWith('dark');
    expect(nextThemePref('dark')).toBe('system');
    expect(nextThemePref('system')).toBe('light');
  });

  it('keeps the phone footer without it — the theme lives in Settings there', () => {
    h.pref = 'dark';
    render(<ShellFooter onSettingsPress={() => {}} />);
    expect(screen.queryByLabelText(/^Theme:/)).toBeNull();
  });
});
