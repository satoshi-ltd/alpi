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
  const Text = ({ children, numberOfLines, adjustsFontSizeToFit, minimumFontScale, maxFontSizeMultiplier }) =>
    React.createElement('span', { 'data-lines': numberOfLines, 'data-fit': String(adjustsFontSizeToFit), 'data-min': minimumFontScale, 'data-max': maxFontSizeMultiplier }, children);
  const Pressable = ({ children, onPress, style, accessibilityRole, accessibilityState, accessibilityLabel }) =>
    React.createElement(
      'button',
      { type: 'button', role: accessibilityRole, 'aria-checked': accessibilityState?.selected, 'aria-label': accessibilityLabel, onClick: onPress, 'data-style': JSON.stringify(flat(style)) },
      children,
    );
  return { View, Text, Pressable };
});
vi.mock('../lib/haptics', () => ({ selection }));
vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { hover: '#eee', bgPane: '#fff', ink: '#000', ink2: '#333' },
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
  it('draws one 44 pt cell per option in a 4 pt radius track and marks the selected one', () => {
    render(<Segmented label="Theme" options={OPTIONS} value="light" onChange={() => {}} />);
    const cells = screen.getAllByRole('radio');
    expect(cells).toHaveLength(3);
    expect(cells.map((c) => c.getAttribute('aria-checked'))).toEqual(['false', 'true', 'false']);
    for (const cell of cells) expect(JSON.parse(cell.getAttribute('data-style')).minHeight).toBe(44);
    expect(JSON.parse(screen.getByRole('radiogroup').getAttribute('data-style'))).toMatchObject({ borderRadius: 4, padding: 2 });
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
