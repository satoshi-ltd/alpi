import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  window: { width: 834, height: 1194 },
  insets: { bottom: 0 },
  offScreen: [],
  keyboard: {},
  mounted: null,
}));

vi.mock('react-native', () => {
  const View = ({ children, style, ...p }) => React.createElement('div', p, children);
  const Text = ({ children, style, ...p }) => React.createElement('span', p, children);
  const Pressable = ({ children, onPress, hitSlop, style, accessibilityLabel, accessibilityHint, ...p }) =>
    React.createElement(
      'button',
      {
        type: 'button',
        onClick: onPress,
        'aria-label': accessibilityLabel,
        'data-hint': accessibilityHint,
        'data-tap': JSON.stringify(typeof style === 'function' ? style({ pressed: false }) : style),
      },
      typeof children === 'function' ? children({ pressed: false }) : children,
    );
  const Modal = ({ children, visible, supportedOrientations }) =>
    visible
      ? React.createElement('div', { 'data-orientations': (supportedOrientations ?? []).join(',') }, children)
      : null;
  return {
    Keyboard: {
      addListener: (event, fn) => {
        h.keyboard[event] = fn;
        return { remove: () => { delete h.keyboard[event]; } };
      },
    },
    Modal,
    Pressable,
    Text,
    View,
    useWindowDimensions: () => h.window,
  };
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
vi.mock('react-native-safe-area-context', () => ({ useSafeAreaInsets: () => h.insets }));
vi.mock('./Button', () => ({ Button: ({ title }) => React.createElement('button', { type: 'button' }, title) }));
vi.mock('./Icon', () => ({ Icon: ({ name }) => React.createElement('span', { 'data-icon': name }) }));
vi.mock('./useSheetGesture', () => ({
  useSheetGesture: (open, onClose, offScreen) => {
    h.offScreen.push(offScreen);
    return { gesture: {}, sheetStyle: {}, backdropStyle: {}, mounted: h.mounted ?? open };
  },
}));

vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { bgPane: '#fff', ink: '#000', ink3: '#666', ink4: '#999', selected: '#eee' },
    fonts: { sans: { medium: 'Inter_500Medium', semibold: 'Inter_600SemiBold' }, mono: 'JetBrainsMono_400Regular' },
    fontSizes: { sm: 12, md: 14, xl: 18 },
    shadow: { base: {} },
  }),
}));

import { PaneContext } from '../nav/PaneContext';
import { mobile, radii } from '../theme/tokens';
import { Sheet } from './Sheet';

function renderSheet(props) {
  h.offScreen.length = 0;
  return render(<Sheet open onClose={() => {}} title="Rename" {...props} />);
}

function renderInTwoPane() {
  h.offScreen.length = 0;
  return render(
    <PaneContext.Provider value={{ twoPane: true, side: 'detail' }}>
      <Sheet open onClose={() => {}} title="Rename" />
    </PaneContext.Provider>,
  );
}

const sheetStyleOf = (container) =>
  JSON.parse([...container.querySelectorAll('[data-style]')].at(-1).getAttribute('data-style'));

const backdropStyleOf = (container) =>
  JSON.parse(container.querySelector('[data-style]').getAttribute('data-style'));

beforeEach(() => {
  h.window = { width: 834, height: 1194 };
  h.insets = { bottom: 0 };
  h.keyboard = {};
  h.mounted = null;
});

describe('Sheet viewport', () => {
  it('sends the sheet past the bottom of the current viewport when closing', () => {
    h.window = { width: 834, height: 1194 };
    renderSheet();
    expect(h.offScreen.at(-1)).toBe(1294);

    h.window = { width: 440, height: 956 };
    renderSheet();
    expect(h.offScreen.at(-1)).toBe(1056);
  });

  it('lets the device rotate while the sheet is open', () => {
    const { container } = renderSheet();
    expect(container.querySelector('[data-orientations]').getAttribute('data-orientations')).toBe(
      'portrait,landscape-left,landscape-right',
    );
  });
});

