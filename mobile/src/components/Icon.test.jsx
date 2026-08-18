import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

import { ICONS as DESKTOP_ICONS, ICON_ALIASES as DESKTOP_ALIASES } from '../../../desktop/src/primitives/iconPaths.js';
import { ICONS, ICON_ALIASES } from './iconPaths';
import { iconSizes, iconStroke } from '../theme/tokens';

afterEach(cleanup);

vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({ colors: { ink2: '#333' } }),
}));

const { Icon } = await import('./Icon');

function draw(props) {
  return render(<Icon {...props} />).container.querySelector('svg');
}

describe('Icon defaults', () => {
  it('lands on the md step when no size is given', () => {
    const svg = draw({ name: 'search' });
    expect(svg.getAttribute('width')).toBe(String(iconSizes.md));
    expect(svg.getAttribute('height')).toBe(String(iconSizes.md));
  });

  it('strokes at the one weight the whole set shares', () => {
    for (const name of ['search', 'gear', 'plus', 'chevron-down', 'trash']) {
      expect(draw({ name }).getAttribute('stroke-width')).toBe(String(iconStroke));
      cleanup();
    }
  });

  it('draws on desktop lucide 24×24 grid', () => {
    expect(draw({ name: 'search' }).getAttribute('viewBox')).toBe('0 0 24 24');
  });
});

describe('Icon size scale', () => {
  it.each(Object.entries(iconSizes))('resolves the %s step to %i', (step, px) => {
    expect(draw({ name: 'check', size: step }).getAttribute('width')).toBe(String(px));
  });

  it('mirrors desktop step for step, with hero as the only mobile-only tier', () => {
    expect(Object.keys(iconSizes)).toEqual(['xs', 'sm', 'md', 'lg', 'xl', 'hero']);
  });

  it('keeps every step one notch above its desktop twin', () => {
    const desktop = { xs: 9, sm: 12, md: 14, lg: 18, xl: 24 };
    for (const [step, px] of Object.entries(desktop)) {
      expect(iconSizes[step], step).toBeGreaterThanOrEqual(px);
    }
  });

  it('sizes the lg step for the 44pt tap target the way desktop sizes md for its 28px button', () => {
    expect(iconSizes.lg / 44).toBeCloseTo(14 / 28, 1);
  });

  it('still takes a raw number so a one-off can opt out', () => {
    expect(draw({ name: 'check', size: 33 }).getAttribute('width')).toBe('33');
  });

  it('falls back to md when handed a step that is not in the scale', () => {
    expect(draw({ name: 'check', size: 'jumbo' }).getAttribute('width')).toBe(String(iconSizes.md));
  });
});

describe('Icon geometry', () => {
  it('renders nothing for a name the map does not know', () => {
    expect(render(<Icon name="nope" />).container.querySelector('svg')).toBeNull();
  });

  it('honours a per-glyph stroke override, so the filled alpi mark stays filled', () => {
    const svg = draw({ name: 'alpi' });
    expect(svg.getAttribute('stroke')).toBe('none');
    expect(svg.getAttribute('fill')).toBe('#333');
  });

  it('routes the mobile nav aliases to chevrons, not desktop arrows', () => {
    expect(draw({ name: 'back' }).querySelector('path').getAttribute('d')).toBe(ICONS['chevron-left'][0][1].d);
    cleanup();
    expect(draw({ name: 'forward' }).querySelector('path').getAttribute('d')).toBe(ICONS['chevron-right'][0][1].d);
  });
});

describe('icon set parity with desktop', () => {
  it('holds no glyph desktop does not have', () => {
    expect(Object.keys(ICONS).filter((name) => !(name in DESKTOP_ICONS))).toEqual([]);
  });

  it('draws every shared glyph from the exact same geometry', () => {
    for (const [name, def] of Object.entries(ICONS)) {
      expect(def, name).toEqual(DESKTOP_ICONS[name]);
    }
  });

  it('keeps the alias table identical, so a desktop call site ports by name', () => {
    expect(ICON_ALIASES).toEqual(DESKTOP_ALIASES);
  });
});
