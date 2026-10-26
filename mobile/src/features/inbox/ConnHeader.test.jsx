import React from 'react';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => {
  const View = ({ children, style, ...p }) =>
    React.createElement('div', { ...p, 'data-style': JSON.stringify(style ?? {}) }, children);
  const Text = ({ children, style, numberOfLines, ...p }) => React.createElement('span', p, children);
  const Pressable = ({ children, onPress, style, accessibilityLabel, hitSlop, ...p }) =>
    React.createElement(
      'button',
      {
        type: 'button',
        onClick: onPress,
        'aria-label': accessibilityLabel,
        'data-hitslop': hitSlop === undefined ? undefined : String(hitSlop),
        'data-style': JSON.stringify((typeof style === 'function' ? style({ pressed: false }) : style) ?? {}),
      },
      children,
    );
  return { View, Text, Pressable };
});

vi.mock('../../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: {
      ink: '#000',
      ink2: '#333',
      ink3: '#666',
      bg: '#fff',
      bgElev: '#ffffff',
      bgSide: '#f5f6f8',
      field: '#f4f4f4',
      line: '#e6e6e6',
      line2: '#dcdcdc',
      selected: '#eee',
      success: '#0f0',
      warning: '#ff0',
      danger: '#f00',
    },
    fonts: { sans: { semibold: 'Geist_600SemiBold', medium: 'Geist_500Medium' }, mono: 'GeistMono_400Regular' },
    fontSizes: { xxs: 9, xs: 11, base: 13 },
    mobile: { tap: 44 },
  }),
}));

vi.mock('../../components/Icon', () => ({ Icon: ({ name }) => React.createElement('span', {}, name) }));

import { CHROME_BTN, tapSlop } from '../../lib/panes';
import { PaneContext } from '../../nav/PaneContext';
import { space } from '../../theme/tokens';
import { ConnHeader } from './ConnHeader';

const rootStyleOf = (container) => JSON.parse(container.querySelector('[data-style]').getAttribute('data-style'));

const inSidebar = (ui) =>
  render(<PaneContext.Provider value={{ twoPane: true, side: 'list' }}>{ui}</PaneContext.Provider>);

describe('ConnHeader seam', () => {
  it('closes the header with the same hairline the detail-pane headers use', () => {
    const { container } = render(<ConnHeader name="Local" host="host.sock" />);
    expect(rootStyleOf(container)).toMatchObject({ borderBottomWidth: 0.5, borderBottomColor: '#e6e6e6' });
  });

  it('still renders the endpoint identity', () => {
    render(<ConnHeader name="casa" host="100.99.29.84" />);
    expect(screen.getByText('casa')).toBeTruthy();
    expect(screen.getByText('100.99.29.84')).toBeTruthy();
  });
});

