import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, renderHook, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  window: { width: 393, height: 852 },
  pathname: '/',
  mounts: 0,
  bgOf: (style) => [style].flat(Infinity).filter(Boolean).reduce((bg, s) => s.backgroundColor ?? bg, null),
}));

vi.mock('react-native', () => {
  const View = ({ children, style, ...p }) => React.createElement('div', p, children);
  const Text = ({ children, style, numberOfLines, ...p }) => React.createElement('span', p, children);
  const Pressable = ({ children, style, onPress, onLongPress, android_ripple, ...p }) =>
    React.createElement(
      'button',
      {
        type: 'button',
        onClick: onPress,
        'data-bg': h.bgOf(typeof style === 'function' ? style({ pressed: false }) : style),
        ...p,
      },
      children,
    );
  return { Pressable, Text, View, StyleSheet: { create: (s) => s }, useWindowDimensions: () => h.window };
});

vi.mock('expo-router', () => ({ usePathname: () => h.pathname }));

vi.mock('../../theme/ThemeContext', async () => {
  const tokens = await import('../../theme/tokens');
  return {
    useTheme: () => ({
      colors: {
        bg: '#fff', bgPane: '#fff', line: '#eee', selected: '#eaeaea', hover: '#f4f4f4',
        ink: '#000', ink2: '#333', ink3: '#666', ink4: '#999', accent: '#c90',
      },
      fonts: {
        sans: { regular: 'r', medium: 'm', semibold: 's', bold: 'b' },
        mono: 'mono', monoMedium: 'monoMedium', monoSemibold: 'monoSemibold',
      },
      alpha: { muted: 0.55 },
      fontSizes: tokens.fontSizes,
    }),
  };
});

vi.mock('../../components/Glyph', () => ({ Glyph: () => React.createElement('span', { 'data-glyph': 'true' }) }));
vi.mock('../../components/Dot', () => ({ Dot: () => React.createElement('span', { 'data-dot': 'true' }) }));

vi.mock('./SidebarPane', () => ({
  SidebarPane: () => React.createElement('div', { 'data-testid': 'sidebar' }),
}));

import { InboxRow } from '../inbox/InboxRow';
import { useTwoPane } from '../../hooks/useTwoPane';
import { usePane } from '../../nav/PaneContext';
import { PaneShell } from './PaneShell';

function Probe() {
  const { twoPane, side } = usePane();
  React.useEffect(() => {
    h.mounts += 1;
  }, []);
  return <span data-testid="probe" data-two={String(twoPane)} data-side={side} />;
}

function probe() {
  return screen.getByTestId('probe');
}

beforeEach(() => {
  h.window = { width: 393, height: 852 };
  h.pathname = '/';
  h.mounts = 0;
});

describe('PaneShell', () => {
  it('renders the children alone on a phone', () => {
    render(
      <PaneShell>
        <Probe />
      </PaneShell>,
    );
    expect(screen.queryByTestId('sidebar')).toBeNull();
    expect(probe().getAttribute('data-two')).toBe('false');
    expect(probe().getAttribute('data-side')).toBe('full');
  });

  it('renders the sidebar beside the children on a tablet', () => {
    h.window = { width: 834, height: 1194 };
    render(
      <PaneShell>
        <Probe />
      </PaneShell>,
    );
    expect(screen.getByTestId('sidebar')).toBeTruthy();
    expect(probe().getAttribute('data-two')).toBe('true');
    expect(probe().getAttribute('data-side')).toBe('detail');
  });

  it('never remounts the children across rotations and Split View resizes', () => {
    h.window = { width: 834, height: 1194 };
    const tree = (
      <PaneShell>
        <Probe />
      </PaneShell>
    );
    const { rerender } = render(tree);
    expect(h.mounts).toBe(1);
    expect(screen.getByTestId('sidebar')).toBeTruthy();

    for (const window of [
      { width: 1194, height: 834 },
      { width: 507, height: 1194 },
      { width: 393, height: 852 },
      { width: 834, height: 1194 },
    ]) {
      h.window = window;
      rerender(
        <PaneShell>
          <Probe />
        </PaneShell>,
      );
      expect(h.mounts).toBe(1);
    }
    expect(screen.getByTestId('sidebar')).toBeTruthy();
  });

  it('drops the sidebar without remounting the children when the window narrows', () => {
    h.window = { width: 834, height: 1194 };
    const { rerender } = render(
      <PaneShell>
        <Probe />
      </PaneShell>,
    );
    h.window = { width: 320, height: 1194 };
    rerender(
      <PaneShell>
        <Probe />
      </PaneShell>,
    );
    expect(screen.queryByTestId('sidebar')).toBeNull();
    expect(probe().getAttribute('data-side')).toBe('full');
    expect(h.mounts).toBe(1);
  });
});

const DEVICES = [
  ['iPhone 17 Pro Max portrait', 440, 956, false],
  ['iPhone 17 Pro Max landscape', 956, 440, false],
  ['iPad Slide Over', 320, 1194, false],
  ['iPad Split View 1/2', 507, 1194, false],
  ['iPad Split View 2/3', 686, 1194, false],
  ['iPad mini portrait', 744, 1133, true],
  ['iPad 11" portrait', 834, 1194, true],
  ['iPad 11" landscape', 1194, 834, true],
  ['Pixel 9 Pro Fold unfolded', 852, 883, true],
  ['Pixel 9 Pro Fold cover', 443, 995, false],
  ['Android 10" tablet portrait', 800, 1280, true],
];

describe('useTwoPane', () => {
  for (const [device, width, height, expected] of DEVICES) {
    it(`${expected ? 'splits' : 'keeps one pane on'} ${device} (${width}x${height})`, () => {
      h.window = { width, height };
      const { result } = renderHook(() => useTwoPane());
      expect(result.current).toBe(expected);
    });
  }

  it('holds two panes while a Split View divider drags inside the hysteresis band', () => {
    h.window = { width: 834, height: 1194 };
    const { result, rerender } = renderHook(() => useTwoPane());
    expect(result.current).toBe(true);

    h.window = { width: 686, height: 1194 };
    rerender();
    expect(result.current).toBe(true);

    h.window = { width: 660, height: 1194 };
    rerender();
    expect(result.current).toBe(false);

    h.window = { width: 686, height: 1194 };
    rerender();
    expect(result.current).toBe(false);

    h.window = { width: 700, height: 1194 };
    rerender();
    expect(result.current).toBe(true);
  });

  it('keeps full-bleed routes single-pane on a tablet', () => {
    h.window = { width: 1194, height: 834 };
    h.pathname = '/pair';
    const { result, rerender } = renderHook(() => useTwoPane());
    expect(result.current).toBe(false);

    h.pathname = '/debug/aln';
    rerender();
    expect(result.current).toBe(false);

    h.pathname = '/chat/doc';
    rerender();
    expect(result.current).toBe(true);
  });
});

const ITEM = { kind: 'profile', id: 'doc', name: 'doc', label: 'doc', preview: 'hey', ts: '2m' };

describe('InboxRow selection', () => {
  it('tints the selected row', () => {
    render(<InboxRow item={ITEM} selected />);
    expect(screen.getByRole('button').getAttribute('data-bg')).toBe('#eaeaea');
  });

  it('leaves the row transparent when the prop is omitted', () => {
    render(<InboxRow item={ITEM} />);
    expect(screen.getByRole('button').getAttribute('data-bg')).toBe('transparent');
  });
});
