import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({ pathname: '/', canGoBack: vi.fn(() => true) }));

vi.mock('expo-router', () => ({
  usePathname: () => h.pathname,
  useRouter: () => ({ canGoBack: h.canGoBack }),
}));

vi.mock('react-native', () => {
  const View = ({ children, style, accessibilityRole, accessibilityLabel, accessible, ...p }) =>
    React.createElement('div', { ...(accessibilityRole === 'header' ? { role: 'heading' } : {}), ...(accessibilityLabel ? { 'aria-label': accessibilityLabel } : {}), 'data-style': JSON.stringify(style), ...p }, children);
  const Text = ({ children, style, numberOfLines, accessibilityRole, ...p }) => React.createElement('span', { ...(accessibilityRole === 'header' ? { role: 'heading' } : {}), 'data-style': JSON.stringify([style].flat(2).filter(Boolean).reduce((a, b) => ({ ...a, ...b }), {})), ...p }, children);
  const Pressable = ({ children, onPress, hitSlop, style, ...p }) =>
    React.createElement(
      'button',
      { type: 'button', onClick: onPress, 'data-hitslop': hitSlop === undefined ? undefined : String(hitSlop), 'data-style': JSON.stringify(typeof style === 'function' ? style({ pressed: false }) : style), ...p },
      children,
    );
  const StyleSheet = { create: (x) => x, absoluteFillObject: {} };
  return { View, Text, Pressable, StyleSheet };
});

vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { ink: '#000', ink2: '#333', ink3: '#666', bg: '#fff', line: '#eee', accent: '#c9a227' },
    fonts: { sans: { semibold: 'Geist_600SemiBold' }, mono: 'GeistMono_400Regular' },
    fontSizes: { xs: 11, lg: 15, xl: 18 },
  }),
}));

vi.mock('./Icon', () => ({ Icon: ({ name }) => React.createElement('span', {}, name) }));

import { PaneContext } from '../nav/PaneContext';
import { nameTone } from '../../../common/name.mjs';
import { fonts } from '../theme/tokens';
import { Button } from './Button';
import { BACK_BLEED, BACK_INK_INSET, CHROME_BTN, PANE_PAD_X, TOGGLE_BLEED } from '../lib/panes';
import { iconSizes } from '../theme/tokens';
import { ScreenHeader, headerRightBleed } from './ScreenHeader';

function inTwoPane(node) {
  return render(<PaneContext.Provider value={{ twoPane: true, side: 'detail' }}>{node}</PaneContext.Provider>);
}

beforeEach(() => {
  h.pathname = '/';
  h.canGoBack.mockClear().mockReturnValue(true);
});

describe('ScreenHeader meta strip', () => {
  const meta = (
    <>
      <span data-meta="model">deepseek-v4-flash</span>
      <span data-meta="budget">$0.00/$1.00</span>
    </>
  );

  it('sits under the subtitle on two panes with a rule between items, like the desktop hero', () => {
    inTwoPane(<ScreenHeader title="doc" subtitle="PROFILE · SETTINGS" meta={meta} />);
    expect(document.querySelectorAll('[data-meta]').length).toBe(2);
    expect(document.querySelectorAll('[testid="meta-sep"]').length).toBe(1);
  });

  it('stays out of the phone header', () => {
    render(<ScreenHeader title="doc" subtitle="PROFILE · SETTINGS" meta={meta} />);
    expect(document.querySelectorAll('[data-meta]').length).toBe(0);
  });
});

