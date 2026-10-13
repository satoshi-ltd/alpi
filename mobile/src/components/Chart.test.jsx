import React, { useEffect } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native-svg', () => {
  const El = (tag) => ({ children, ...p }) => React.createElement(tag, {
    'data-fill': p.fill, 'data-stroke': p.stroke, 'data-dash': p.strokeDasharray, 'data-points': p.points,
  }, children);
  const Svg = El('svg');
  return { default: Svg, Svg, Circle: El('circle'), Line: El('line'), Polyline: El('polyline'), Rect: El('rect'), Text: El('text') };
});
const h = vi.hoisted(() => ({ width: 340, pane: { twoPane: false, sidebarOpen: true } }));

vi.mock('react-native', () => ({
  View: ({ children, onLayout, accessibilityLabel, style }) => {
    useEffect(() => { onLayout?.({ nativeEvent: { layout: { width: h.width } } }); }, []);
    return React.createElement('div', { ...(accessibilityLabel ? { 'aria-label': accessibilityLabel } : {}), 'data-min': style?.minWidth }, children);
  },
  Text: ({ children }) => React.createElement('span', {}, children),
  useWindowDimensions: () => ({ width: 390, height: 844 }),
}));
vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { ink: '#141414', ink2: '#454545', ink3: '#6b6b6b', ink4: '#b4b4b4', line2: '#dddddd', bgPane: '#ffffff' },
    fonts: { sans: { regular: 'r', semibold: 's' }, mono: 'm' },
    fontSizes: { xs: 11, sm: 12 },
  }),
}));

import { parseChart } from '../../../common/chartSpec.mjs';
import { mixHex } from '../../../common/color.mjs';
import { Chart } from './Chart';

const LINE = parseChart({ type: 'line', title: 'Chats per day', x: ['Mon', 'Tue', 'Wed', 'Thu'], series: [{ name: 'This week', values: [3, 1, 4, 2] }, { name: 'Last week', values: [2, 2, 3, 3] }] });

describe('Chart', () => {
  it('draws the first series in the full profile accent and the comparison dashed in another tone of it, toward the ink like the header', () => {
    const { container } = render(<Chart spec={LINE} accent="#2e7d4f" />);
    const [first, second] = container.querySelectorAll('polyline');
    expect(first.getAttribute('data-stroke')).toBe('#2e7d4f');
    expect(second.getAttribute('data-stroke')).toBe(mixHex('#2e7d4f', 0.58, '#141414'));
    expect(second.getAttribute('data-dash')).toBe('3 3');
  });

  it('falls back to the ink and its greys without an accent', () => {
    const { container } = render(<Chart spec={LINE} />);
    const [first, second] = container.querySelectorAll('polyline');
    expect(first.getAttribute('data-stroke')).toBe('#141414');
    expect(second.getAttribute('data-stroke')).toBe('#6b6b6b');
  });

  it('reads aloud from the data and shows its title and legend', () => {
    const { container } = render(<Chart spec={LINE} />);
    expect(container.querySelector('[aria-label]').getAttribute('aria-label')).toBe('Line chart, Chats per day. 4 points from Mon to Thu. This week: from 3 to 2; Last week: from 2 to 3.');
    expect(container.textContent).toContain('Chats per day');
    expect(container.textContent).toContain('Last week');
  });

  it('draws one bar per value and no legend for a single series', () => {
    const bars = parseChart({ type: 'bar', x: ['Mon', 'Tue', 'Wed'], series: [{ name: 'Bookings', values: [12, 15, 11] }] });
    const { container } = render(<Chart spec={bars} accent="#2e7d4f" />);
    expect(container.querySelectorAll('rect')).toHaveLength(3);
    expect(container.textContent).not.toContain('Bookings');
  });
});

vi.mock('../nav/PaneContext', () => ({ usePane: () => h.pane }));

describe('Chart sizing', () => {
  it('holds a floor width so a shrink-wrapped bubble cannot squash it', () => {
    const { container } = render(<Chart spec={LINE} />);
    expect(container.querySelector('[aria-label]').getAttribute('data-min')).toBe(String(Math.round((390 - 32) * 0.76) - 32));
  });

  it('draws nothing until it knows its width', () => {
    h.width = 0;
    const { container } = render(<Chart spec={LINE} />);
    expect(container.querySelector('svg')).toBeNull();
    h.width = 340;
  });
});

describe('Chart floor in a narrow pane', () => {
  it('fits the floor inside a bubble of a pane next to the sidebar', () => {
    h.pane = { twoPane: true, sidebarOpen: true };
    const { container } = render(<Chart spec={LINE} />);
    expect(Number(container.querySelector('[aria-label]').getAttribute('data-min'))).toBe(Math.round((390 - 280 - 32) * 0.76) - 32);
    h.pane = { twoPane: false, sidebarOpen: true };
  });
});
