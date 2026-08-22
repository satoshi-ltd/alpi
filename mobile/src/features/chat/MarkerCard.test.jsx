import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

afterEach(cleanup);

const { fontOf, flatStyle } = vi.hoisted(() => ({
  fontOf: (style) => [style].flat(Infinity).filter(Boolean).reduce((f, s) => s.fontFamily ?? f, null),
  flatStyle: (style) => Object.assign({}, ...[style].flat(Infinity).filter(Boolean)),
}));

vi.mock('react-native', () => {
  const View = ({ children, style, ...p }) =>
    React.createElement('div', { ...p, 'data-style': JSON.stringify(flatStyle(style)) }, children);
  const Text = ({ children, style, ...p }) => {
    const flat = flatStyle(style);
    return React.createElement(
      'span',
      {
        ...p,
        'data-font': fontOf(style),
        'data-size': flat.fontSize,
        'data-lh': flat.lineHeight,
      },
      children,
    );
  };
  return { View, Text, StyleSheet: { create: (s) => s } };
});

vi.mock('../../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { ink: '#000000', ink3: '#666666', bgPane: '#ffffff', warning: '#cc8800' },
    fonts: {
      sans: { regular: 'Inter_400Regular', semibold: 'Inter_600SemiBold' },
      monoMedium: 'JetBrainsMono_500Medium',
      monoSemibold: 'JetBrainsMono_600SemiBold',
    },
    shadow: { sm: { shadowOpacity: 0.06, shadowRadius: 2, elevation: 1 } },
    fontSizes: { md: 14, xs: 11 },
  }),
}));

vi.mock('../../components/Diamond', () => ({ Diamond: () => React.createElement('span', { 'data-diamond': 'true' }) }));
vi.mock('../../components/Dot', () => ({ Dot: () => React.createElement('span', { 'data-dot': 'true' }) }));
vi.mock('../../components/RichText', () => ({
  RichText: ({ children }) => React.createElement('span', { 'data-rich': 'true' }, children),
}));

import { BUBBLE_MAX_PANE } from '../../lib/panes';
import { ICONS } from '../../../../common/iconPaths.mjs';
import { PaneContext } from '../../nav/PaneContext';
import { iconSizes } from '../../theme/tokens';
import { MarkerCard } from './MarkerCard';

function caps(container) {
  return [...container.querySelectorAll('div')]
    .map((node) => JSON.parse(node.getAttribute('data-style') || '{}').maxWidth)
    .filter(Boolean);
}

describe('MarkerCard typography', () => {
  it('draws the done tick with the icon set, at desktop MarkerCard weight', () => {
    const { container } = render(<MarkerCard variant="done" hubColor="#0af0af" seq={12} speakerName="scout" title="shipped" />);
    const tick = container.querySelector('svg');
    expect(tick.getAttribute('width')).toBe(String(iconSizes.xs));
    expect(tick.getAttribute('stroke-width')).toBe('2.2');
    expect(tick.querySelector('path').getAttribute('d')).toBe(ICONS.check[0][1].d);
  });

  it('keeps eyebrow, meta and title on their own tokens', () => {
    render(<MarkerCard variant="task" hubColor="#0af0af" seq={7} speakerName="scout" title="collect the brief" />);
    expect(screen.getByText('TASK').getAttribute('data-font')).toBe('JetBrainsMono_600SemiBold');
    expect(screen.getByText('#7').getAttribute('data-font')).toBe('JetBrainsMono_500Medium');
    expect(screen.getByText('collect the brief').getAttribute('data-font')).toBe('Inter_600SemiBold');
  });
});

describe('MarkerCard descenders', () => {
  it('leaves the speaker name room for a descender, since profile names carry g and y', () => {
    render(<MarkerCard variant="task" hubColor="#0af0af" seq={7} speakerName="lingo" title="translate" />);
    const name = screen.getByText('lingo');
    expect(Number(name.getAttribute('data-lh'))).toBeGreaterThan(Number(name.getAttribute('data-size')));
  });
});

describe('MarkerCard surface', () => {
  it('stays flat like the rest of the transcript', () => {
    const { container } = render(
      <MarkerCard variant="done" hubColor="#0af0af" seq={12} speakerName="scout" title="shipped" />,
    );
    const styles = [...container.querySelectorAll('div')]
      .map((node) => JSON.parse(node.getAttribute('data-style') || '{}'));
    expect(styles.length).toBeGreaterThan(0);
    for (const style of styles) {
      expect(style.shadowOpacity).toBeUndefined();
      expect(style.elevation).toBeUndefined();
    }
  });
});

describe('MarkerCard cap by pane mode', () => {
  it('keeps the phone cap outside a pane provider', () => {
    const { container } = render(<MarkerCard variant="task" hubColor="#0af0af" title="collect the brief" />);
    expect(caps(container)).toEqual(['90%']);
  });

  it('follows the transcript bubbles to the desktop cap in two-pane mode', () => {
    const { container } = render(
      <PaneContext.Provider value={{ twoPane: true, side: 'detail' }}>
        <MarkerCard variant="task" hubColor="#0af0af" title="collect the brief" />
      </PaneContext.Provider>,
    );
    expect(caps(container)).toEqual([BUBBLE_MAX_PANE]);
  });
});