describe('ScreenHeader back chevron', () => {
  it('renders the chevron outside any pane provider', () => {
    render(<ScreenHeader title="Outputs" onBack={() => {}} />);
    expect(screen.getByText('back')).toBeTruthy();
  });

  it('drops the chevron at a pane root in two-pane mode', () => {
    h.pathname = '/chat/doc';
    inTwoPane(<ScreenHeader title="Chat" onBack={() => {}} />);
    expect(screen.queryByText('back')).toBeNull();
    expect(screen.getByText('Chat')).toBeTruthy();
  });

  it('drops the chevron on /outputs in two-pane mode — notifications are a pane root, like settings', () => {
    h.pathname = '/outputs';
    inTwoPane(<ScreenHeader title="Notifications" onBack={() => {}} />);
    expect(screen.queryByText('back')).toBeNull();
  });

  it('keeps the chevron on /outputs on the phone, where it was pushed over the roster', () => {
    h.pathname = '/outputs';
    render(<ScreenHeader title="Notifications" onBack={() => {}} />);
    expect(screen.getByText('back')).toBeTruthy();
  });

  it('leads a drilled screen with the same back control in two-pane mode as on the phone', () => {
    h.pathname = '/profile/doc/settings';
    const onBack = vi.fn();
    inTwoPane(<ScreenHeader title="Settings" onBack={onBack} />);
    expect(screen.queryByText('arrow-left')).toBeNull();
    const back = screen.getByText('back').closest('button');
    const title = screen.getByText('Settings');
    expect(back.compareDocumentPosition(title) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    back.click();
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it('drops the chevron without an onBack handler', () => {
    render(<ScreenHeader title="Outputs" />);
    expect(screen.queryByText('back')).toBeNull();
  });
});

describe('ScreenHeader right slot', () => {
  it('lets a 44 pt header button bleed into the padding so it never outgrows the chrome row', () => {
    const bleed = headerRightBleed(<Button title="Save" size="md" />);
    expect(Button.touchHeight('md') - 2 * bleed).toBe(CHROME_BTN);
    expect(Button.touchHeight('sm') - 2 * headerRightBleed(<Button title="Edit" size="sm" />)).toBe(CHROME_BTN);
  });

  it('leaves anything that is not a Button at its own height', () => {
    expect(headerRightBleed(<span>wave</span>)).toBe(0);
    expect(headerRightBleed(null)).toBe(0);
  });
});

describe('ScreenHeader name title', () => {
  const nameOf = () => JSON.parse(screen.getByRole('heading').getAttribute('data-style'));

  it('sets a profile title in the name face, in its accent\'s ink tone, when it carries an accent', () => {
    render(<ScreenHeader title="@doc" accent="#6572e4" />);
    expect(screen.getByRole('heading').textContent).toBe('@doc');
    expect(nameOf().fontFamily).toBe(fonts.name);
    expect(nameOf().color).toBe(nameTone('#6572e4', '#fff'));
  });

  it('sets a workgroup title in the name face in neutral ink, muted when paused', () => {
    const { rerender } = render(<ScreenHeader title="alpha" accent="#6572e4" neutral />);
    expect(nameOf().fontFamily).toBe(fonts.name);
    expect(nameOf().color).toBe('#000');
    rerender(<ScreenHeader title="alpha" accent="#6572e4" neutral muted />);
    expect(nameOf().color).toBe('#666');
  });

  it('sets the name at no less than 28 even when the title step is smaller', () => {
    render(<ScreenHeader title="@doc" accent="#6572e4" />);
    expect(nameOf().fontSize).toBe(28);
  });

  it('keeps plain Geist titles on screens with no accent', () => {
    render(<ScreenHeader title="Settings" />);
    expect(JSON.parse(screen.getByText('Settings').getAttribute('data-style')).fontFamily).toBe('Geist_600SemiBold');
  });
});

describe('ScreenHeader seam', () => {
  it('ends on its seam with no accent stripe under two panes', () => {
    const { container } = inTwoPane(<ScreenHeader title="doc" accent="#abc123" />);
    const stripe = [...container.querySelectorAll('div')].find((el) => (el.getAttribute('style') || '').includes('#abc123') && (el.getAttribute('style') || '').includes('absolute'));
    expect(stripe).toBeUndefined();
  });
});

describe('ScreenHeader back control geometry', () => {
  const back = () => screen.getByText('back').closest('button');

  it('is the 36 pt chrome button with a slop that lifts the target to 44 pt on both axes', () => {
    render(<ScreenHeader title="Outputs" onBack={() => {}} />);
    const style = JSON.parse(back().getAttribute('data-style'));
    const slop = Number(back().getAttribute('data-hitslop'));
    expect(style.width).toBe(CHROME_BTN);
    expect(style.height).toBe(CHROME_BTN);
    expect(style.width + 2 * slop).toBeGreaterThanOrEqual(44);
    expect(style.height + 2 * slop).toBeGreaterThanOrEqual(44);
  });

  it('pulls the glyph box flush to the header padding, the same bleed the chat header uses', () => {
    render(<ScreenHeader title="Outputs" onBack={() => {}} />);
    const style = JSON.parse(back().getAttribute('data-style'));
    expect(BACK_BLEED).toBe((CHROME_BTN - iconSizes.md) / 2);
    expect(style.marginLeft).toBe(-(BACK_BLEED + BACK_INK_INSET));
  });

  it('puts the chevron ink on the 16 pt edge: bleed plus the glyph padding of the 20 pt chevron, the title keeping its x', () => {
    render(<ScreenHeader title="Outputs" onBack={() => {}} />);
    const style = JSON.parse(back().getAttribute('data-style'));
    expect(BACK_INK_INSET).toBeCloseTo(6.5625, 6);
    expect(style.marginLeft).toBeCloseTo(-(BACK_BLEED + BACK_INK_INSET), 6);
    expect(style.marginRight).toBeCloseTo(BACK_INK_INSET, 6);
    expect(style.marginLeft + style.marginRight).toBe(-BACK_BLEED);
    expect(style.width).toBe(CHROME_BTN);
  });
});

describe('ScreenHeader two-pane show-sidebar button', () => {
  const inClosedSidebar = (node) =>
    render(<PaneContext.Provider value={{ twoPane: true, sidebarOpen: false, toggleSidebar() {}, side: 'detail' }}>{node}</PaneContext.Provider>);

  it('pads 16 and bleeds the button 10 so the icon starts at x = 16, the same rule as the chat header', () => {
    const { container } = inClosedSidebar(<ScreenHeader title="Settings" />);
    const root = JSON.parse(container.firstChild.getAttribute('data-style'));
    const wrap = screen.getByText('panel-left').closest('button').parentElement;
    const margin = JSON.parse(wrap.getAttribute('data-style')).marginLeft;
    expect(root.paddingHorizontal).toBe(PANE_PAD_X);
    expect(margin).toBe(-TOGGLE_BLEED);
    expect(root.paddingHorizontal + margin + (CHROME_BTN - iconSizes.md) / 2).toBe(16);
  });

  it('keeps the chevron ink off the toggle: only a leading back control takes the ink shift', () => {
    h.pathname = '/outputs/abc';
    inClosedSidebar(<ScreenHeader title="Outputs" onBack={() => {}} />);
    const style = JSON.parse(screen.getByText('back').closest('button').getAttribute('data-style'));
    expect(style.marginLeft).toBe(-BACK_BLEED);
    expect(style.marginRight).toBe(0);
  });
});
