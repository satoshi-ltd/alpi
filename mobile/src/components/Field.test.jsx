import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => {
  const R = require('react');
  const host = (tag) => ({ children, style, accessibilityRole, ...rest }) =>
    R.createElement(tag, { role: accessibilityRole, 'data-style': JSON.stringify(style) }, children);
  return { Text: host('span'), TextInput: () => R.createElement('input'), View: host('div') };
});
vi.mock('./Eyebrow', () => ({ Eyebrow: ({ children }) => React.createElement('label', null, children) }));
vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { field: '#eee', fill: '#f2f2f2', bgPane: '#fff', bgElev: '#fefefe', edge: '#8c8c8c', line2: '#ddd', ink: '#000', ink2: '#222', ink3: '#666', danger: '#c14545', dangerText: '#b73737' },
    fonts: { mono: 'mono', sans: { regular: 'sans' } },
    fontSizes: { xs: 12, sm: 14, md: 15, lg: 16 },
    mobile: { inputH: 44 },
  }),
}));

import { Field } from './Field';

describe('Field', () => {
  it('rests as a fill with no edge and fades a read-only field by the shared alpha', () => {
    const well = (container) => JSON.parse([...container.querySelectorAll('[data-style]')].find((n) => n.getAttribute('data-style').includes('borderColor')).getAttribute('data-style'));
    const { container, rerender } = render(<Field value="a" onChangeText={() => {}} />);
    expect(well(container)).toMatchObject({ backgroundColor: '#f2f2f2', borderColor: 'transparent', borderRadius: 12 });
    expect(well(container).opacity).toBeUndefined();
    rerender(<Field value="a" onChangeText={() => {}} editable={false} />);
    expect(well(container)).toMatchObject({ backgroundColor: '#f2f2f2', borderColor: 'transparent', opacity: 0.45 });
  });

  it('shows the error in place of the helper and tints the border', () => {
    const { container } = render(<Field label="USD per day" value="abc" onChangeText={() => {}} helper="a number" error="Enter a number, or leave it empty" />);
    expect(screen.getByRole('alert').textContent).toBe('Enter a number, or leave it empty');
    expect(screen.queryByText('a number')).toBeNull();
    const box = [...container.querySelectorAll('[data-style]')].find((n) => n.getAttribute('data-style').includes('borderColor'));
    expect(JSON.parse(box.getAttribute('data-style')).borderColor).toBe('#b73737');
  });

  it('draws the error and the helper at the 14 pt description size in the regular sans face', () => {
    const { rerender } = render(<Field value="" onChangeText={() => {}} helper="a number" />);
    const styleOf = (text) => JSON.parse(screen.getByText(text).getAttribute('data-style'));
    expect(styleOf('a number')).toMatchObject({ fontFamily: 'sans', fontSize: 14, color: '#666' });
    rerender(<Field value="" onChangeText={() => {}} error="Enter a number" />);
    expect(styleOf('Enter a number')).toMatchObject({ fontFamily: 'sans', fontSize: 14, color: '#b73737' });
  });
});