describe('ConnHeader in the sidebar', () => {
  it('sits on the sidebar surface, never on the white pane background', () => {
    const { container } = inSidebar(<ConnHeader name="Local" host="host.sock" />);
    const style = rootStyleOf(container);
    expect(style.backgroundColor).toBe('#f5f6f8');
    expect(style.backgroundColor).not.toBe('#fff');
  });

  it('draws the same trigger shape on the phone as in the sidebar', () => {
    const shapeOf = (container) =>
      [...container.querySelectorAll('button')]
        .map((n) => Object.assign({}, ...[JSON.parse(n.getAttribute('data-style') || '{}')].flat(Infinity)))
        .find((st) => st.borderRadius !== undefined && st.backgroundColor);
    const phone = shapeOf(render(<ConnHeader name="Local" host="host.sock" onConnPress={() => {}} />).container);
    cleanup();
    const tablet = shapeOf(inSidebar(<ConnHeader name="Local" host="host.sock" onConnPress={() => {}} />).container);
    for (const key of ['borderRadius', 'backgroundColor', 'borderColor', 'paddingHorizontal', 'gap']) {
      expect(phone[key]).toBe(tablet[key]);
    }
  });

  it('fills the trigger like desktop instead of letting the sidebar show through', () => {
    const { container } = inSidebar(<ConnHeader name="Local" host="host.sock" onConnPress={() => {}} />);
    const fills = [...container.querySelectorAll('button')]
      .map((node) => JSON.parse(node.getAttribute('data-style') || '{}').backgroundColor)
      .filter(Boolean);
    expect(fills).toContain('#ffffff');
    expect(fills).not.toContain('transparent');
  });

  it('labels the block and keeps the identity', () => {
    inSidebar(<ConnHeader name="Local" host="host.sock" />);
    expect(screen.getByText('Connection')).toBeTruthy();
    expect(screen.getByText('Local')).toBeTruthy();
    expect(screen.getByText('host.sock')).toBeTruthy();
  });

  it('labels the block on the phone too, so the identity is not a bare pill', () => {
    render(<ConnHeader name="Local" host="host.sock" />);
    expect(screen.getByText('Connection')).toBeTruthy();
    expect(screen.getByText('Local')).toBeTruthy();
  });

  it('gives the trigger the full width on both surfaces instead of capping the phone', () => {
    const capped = (container) =>
      [...container.querySelectorAll('button')]
        .map((n) => Object.assign({}, ...[JSON.parse(n.getAttribute('data-style') || '{}')].flat(Infinity)))
        .some((st) => st.maxWidth !== undefined);
    expect(capped(render(<ConnHeader name="Local" host="host.sock" onConnPress={() => {}} />).container)).toBe(false);
    cleanup();
    expect(capped(inSidebar(<ConnHeader name="Local" host="host.sock" onConnPress={() => {}} />).container)).toBe(false);
  });

  it('keeps the search toggle smaller than the row it labels, without shrinking its touch target', () => {
    const { container } = inSidebar(
      <ConnHeader name="Local" host="host.sock" onToggleSearch={() => {}} />,
    );
    const toggle = screen.getByLabelText('Filter profiles and workgroups');
    const style = JSON.parse(toggle.getAttribute('data-style') || '{}');
    expect(style.height).toBe(CHROME_BTN);
    expect(style.height).toBeLessThan(44);
    expect(toggle.getAttribute('data-hitslop')).toBe(String(tapSlop(CHROME_BTN)));
    expect(style.height + tapSlop(CHROME_BTN) * 2).toBe(44);
    const rows = [...container.querySelectorAll('[data-style]')]
      .map((n) => JSON.parse(n.getAttribute('data-style') || '{}'));
    expect(rows.every((st) => st.minHeight === undefined || st.minHeight === 44)).toBe(true);
  });

  it('opens the eyebrow row on the trimmed top padding the chat header uses', () => {
    const { container } = inSidebar(<ConnHeader name="Local" host="host.sock" onToggleSearch={() => {}} />);
    expect(rootStyleOf(container).paddingTop).toBe(space.s2);
  });
});

describe('ConnHeader job', () => {
  it.each([
    ['the phone', render],
    ['the sidebar', inSidebar],
  ])('leaves %s header with the connection and the search toggle, no bell and no gear', (_, mount) => {
    mount(<ConnHeader name="Local" host="host.sock" onConnPress={() => {}} onToggleSearch={() => {}} />);
    expect(screen.getByLabelText('Filter profiles and workgroups')).toBeTruthy();
    expect(screen.queryByText('bell')).toBeNull();
    expect(screen.queryByText('gear')).toBeNull();
  });

  it('takes no bell or gear handler at all — the footer owns both entries', () => {
    const text = readFileSync(join(import.meta.dirname, 'ConnHeader.jsx'), 'utf8');
    expect(text).not.toMatch(/onBellPress|onGearPress|unread/);
  });
});

describe('ConnHeader activity entry', () => {
  it('draws no activity entry — the footer beside the bell owns it, on phone and fold alike', () => {
    for (const mount of [render, inSidebar]) {
      mount(<ConnHeader name="Local" host="host.sock" onActivityPress={() => {}} needsYou={2} />);
      expect(screen.queryByLabelText(/^Activity/)).toBeNull();
      cleanup();
    }
    const text = readFileSync(join(import.meta.dirname, 'ConnHeader.jsx'), 'utf8');
    expect(text).not.toMatch(/onActivityPress|needsYou/);
  });

  it('names the connection trigger for a screen reader', () => {
    render(<ConnHeader name="casa" host="100.99.29.84" onConnPress={() => {}} />);
    expect(screen.getByLabelText('Connection casa, 100.99.29.84, online')).toBeTruthy();
  });

  it('draws no word for online, the dot says it, and still speaks it', () => {
    render(<ConnHeader name="casa" host="h" status="online" onConnPress={() => {}} />);
    expect(screen.queryByText('online')).toBeNull();
    expect(screen.getByLabelText('Connection casa, h, online')).toBeTruthy();
  });

  it('says the state in words, in the label too', () => {
    const { rerender } = render(<ConnHeader name="casa" host="h" status="offline" onConnPress={() => {}} />);
    expect(screen.getByText('offline · retrying…')).toBeTruthy();
    expect(screen.getByLabelText('Connection casa, h, offline · retrying…')).toBeTruthy();
    rerender(<ConnHeader name="casa" host="h" status="disabled" onConnPress={() => {}} />);
    expect(screen.getByText('disabled')).toBeTruthy();
    rerender(<ConnHeader name="casa" host="h" status="unknown" onConnPress={() => {}} />);
    expect(screen.getByText('connecting…')).toBeTruthy();
  });

  it('keeps the switcher at the 44 pt touch floor', () => {
    render(<ConnHeader name="casa" host="h" onConnPress={() => {}} />);
    const trigger = JSON.parse(screen.getByLabelText(/^Connection casa/).getAttribute('data-style'));
    expect(trigger.minHeight).toBe(44);
  });
});

