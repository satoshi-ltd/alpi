import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

const { flat, selection } = vi.hoisted(() => ({
  flat: (style) => Object.assign({}, ...[style].flat(Infinity).filter(Boolean)),
  selection: vi.fn(),
}));

vi.mock('react-native', () => {
  const View = ({ children, style, accessibilityRole, accessibilityLabel }) =>
    React.createElement('div', { role: accessibilityRole, 'aria-label': accessibilityLabel, 'data-style': JSON.stringify(flat(style)) }, children);
  const Text = ({ children, style, numberOfLines, adjustsFontSizeToFit, minimumFontScale, maxFontSizeMultiplier }) =>
    React.createElement('span', { 'data-style': JSON.stringify(flat(style)), 'data-lines': numberOfLines, 'data-fit': String(adjustsFontSizeToFit), 'data-min': minimumFontScale, 'data-max': maxFontSizeMultiplier }, children);
  const Pressable = ({ children, onPress, style, accessibilityRole, accessibilityState, accessibilityLabel }) =>
    React.createElement(
      'button',
      { type: 'button', role: accessibilityRole, 'aria-checked': accessibilityState?.selected, 'aria-label': accessibilityLabel, onClick: onPress, 'data-style': JSON.stringify(flat(style)) },
      children,
    );
  return { View, Text, Pressable };
});
vi.mock('../lib/haptics', () => ({ selection }));
const theme = vi.hoisted(() => ({ mode: 'light' }));
vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({
    mode: theme.mode,
    colors: { hover: '#eee', selected: '#e5e5e5', bgPane: '#fff', ink: '#000', ink2: '#333', accent: '#14110c', fill: '#f2f2f2', raised: '#ffffff', line2: 'rgba(237,237,237,0.16)' },
    fonts: { sans: { regular: 'r', semibold: 's' } },
    fontSizes: { md: 14 },
  }),
}));

import { Segmented } from './Segmented';

const OPTIONS = [
  { value: 'system', label: 'System' },
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
];

describe('Segmented', () => {
  it('edges the selected cell in dark, where raised and fill sit close, and sets it semibold in both themes', () => {
    for (const mode of ['light', 'dark']) {
      theme.mode = mode;
      render(<Segmented label="Theme" options={OPTIONS} value="light" onChange={() => {}} />);
      const [off, on] = screen.getAllByRole('radio').map((c) => JSON.parse(c.getAttribute('data-style')));
      expect(on.borderWidth).toBe(off.borderWidth);
      expect(on.borderColor).toBe(mode === 'dark' ? 'rgba(237,237,237,0.16)' : 'transparent');
      expect(off.borderColor).toBe('transparent');
      const label = JSON.parse(screen.getByText('Light').getAttribute('data-style'));
      expect(label.fontFamily).toBe('s');
      cleanup();
    }
    theme.mode = 'light';
  });

  it('draws one 44 pt pill cell per option on a pill track 4 pt in, and marks the selected one', () => {
    render(<Segmented label="Theme" options={OPTIONS} value="light" onChange={() => {}} />);
    const cells = screen.getAllByRole('radio');
    expect(cells).toHaveLength(3);
    expect(cells.map((c) => c.getAttribute('aria-checked'))).toEqual(['false', 'true', 'false']);
    for (const cell of cells) expect(JSON.parse(cell.getAttribute('data-style')).minHeight).toBe(44);
    expect(JSON.parse(screen.getByRole('radiogroup').getAttribute('data-style'))).toMatchObject({ borderRadius: 999, padding: 4 });
    for (const cell of cells) expect(JSON.parse(cell.getAttribute('data-style')).borderRadius).toBe(999);
  });

  it('raises the selected cell on the fill track with an ink label, never a black chip', () => {
    render(<Segmented label="Theme" options={OPTIONS} value="light" onChange={() => {}} />);
    const style = (el) => JSON.parse(el.getAttribute('data-style'));
    expect(style(screen.getByRole('radiogroup')).backgroundColor).toBe('#f2f2f2');
    const [system, light] = screen.getAllByRole('radio');
    expect(style(light).backgroundColor).toBe('#ffffff');
    expect(style(light).shadowOpacity).toBeGreaterThan(0);
    expect(style(light.querySelector('span')).color).toBe('#000');
    expect(style(system).backgroundColor).toBe('transparent');
    expect(style(system.querySelector('span')).color).toBe('#333');
  });

  it('shrinks and caps label growth instead of clipping, keeping the spoken labels', () => {
    render(<Segmented label="Text size" options={[...OPTIONS, { value: 'x', label: 'Largest' }]} value="light" onChange={() => {}} />);
    const label = screen.getByLabelText('Largest').querySelector('span');
    expect(label.getAttribute('data-fit')).toBe('true');
    expect(label.getAttribute('data-lines')).toBe('1');
    expect(Number(label.getAttribute('data-min'))).toBeLessThan(1);
    expect(Number(label.getAttribute('data-max'))).toBe(1.2);
  });

  it('reports the tapped value with a selection haptic, and nothing for the selected cell', () => {
    const onChange = vi.fn();
    render(<Segmented label="Theme" options={OPTIONS} value="light" onChange={onChange} />);
    fireEvent.click(screen.getByLabelText('Light'));
    expect(onChange).not.toHaveBeenCalled();
    fireEvent.click(screen.getByLabelText('Dark'));
    expect(onChange).toHaveBeenCalledWith('dark');
    expect(selection).toHaveBeenCalledTimes(1);
  });
});
