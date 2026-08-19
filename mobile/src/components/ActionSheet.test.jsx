import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({ window: { width: 834, height: 1194 }, insets: { bottom: 0 }, offScreen: [], mounted: null }));

vi.mock('react-native', () => {
  const View = ({ children, style, ...p }) => React.createElement('div', p, children);
  const Text = ({ children, style, ...p }) => React.createElement('span', p, children);
  const Pressable = ({ children, onPress, android_ripple, style, accessibilityLabel, accessibilityHint, hitSlop, ...p }) =>
    React.createElement(
      'button',
      {
        type: 'button',
        onClick: onPress,
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
  return { Modal, Pressable, ScrollView, Text, View, useWindowDimensions: () => h.window };
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
    colors: { bgPane: '#fff', ink: '#000', ink2: '#333', ink3: '#666', ink4: '#999', line: '#ddd', danger: '#f00', selected: '#eee' },
    fonts: {
      sans: { regular: 'Inter_400Regular', semibold: 'Inter_600SemiBold' },
      mono: 'JetBrainsMono_400Regular',
      monoMedium: 'JetBrainsMono_500Medium',
    },
    fontSizes: { xs: 11, sm: 12, lg: 15 },
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

const sheetStyleOf = (container) =>
  JSON.parse([...container.querySelectorAll('[data-style]')].at(-1).getAttribute('data-style'));

beforeEach(() => {
  h.window = { width: 834, height: 1194 };
  h.insets = { bottom: 0 };
  h.mounted = null;
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

describe('ActionSheet wide form', () => {
  it('keeps the phone bottom-sheet form outside any pane provider', () => {
    const { container } = renderSheet();
    expect(sheetStyleOf(container)).toEqual({
      backgroundColor: '#fff',
      borderTopLeftRadius: radii.sheet,
      borderTopRightRadius: radii.sheet,
      overflow: 'hidden',
    });
  });

  it('becomes a centred capped dialog in two-pane mode', () => {
    const { container } = renderInTwoPane();
    expect(sheetStyleOf(container)).toEqual({
      backgroundColor: '#fff',
      borderTopLeftRadius: radii.sheet,
      borderTopRightRadius: radii.sheet,
      borderBottomLeftRadius: radii.sheet,
      borderBottomRightRadius: radii.sheet,
      overflow: 'hidden',
      alignSelf: 'center',
      width: '100%',
      maxWidth: 560,
      marginBottom: 24,
    });
  });

  it('clears the home indicator when the inset is taller than the floor', () => {
    h.insets = { bottom: 34 };
    const { container } = renderInTwoPane();
    expect(sheetStyleOf(container).marginBottom).toBe(34);
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
