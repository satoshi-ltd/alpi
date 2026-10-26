import { scaleFontSizes } from '../theme/textScale';
import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({ window: { width: 834, height: 1194 }, insets: { bottom: 0 }, offScreen: [], mounted: null, selection: vi.fn(), dims: { listeners: [], removed: 0 } }));

vi.mock('../lib/haptics', () => ({ selection: h.selection }));

vi.mock('react-native', () => {
  const View = ({ children, style, ...p }) => React.createElement('div', { ...p, 'data-vstyle': JSON.stringify(style) }, children);
  const Text = ({ children, style, ...p }) => React.createElement('span', { ...p, 'data-text-style': JSON.stringify(style) }, children);
  const Pressable = ({ children, onPress, android_ripple, style, accessibilityLabel, accessibilityHint, accessibilityState, accessibilityRole, disabled, hitSlop, ...p }) =>
    React.createElement(
      'button',
      {
        type: 'button',
        onClick: onPress,
        disabled,
        'aria-disabled': accessibilityState?.disabled,
        'aria-label': accessibilityLabel,
        'data-hint': accessibilityHint,
        'data-tap': JSON.stringify(style instanceof Function ? style({ pressed: false }) : style),
      },
      children instanceof Function ? children({ pressed: false }) : children,
    );
  const ScrollView = ({ children, style }) =>
    React.createElement('div', { 'data-max-height': String(style?.maxHeight) }, children);
  const Modal = ({ children, visible, supportedOrientations }) =>
    visible
      ? React.createElement('div', { 'data-orientations': (supportedOrientations ?? []).join(',') }, children)
      : null;
  return { Modal, Pressable, ScrollView, Text, View, useWindowDimensions: () => h.window, Dimensions: { addEventListener: (type, fn) => { h.dims.listeners.push({ type, fn }); return { remove: () => { h.dims.removed += 1; } }; } } };
});

vi.mock('react-native-reanimated', () => ({
  default: {
    View: ({ children, style, pointerEvents }) =>
      React.createElement(
        'div',
        {
          'data-style': JSON.stringify(Object.assign({}, ...[].concat(style))),
          'data-pe': pointerEvents ?? '',
        },
        children,
      ),
  },
}));
vi.mock('react-native-gesture-handler', () => ({
  GestureDetector: ({ children }) => React.createElement('div', { 'data-gesture': 'pan' }, children),
}));
vi.mock('./Dot', () => ({ Dot: ({ color }) => React.createElement('i', { 'data-dot': color }) }));
vi.mock('./Toggle', () => ({ Toggle: ({ on, label }) => React.createElement('i', { 'data-switch': String(on), 'data-switch-label': label }) }));
vi.mock('./Icon', () => ({ Icon: ({ name }) => React.createElement('span', { 'data-icon': name }) }));
vi.mock('react-native-safe-area-context', () => ({ useSafeAreaInsets: () => h.insets }));
vi.mock('./useSheetGesture', () => ({
  useSheetGesture: (open, onClose, offScreen) => {
    h.offScreen.push(offScreen);
    return { gesture: {}, sheetStyle: {}, backdropStyle: {}, mounted: h.mounted ?? open };
  },
}));

vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({
    shadow: { sheet: { borderWidth: 0, borderTopWidth: 1, borderColor: '#sheet' }, dialog: { borderWidth: 0.5, borderColor: '#ddd' }, popover: { borderWidth: 0.5, borderColor: '#ddd' } },
    colors: { bgPane: '#fff', ink: '#000', ink2: '#333', ink3: '#666', ink4: '#999', line: '#ddd', danger: '#f00', accent: '#c90', dangerText: '#a00', selected: '#eee' },
    fonts: {
      sans: { regular: 'Geist_400Regular', semibold: 'Geist_600SemiBold' },
      mono: 'GeistMono_400Regular',
      monoMedium: 'GeistMono_500Medium',
    },
    fontSizes: scaleFontSizes(h.textScale ?? 1),
  }),
}));

import { PaneContext } from '../nav/PaneContext';
import { mobile, radii } from '../theme/tokens';
import { ActionSheet } from './ActionSheet';