describe('Sheet wide form', () => {
  it('keeps the phone bottom-sheet form outside any pane provider', () => {
    const { container } = renderSheet();
    expect(sheetStyleOf(container)).toEqual({
      maxHeight: '88%',
      backgroundColor: '#fff',
      borderTopLeftRadius: radii['3xl'],
      borderTopRightRadius: radii['3xl'],
      overflow: 'hidden',
    });
  });

  it('becomes a centred capped dialog in two-pane mode', () => {
    const { container } = renderInTwoPane();
    expect(sheetStyleOf(container)).toEqual({
      maxHeight: '88%',
      backgroundColor: '#fff',
      borderTopLeftRadius: radii['3xl'],
      borderTopRightRadius: radii['3xl'],
      borderBottomLeftRadius: radii['3xl'],
      borderBottomRightRadius: radii['3xl'],
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

describe('Sheet keyboard', () => {
  const raise = (px) => act(() => h.keyboard.keyboardDidShow({ endCoordinates: { height: px } }));
  const drop = () => act(() => h.keyboard.keyboardDidHide());

  for (const [label, mount] of [['one pane', renderSheet], ['two panes', renderInTwoPane]]) {
    it(`lifts the sheet clear of the keyboard on ${label}`, () => {
      const { container } = mount();
      expect(backdropStyleOf(container).paddingBottom).toBe(0);

      raise(336);
      expect(backdropStyleOf(container).paddingBottom).toBe(336);

      drop();
      expect(backdropStyleOf(container).paddingBottom).toBe(0);
    });
  }

  it('subscribes on Did events so iOS commits the focus before the layout shifts', () => {
    renderSheet();
    expect(Object.keys(h.keyboard).sort()).toEqual(['keyboardDidHide', 'keyboardDidShow']);
  });
});

describe('Sheet dismissal contract', () => {
  const closeButton = () => screen.getByRole('button', { name: 'Close' });

  it('dismisses through an icon, never the word Cancel', () => {
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

  it('keeps the close control on a sheet that hides its title', () => {
    renderSheet({ hideHeader: true, title: undefined });
    expect(closeButton()).toBeTruthy();
    expect(screen.queryByText('Rename')).toBeNull();
  });

  it('routes the close icon and the backdrop to the same handler', () => {
    const closes = [];
    h.offScreen.length = 0;
    const { container } = render(<Sheet open onClose={() => closes.push('x')} title="Rename" />);
    closeButton().click();
    container.querySelectorAll('button')[0].click();
    expect(closes.length).toBe(2);
  });

  it('wraps the header in the pan detector so swipe-down starts on the grabber', () => {
    const { container } = renderSheet();
    const pan = container.querySelector('[data-gesture="pan"]');
    expect(pan.contains(closeButton())).toBe(true);
  });
});

describe('Sheet exit', () => {
  it('keeps rendering what it showed while it animates out, after the consumer clears the target', () => {
    h.offScreen.length = 0;
    const { rerender } = render(
      <Sheet open onClose={() => {}} title="MCP · fs" subtitle="npx fs">
        <span>server detail</span>
      </Sheet>,
    );
    expect(screen.getByText('MCP · fs')).toBeTruthy();

    h.mounted = true;
    rerender(<Sheet open={false} onClose={() => {}} title="" subtitle="" />);

    expect(screen.getByText('MCP · fs')).toBeTruthy();
    expect(screen.getByText('npx fs')).toBeTruthy();
    expect(screen.getByText('server detail')).toBeTruthy();
  });

  it('keeps the footer action rendered through the exit instead of collapsing the sheet', () => {
    h.offScreen.length = 0;
    const { rerender } = render(
      <Sheet open onClose={() => {}} title="MCP · fs" primaryAction={{ label: 'Remove server' }} />,
    );
    h.mounted = true;
    rerender(<Sheet open={false} onClose={() => {}} title="" primaryAction={undefined} />);
    expect(screen.getByText('Remove server')).toBeTruthy();
  });

  it('stops taking taps the moment it starts leaving', () => {
    h.offScreen.length = 0;
    const { container, rerender } = render(<Sheet open onClose={() => {}} title="Rename" />);
    expect(container.querySelector('[data-pe]').getAttribute('data-pe')).toBe('auto');
    h.mounted = true;
    rerender(<Sheet open={false} onClose={() => {}} title="Rename" />);
    expect(container.querySelector('[data-pe]').getAttribute('data-pe')).toBe('none');
  });

  it('drops the surface once the exit is over', () => {
    h.offScreen.length = 0;
    const { container, rerender } = render(<Sheet open onClose={() => {}} title="Rename" />);
    h.mounted = false;
    rerender(<Sheet open={false} onClose={() => {}} title="Rename" />);
    expect(container.querySelector('[data-orientations]')).toBeNull();
  });
});
