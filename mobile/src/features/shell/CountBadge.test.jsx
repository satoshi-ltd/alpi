import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({ scale: 1.3 }));

vi.mock('react-native', () => ({
  View: ({ children, style }) =>
    React.createElement('div', { 'data-h': style?.height, 'data-min-w': style?.minWidth, 'data-w': style?.width, 'data-border': style?.borderWidth }, children),
  Text: ({ children, style, allowFontScaling, maxFontSizeMultiplier }) =>
    React.createElement('span', {
      'data-size': style?.fontSize,
      'data-lh': style?.lineHeight,
      'data-scaling': String(allowFontScaling),
      'data-max-mult': maxFontSizeMultiplier,
    }, children),
  Pressable: ({ children }) => React.createElement('button', { type: 'button' }, children),
}));
vi.mock('expo-constants', () => ({ default: { expoConfig: { version: '0.6.0' } } }));
vi.mock('../../components/Icon', () => ({ Icon: () => null }));
vi.mock('../../theme/ThemeContext', async () => {
  const { scaleFontSizes } = await import('../../theme/textScale');
  return {
    useTheme: () => ({
      colors: { danger: '#c14545', warning: '#e08a3c', onDanger: '#fff' },
      fonts: { sans: { semibold: 's' } },
      fontSizes: scaleFontSizes(h.scale),
      chromeScale: 1,
    }),
  };
});

import { countBadge } from '../../theme/tokens';
import { CountBadge } from './ShellFooter';

describe('CountBadge', () => {
  it.each([1, 1.3])('keeps the digits inside the pill at text scale %s', (scale) => {
    h.scale = scale;
    render(<CountBadge count={7} tone="danger" ring="#fff" />);
    const text = screen.getByText('7');
    const pill = text.parentElement;
    const inner = Number(pill.getAttribute('data-h')) - 2 * Number(pill.getAttribute('data-border'));
    expect(text.getAttribute('data-scaling')).toBe('false');
    expect(text.getAttribute('data-max-mult')).toBeNull();
    expect(Number(text.getAttribute('data-size'))).toBe(countBadge.fontSize);
    expect(Number(text.getAttribute('data-lh'))).toBeLessThanOrEqual(inner);
    expect(Number(text.getAttribute('data-size'))).toBeLessThanOrEqual(Number(text.getAttribute('data-lh')));
  });

  it('keeps an 18 pt floor and grows sideways for 99+', () => {
    render(<CountBadge count={250} tone="warning" ring="#fff" />);
    const pill = screen.getByText('99+').parentElement;
    expect(Number(pill.getAttribute('data-h'))).toBe(18);
    expect(Number(pill.getAttribute('data-min-w'))).toBe(18);
    expect(pill.getAttribute('data-w')).toBeNull();
  });
});
