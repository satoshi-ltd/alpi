import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({ scale: 1.3 }));

vi.mock('react-native', () => ({
  View: ({ children, style, accessibilityLabel }) =>
    React.createElement('div', { 'data-h': style?.height, 'data-min-w': style?.minWidth, 'data-w': style?.width, 'data-border': style?.borderWidth, 'data-radius': style?.borderRadius, 'data-bg': style?.backgroundColor, 'aria-label': accessibilityLabel }, children),
  Text: ({ children, style, allowFontScaling, maxFontSizeMultiplier, numberOfLines }) =>
    React.createElement('span', {
      'data-size': style?.fontSize,
      'data-lh': style?.lineHeight,
      'data-scaling': String(allowFontScaling),
      'data-max-mult': maxFontSizeMultiplier,
      'data-lines': numberOfLines,
    }, children),
  Pressable: ({ children }) => React.createElement('button', { type: 'button' }, children),
}));
vi.mock('../theme/ThemeContext', async () => {
  const { scaleFontSizes } = await import('../theme/textScale');
  return {
    useTheme: () => ({
      colors: { danger: '#c14545', warning: '#e08a3c', onDanger: '#fff' },
      fonts: { sans: { semibold: 's' } },
      fontSizes: scaleFontSizes(h.scale),
      chromeScale: 1,
    }),
  };
});

import { countBadge } from '../theme/tokens';
import { CountBadge } from './CountBadge';

describe('CountBadge', () => {
  it.each([1, 1.3])('keeps the digits inside the pill at text scale %s', (scale) => {
    h.scale = scale;
    render(<CountBadge count={7} />);
    const text = screen.getByText('7');
    const pill = text.parentElement;
    const inner = Number(pill.getAttribute('data-h'));
    expect(text.getAttribute('data-scaling')).toBe('false');
    expect(text.getAttribute('data-max-mult')).toBeNull();
    expect(Number(text.getAttribute('data-size'))).toBe(countBadge.fontSize);
    expect(Number(text.getAttribute('data-lh'))).toBeLessThanOrEqual(inner);
    expect(Number(text.getAttribute('data-size'))).toBeLessThanOrEqual(Number(text.getAttribute('data-lh')));
  });

  it('never ellipsizes the count', () => {
    render(<CountBadge count={2} />);
    expect(screen.getByText('2').getAttribute('data-lines')).toBeNull();
  });

  it('keeps an 18 pt floor and grows sideways for 9+', () => {
    render(<CountBadge count={250} />);
    const pill = screen.getByText('9+').parentElement;
    expect(Number(pill.getAttribute('data-h'))).toBe(18);
    expect(Number(pill.getAttribute('data-min-w'))).toBe(18);
    expect(pill.getAttribute('data-w')).toBeNull();
  });
});

describe('CountBadge shape', () => {
  it('is a 4 pt square badge with no ring, in the danger tone', () => {
    render(<CountBadge count={3} />);
    const pill = screen.getByText('3').parentElement;
    expect(Number(pill.getAttribute('data-radius'))).toBe(countBadge.radius);
    expect(countBadge.radius).toBe(4);
    expect(pill.getAttribute('data-border')).toBeNull();
    expect(pill.getAttribute('data-bg')).toBe('#c14545');
  });

  it('draws nothing at zero and speaks its label when given one', () => {
    const { container, rerender } = render(<CountBadge count={0} />);
    expect(container.textContent).toBe('');
    rerender(<CountBadge count={2} label="2 files need you" />);
    expect(screen.getByLabelText('2 files need you').textContent).toBe('2');
  });
});