const ACTIONS = [{ id: 'rename', label: 'Rename' }, { id: 'delete', label: 'Delete', danger: true }];

function renderSheet() {
  h.offScreen.length = 0;
  return render(<ActionSheet open onClose={() => {}} title="Session" actions={ACTIONS} />);
}

function renderInTwoPane() {
  h.offScreen.length = 0;
  return render(
    <PaneContext.Provider value={{ twoPane: true, side: 'detail' }}>
      <ActionSheet open onClose={() => {}} title="Session" actions={ACTIONS} />
    </PaneContext.Provider>,
  );
}

const capOf = (container) => Number(container.querySelector('[data-max-height]').getAttribute('data-max-height'));

const vstyles = (container) => [...container.querySelectorAll('[data-vstyle]')].map((n) => n.getAttribute('data-vstyle')).join('|');

const sheetStyleOf = (container) =>
  JSON.parse([...container.querySelectorAll('[data-style]')].at(-1).getAttribute('data-style'));

beforeEach(() => {
  h.textScale = 1;
  h.window = { width: 834, height: 1194 };
  h.insets = { bottom: 0 };
  h.mounted = null;
  h.dims.listeners.length = 0;
  h.dims.removed = 0;
});

describe('ActionSheet viewport', () => {
  it('caps the action list at 60% of the live viewport height', () => {
    h.window = { width: 834, height: 1194 };
    const { container, rerender } = renderSheet();
    expect(capOf(container)).toBe(1194 * 0.6);

    h.window = { width: 1194, height: 834 };
    rerender(<ActionSheet open onClose={() => {}} title="Session" actions={ACTIONS} />);
    expect(capOf(container)).toBe(834 * 0.6);
  });

  it('sends the sheet past the bottom of the current viewport when closing', () => {
    h.window = { width: 834, height: 1194 };
    renderSheet();
    expect(h.offScreen.at(-1)).toBe(1294);
  });

  it('lets the device rotate while the sheet is open', () => {
    const { container } = renderSheet();
    expect(container.querySelector('[data-orientations]').getAttribute('data-orientations')).toBe(
      'portrait,landscape-left,landscape-right',
    );
  });
});

function renderAnchored(anchor, width = 852) {
  h.window = { width, height: 884 };
  return render(
    <PaneContext.Provider value={{ twoPane: true, side: 'detail' }}>
      <ActionSheet open onClose={() => {}} title="doc" actions={ACTIONS} anchor={anchor} />
    </PaneContext.Provider>,
  );
}

