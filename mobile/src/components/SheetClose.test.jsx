import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => ({
  Pressable: ({ children, style, hitSlop, accessibilityLabel }) =>
    React.createElement(
      'button',
      { 'aria-label': accessibilityLabel, 'data-hitslop': String(hitSlop), 'data-style': JSON.stringify(typeof style === 'function' ? style({ pressed: false }) : style) },
      children,
    ),
}));
vi.mock('./Icon', () => ({ Icon: () => React.createElement('i') }));
vi.mock('../theme/ThemeContext', () => ({ useTheme: () => ({ colors: { selected: '#eee', ink3: '#666' } }) }));

import { fontSizes, iconSizes, lineHeights, mobile, space, typography } from '../theme/tokens';
import { SHEET_CLOSE_BLEED, SheetClose } from './SheetClose';
import { sheetStyles } from './sheetStyles';

const closeStyle = () => {
  render(<SheetClose onPress={() => {}} />);
  return JSON.parse(screen.getByLabelText('Close').getAttribute('data-style'));
};

describe('SheetClose geometry', () => {
  it('stays a 44 pt target', () => {
    const style = closeStyle();
    expect(style.width).toBe(mobile.tap);
    expect(style.height).toBe(mobile.tap);
  });

  it('centres the glyph on the first title line, on a phone sheet and on a two-pane dialog', () => {
    const style = closeStyle();
    const line = fontSizes[typography.dialogTitle.size] * lineHeights[typography.dialogTitle.leading];
    for (const top of [sheetStyles.header.paddingTop, sheetStyles.dialogHeader.paddingTop]) {
      const glyphCentre = top + style.marginTop + mobile.tap / 2;
      expect(Math.abs(glyphCentre - (top + line / 2))).toBeLessThanOrEqual(0.5);
    }
  });

  it('puts the glyph the same distance from the right edge as the title sits from the left', () => {
    const style = closeStyle();
    const glyphFromRight = sheetStyles.header.paddingRight + style.marginRight + (mobile.tap - iconSizes.md) / 2;
    expect(glyphFromRight).toBe(sheetStyles.header.paddingLeft);
    expect(style.marginTop).toBe(-SHEET_CLOSE_BLEED);
    expect(style.marginRight).toBe(-SHEET_CLOSE_BLEED);
    expect(space.s4).toBe(SHEET_CLOSE_BLEED);
  });
});
