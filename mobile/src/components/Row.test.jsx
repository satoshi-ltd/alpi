import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

afterEach(cleanup);

const { fontOf } = vi.hoisted(() => ({
  fontOf: (style) => [style].flat(Infinity).filter(Boolean).reduce((f, s) => s.fontFamily ?? f, null),
}));

vi.mock('react-native', () => {
  const View = ({ children, style, ...p }) => React.createElement('div', p, children);
  const Text = ({ children, style, numberOfLines, ellipsizeMode, ...p }) =>
    React.createElement('span', { ...p, 'data-font': fontOf(style), 'data-lines': numberOfLines }, children);
  const Pressable = ({ children, onPress, android_ripple, style, ...p }) =>
    React.createElement('button', { type: 'button', onClick: onPress, ...p }, children);
  return { View, Text, Pressable };
});

vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { ink: '#000', ink3: '#666', ink4: '#999', danger: '#f00', bgPane: '#fff', selected: '#eee' },
    fonts: {
      sans: { regular: 'Geist_400Regular' },
      mono: 'GeistMono_400Regular',
      monoMedium: 'GeistMono_500Medium',
    },
    fontSizes: { xs: 11, md: 14, lg: 15, xl: 18 },
  }),
}));

import { iconSizes } from '../theme/tokens';
import { Row, SectionHeader } from './Row';

describe('Row typography', () => {
  it('renders every string in a theme font, chevron included', () => {
    const { container } = render(<Row label="Connections" helper="two paired" value="alpi-casa" onPress={() => {}} />);
    expect(screen.getByText('Connections').getAttribute('data-font')).toBe('Geist_400Regular');
    expect(screen.getByText('two paired').getAttribute('data-font')).toBe('GeistMono_500Medium');
    expect(screen.getByText('alpi-casa').getAttribute('data-font')).toBe('Geist_400Regular');
    expect(container.querySelector('svg').getAttribute('width')).toBe(String(iconSizes.md));
  });

  it('renders the section header in the mono token', () => {
    render(<SectionHeader>servers</SectionHeader>);
    expect(screen.getByText('servers').getAttribute('data-font')).toBe('GeistMono_500Medium');
  });
});

describe('Row spoken label', () => {
  const spoken = (container) => container.querySelector('button').getAttribute('accessibilitylabel');

  it('speaks a string value and prefers spokenValue for an element value', () => {
    const plain = render(<Row label="Skills" helper="h" value="5" onPress={() => {}} />);
    expect(spoken(plain.container)).toBe('Skills, 5, h');
    cleanup();
    const flagged = render(<Row label="Skills" helper="1 fails lint" value={<span>1 5</span>} spokenValue="1 skill needs you, 5" onPress={() => {}} />);
    expect(spoken(flagged.container)).toBe('Skills, 1 skill needs you, 5, 1 fails lint');
  });

  it('lets a helper wrap to two lines by default and keeps an explicit single line', () => {
    render(<Row label="Fast model" helper="cheap model for side-tasks and delegation" value="main model" onPress={() => {}} />);
    expect(screen.getByText('cheap model for side-tasks and delegation').getAttribute('data-lines')).toBe('2');
    cleanup();
    render(<Row label="Fast model" helper="cheap model" helperLines={1} value="main model" onPress={() => {}} />);
    expect(screen.getByText('cheap model').getAttribute('data-lines')).toBe('1');
  });
});

describe('Row with a control below', () => {
  it('ignores press, value, trailing, chevron and danger and renders the children under the label', () => {
    const onPress = vi.fn();
    const onLongPress = vi.fn();
    const { container } = render(
      <Row label="Theme" value="ignored" trailing={<b data-trailing="" />} onPress={onPress} onLongPress={onLongPress} chevron danger below={<i data-control="" />} />,
    );
    expect(container.querySelector('button')).toBeNull();
    expect(container.querySelector('[data-trailing]')).toBeNull();
    expect(container.querySelector('[data-testid="row-lane"]')).toBeNull();
    expect(screen.queryByText('ignored')).toBeNull();
    expect(container.querySelector('[data-control]').previousSibling.textContent).toBe('Theme');
    expect(onPress).not.toHaveBeenCalled();
    expect(onLongPress).not.toHaveBeenCalled();
  });

  it('stacks the label and helper over the control at full width, with no value, lane or button', () => {
    const { container } = render(<Row label="Theme" helper="three modes" value="ignored" below={<i data-control="" />} />);
    expect(screen.getByText('Theme')).toBeTruthy();
    expect(screen.getByText('three modes')).toBeTruthy();
    expect(screen.queryByText('ignored')).toBeNull();
    expect(container.querySelector('button')).toBeNull();
    const control = container.querySelector('[data-control]');
    expect(control.previousSibling.textContent).toBe('Themethree modes');
  });
});