describe('ActionSheet popover on a fold', () => {
  const anchor = { x: 796, y: 3, width: 44, height: 44 };

  it('opens a 280 pt popover 6 pt under the trigger, aligned to its right edge, with no veil', () => {
    const { container } = renderAnchored(anchor);
    const style = sheetStyleOf(container);
    expect(style).toMatchObject({ position: 'absolute', width: 280, top: 53, left: 560, borderRadius: radii.xs });
    expect(JSON.parse(container.querySelector('[data-style]').getAttribute('data-style')).backgroundColor).toBe('transparent');
  });

  it('has no title row, grabber or drag handle', () => {
    const { container } = renderAnchored(anchor);
    expect(screen.queryByText('doc')).toBeNull();
    expect(container.querySelector('[data-gesture]')).toBeNull();
    expect(vstyles(container)).not.toContain('"width":36');
  });

  it('keeps the popover inside the pane edge', () => {
    const { container } = renderAnchored({ x: 0, y: 3, width: 44, height: 44 }, 852);
    expect(sheetStyleOf(container).left).toBe(8);
  });

  it('keeps the popover above the bottom edge', () => {
    h.window = { width: 852, height: 884 };
    const { container } = render(
      <PaneContext.Provider value={{ twoPane: true, side: 'detail' }}>
        <ActionSheet open onClose={() => {}} title="doc" actions={ACTIONS} anchor={{ x: 796, y: 860, width: 44, height: 20 }} />
      </PaneContext.Provider>,
    );
    expect(sheetStyleOf(container).top).toBe(884 - 884 * 0.6 - 8);
  });

  it('closes when the window changes and stops listening afterwards', () => {
    const onClose = vi.fn();
    h.window = { width: 852, height: 884 };
    const { unmount } = render(
      <PaneContext.Provider value={{ twoPane: true, side: 'detail' }}>
        <ActionSheet open onClose={onClose} title="doc" actions={ACTIONS} anchor={anchor} />
      </PaneContext.Provider>,
    );
    expect(h.dims.listeners.map((l) => l.type)).toEqual(['change']);
    h.dims.listeners[0].fn();
    expect(onClose).toHaveBeenCalledTimes(1);
    unmount();
    expect(h.dims.removed).toBe(1);
  });

  it('does not listen for window changes on a bottom sheet', () => {
    renderSheet();
    expect(h.dims.listeners).toHaveLength(0);
  });

  it('falls back to the centred dialog without an anchor, still with no grabber', () => {
    const { container } = renderAnchored(null);
    expect(sheetStyleOf(container).alignSelf).toBe('center');
    expect(screen.getByText('doc')).toBeTruthy();
    expect(container.querySelector('[data-gesture]')).toBeNull();
    expect(vstyles(container)).not.toContain('"width":36');
  });

  it('keeps the bottom sheet on the phone even when handed an anchor', () => {
    const { container } = render(<ActionSheet open onClose={() => {}} title="doc" actions={ACTIONS} anchor={anchor} />);
    expect(container.querySelector('[data-gesture]')).toBeTruthy();
    expect(sheetStyleOf(container).position).toBeUndefined();
  });
});

describe('ActionSheet wide form', () => {
  it('keeps the phone bottom-sheet form outside any pane provider', () => {
    const { container } = renderSheet();
    expect(sheetStyleOf(container)).toEqual({
      backgroundColor: '#fff',
      borderWidth: 0,
      borderTopWidth: 1,
      borderColor: '#sheet',
      borderTopLeftRadius: radii.xs,
      borderTopRightRadius: radii.xs,
      overflow: 'hidden',
    });
  });

  it('becomes a centred capped dialog in two-pane mode', () => {
    const { container } = renderInTwoPane();
    expect(sheetStyleOf(container)).toEqual({
      backgroundColor: '#fff',
      borderWidth: 0.5,
      borderColor: '#ddd',
      borderTopLeftRadius: radii.xs,
      borderTopRightRadius: radii.xs,
      borderRadius: radii.xs,
      overflow: 'hidden',
      alignSelf: 'center',
      width: '100%',
      maxWidth: 560,
    });
  });

  it('floats the dialog without stacking the inset twice', () => {
    h.insets = { bottom: 34 };
    const { container } = renderInTwoPane();
    expect(sheetStyleOf(container).marginBottom).toBeUndefined();
  });

  it('marks the current choice when it is used as a picker', () => {
    h.offScreen.length = 0;
    render(<ActionSheet open onClose={() => {}} title="Hub" actions={[{ id: 'a', label: 'doc', selected: true }, { id: 'b', label: 'abby', selected: false }]} />);
    const tap = (name) => JSON.parse(screen.getByRole('button', { name }).getAttribute('data-tap'));
    expect(tap('doc').backgroundColor).toBe('#eee');
    expect(tap('abby').backgroundColor).toBe('transparent');
  });
});

describe('ActionSheet dismissal contract', () => {
  const closeButton = () => screen.getByRole('button', { name: 'Close' });

  it('carries the same icon close affordance as Sheet', () => {
    renderSheet();
    expect(closeButton().querySelector('[data-icon]').getAttribute('data-icon')).toBe('x');
    expect(screen.queryByText('Cancel')).toBeNull();
  });

  it('names the icon for a screen reader and spells out the swipe it stands for', () => {
    renderSheet();
    expect(closeButton().getAttribute('data-hint')).toMatch(/swipe/i);
  });

  it('holds the close control at the touch floor', () => {
    renderSheet();
    const tap = JSON.parse(closeButton().getAttribute('data-tap'));
    expect(tap.width).toBe(mobile.tap);
    expect(tap.height).toBe(mobile.tap);
  });

  it('offers the close control even when the caller passes no title', () => {
    h.offScreen.length = 0;
    render(<ActionSheet open onClose={() => {}} actions={ACTIONS} />);
    expect(closeButton()).toBeTruthy();
  });

  it('wraps the header in the pan detector so swipe-down starts on the grabber', () => {
    const { container } = renderSheet();
    expect(container.querySelector('[data-gesture="pan"]').contains(closeButton())).toBe(true);
  });
});