describe('ConnHeader status dot', () => {
  const dotOf = (container) => container.querySelector('[testID="conn-status-dot"]');
  const styleOf = (node) => JSON.parse(node.getAttribute('data-style'));

  it('sits on the connection icon corner like the desktop pill, never beside the chevron', () => {
    const { container } = render(<ConnHeader name="casa" host="h" onConnPress={() => {}} />);
    const dot = dotOf(container);
    expect(dot).not.toBeNull();
    const style = styleOf(dot);
    expect(style).toMatchObject({ position: 'absolute', bottom: -2, right: -2, width: 8, height: 8, borderRadius: 4 });
    expect(dot.parentElement.querySelector('span').textContent).toBe('cpu');
  });

  it('takes its size from the dot scale and carries a ring in the surface colour', () => {
    const text = readFileSync(join(import.meta.dirname, 'ConnHeader.jsx'), 'utf8');
    expect(text).toMatch(/\.\.\.dotShape\('md'\),\s*position: 'absolute'/);
    expect(text).not.toMatch(/width: 8,/);
    const { container } = render(<ConnHeader name="casa" host="h" onConnPress={() => {}} />);
    expect(styleOf(dotOf(container)).borderColor).toBe('#ffffff');
  });

  it('colours the dot by state and keeps the word only when not online', () => {
    const { container, rerender } = render(<ConnHeader name="casa" host="h" status="online" onConnPress={() => {}} />);
    expect(styleOf(dotOf(container)).backgroundColor).toBe('#0f0');
    expect(screen.queryByText('online')).toBeNull();
    rerender(<ConnHeader name="casa" host="h" status="offline" onConnPress={() => {}} />);
    expect(styleOf(dotOf(container)).backgroundColor).toBe('#f00');
    expect(screen.getByText('offline · retrying…')).toBeTruthy();
  });
});

describe('ConnHeader right edge', () => {
  it('puts the icon button ink and the trigger chevron on one edge, 24.5 pt from the screen', () => {
    const { container } = render(<ConnHeader name="Local" host="host.sock" onToggleSearch={() => {}} onConnPress={() => {}} />);
    const header = rootStyleOf(container);
    const row = JSON.parse(screen.getByLabelText('Filter profiles and workgroups').parentElement.getAttribute('data-style'));
    const trigger = JSON.parse(screen.getByLabelText(/^Connection /).getAttribute('data-style'));
    const iconInk = header.paddingHorizontal + row.paddingRight + (CHROME_BTN - 16) / 2;
    const chevronInk = header.paddingHorizontal + 0.5 + trigger.paddingHorizontal;
    expect(header.paddingHorizontal).toBe(space.s5);
    expect(trigger.paddingHorizontal).toBe(space.s5);
    expect(iconInk).toBe(24.5);
    expect(chevronInk).toBe(24.5);
  });

  it('moves the hide-sidebar button with the same edge and keeps the 44 pt targets', () => {
    render(<ConnHeader name="Local" host="host.sock" onCollapse={() => {}} />);
    const hide = screen.getByLabelText('Hide sidebar');
    expect(JSON.parse(hide.parentElement.getAttribute('data-style')).paddingRight).toBe(2.5);
    expect(Number(hide.getAttribute('data-hitslop'))).toBe(tapSlop(CHROME_BTN));
  });
});