describe('ActionSheet exit', () => {
  it('keeps its title and actions on screen while it animates out', () => {
    h.offScreen.length = 0;
    const { rerender } = render(<ActionSheet open onClose={() => {}} title="@doc" subtitle="PROFILE" actions={ACTIONS} />);
    expect(screen.getByText('Rename')).toBeTruthy();

    h.mounted = true;
    rerender(<ActionSheet open={false} onClose={() => {}} title="" subtitle="" actions={[]} />);

    expect(screen.getByText('@doc')).toBeTruthy();
    expect(screen.getByText('PROFILE')).toBeTruthy();
    expect(screen.getByText('Rename')).toBeTruthy();
    expect(screen.getByText('Delete')).toBeTruthy();
  });

  it('stops taking taps the moment it starts leaving', () => {
    h.offScreen.length = 0;
    const { container, rerender } = render(<ActionSheet open onClose={() => {}} title="@doc" actions={ACTIONS} />);
    expect(container.querySelector('[data-pe]').getAttribute('data-pe')).toBe('auto');
    h.mounted = true;
    rerender(<ActionSheet open={false} onClose={() => {}} title="@doc" actions={ACTIONS} />);
    expect(container.querySelector('[data-pe]').getAttribute('data-pe')).toBe('none');
  });

  it('drops the surface once the exit is over', () => {
    h.offScreen.length = 0;
    const { container, rerender } = render(<ActionSheet open onClose={() => {}} title="@doc" actions={ACTIONS} />);
    h.mounted = false;
    rerender(<ActionSheet open={false} onClose={() => {}} title="@doc" actions={ACTIONS} />);
    expect(container.querySelector('[data-orientations]')).toBeNull();
  });
});


describe('ActionSheet action availability', () => {
  it('does not dismiss or invoke a disabled action', () => {
    const onClose = vi.fn();
    const onPress = vi.fn();
    render(<ActionSheet open onClose={onClose} actions={[{ label: 'Delete', disabled: true, onPress }]} />);
    const action = screen.getByRole('button', { name: 'Delete' });
    expect(action.disabled).toBe(true);
    expect(action.getAttribute('aria-disabled')).toBe('true');
    fireEvent.click(action);
    expect(onPress).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  it('dismisses before invoking an enabled action that may open another sheet', () => {
    const calls = [];
    render(<ActionSheet open onClose={() => calls.push('close')} actions={[{ label: 'Rename', onPress: () => calls.push('rename') }]} />);
    fireEvent.click(screen.getByRole('button', { name: 'Rename' }));
    expect(calls).toEqual(['close', 'rename']);
  });
});


describe('dialog title role', () => {
  it('uses the same title size and scales it with the text preference', () => {
    const { rerender } = render(<ActionSheet open onClose={() => {}} title="Preferences" />);
    const titleStyle = () => JSON.parse(screen.getByText('Preferences').getAttribute('data-text-style'));
    expect(titleStyle().fontSize).toBe(18);
    expect(titleStyle().lineHeight).toBeCloseTo(23.4);
    h.textScale = 1.3;
    rerender(<ActionSheet open onClose={() => {}} title="Preferences" />);
    expect(titleStyle().fontSize).toBe(23);
    expect(titleStyle().lineHeight).toBeCloseTo(29.9);
  });
});

describe('ActionSheet feel', () => {
  it('ticks a selection when a picker opens and stays quiet while closed', () => {
    const picker = [{ id: 'a', label: 'doc', selected: true }, { id: 'b', label: 'abby' }];
    h.selection.mockClear();
    const { rerender } = render(<ActionSheet open={false} onClose={() => {}} actions={picker} />);
    expect(h.selection).not.toHaveBeenCalled();
    rerender(<ActionSheet open onClose={() => {}} actions={picker} />);
    rerender(<ActionSheet open onClose={() => {}} actions={picker} />);
    expect(h.selection).toHaveBeenCalledTimes(1);
  });

  it('stays quiet when a menu with no pickable rows opens', () => {
    h.selection.mockClear();
    render(<ActionSheet open onClose={() => {}} actions={[{ label: 'Pin' }]} />);
    expect(h.selection).not.toHaveBeenCalled();
  });
});


describe('ActionSheet picker lane', () => {
  it('draws the choice in the accent', () => {
    render(<ActionSheet open onClose={() => {}} actions={[{ id: 'a', label: 'doc', selected: true }, { id: 'b', label: 'abby' }]} />);
    expect([...document.querySelectorAll('[data-dot]')].map((d) => d.getAttribute('data-dot'))).toEqual(['#c90']);
  });

  const lefts = () => [...document.querySelectorAll('[data-vstyle]')].map((d) => JSON.parse(d.getAttribute('data-vstyle') ?? 'null')).filter((st) => st && st.marginLeft !== undefined).map((st) => st.marginLeft);

  it('starts the divider at the text edge of a picker', () => {
    render(<ActionSheet open onClose={() => {}} actions={[{ id: 'a', label: 'doc', selected: true }, { divider: true }, { id: 'b', label: 'abby' }]} />);
    expect(lefts()).toEqual([42]);
  });

  it('keeps the icon lane for a menu', () => {
    render(<ActionSheet open onClose={() => {}} actions={[{ id: 'a', label: 'doc' }, { divider: true }]} />);
    expect(lefts()).toEqual([52]);
  });

  it('uses a 12 gap between the dot slot and the text', () => {
    render(<ActionSheet open onClose={() => {}} actions={[{ id: 'a', label: 'doc', selected: true }]} />);
    const tap = JSON.parse(screen.getByRole('button', { name: 'doc' }).getAttribute('data-tap'));
    expect([tap.gap, tap.paddingHorizontal]).toEqual([12, 16]);
  });
});

describe('ActionSheet switch rows', () => {
  it('flips a switch row without closing the sheet', () => {
    const onClose = vi.fn();
    const onValueChange = vi.fn();
    render(<ActionSheet open onClose={onClose} actions={[{ id: 'ar', label: 'Auto-read replies', kind: 'switch', value: false, onValueChange }]} />);
    const row = screen.getByRole('button', { name: 'Auto-read replies' });
    expect(document.querySelector('[data-switch]').getAttribute('data-switch')).toBe('false');
    fireEvent.click(row);
    expect(onValueChange).toHaveBeenCalledWith(true);
    expect(onClose).not.toHaveBeenCalled();
  });

  it('still closes for navigation rows', () => {
    const onClose = vi.fn();
    render(<ActionSheet open onClose={onClose} actions={[{ id: 'go', label: 'Skills', onPress: () => {} }]} />);
    fireEvent.click(screen.getByRole('button', { name: 'Skills' }));
    expect(onClose).toHaveBeenCalled();
  });
});

describe('ActionSheet item hints', () => {
  const LEFT = [{ id: 'schedule', label: 'Schedule', icon: React.createElement('i', { 'data-icon': 'clock' }), detail: '1 failed', detailDanger: true, badge: true }, { id: 'tools', label: 'Tools', detail: 'view' }];

  it('puts a badge on the icon and the detail in the danger tone when an item asks', () => {
    render(<ActionSheet open onClose={() => {}} title="doc" actions={LEFT} />);
    expect(document.querySelectorAll('[testid="action-badge"]').length).toBe(1);
    const flagged = JSON.parse(screen.getByText('1 failed').getAttribute('data-text-style'));
    const quiet = JSON.parse(screen.getByText('view').getAttribute('data-text-style'));
    expect(flagged.color).toBe('#a00');
    expect(quiet.color).toBe('#666');
  });
});
