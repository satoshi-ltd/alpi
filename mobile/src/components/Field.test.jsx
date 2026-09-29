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
    colors: { bgInput: '#eee', bgPane: '#fff', line2: '#ddd', ink: '#000', ink2: '#222', ink3: '#666', dangerText: '#b73737' },
    fonts: { mono: 'mono', sans: { regular: 'sans' } },
    fontSizes: { xs: 11, sm: 12, lg: 16 },
    mobile: { inputH: 44 },
  }),
}));

import { Field } from './Field';

describe('Field', () => {
  it('shows the error in place of the helper and tints the border', () => {
    const { container } = render(<Field label="USD per day" value="abc" onChangeText={() => {}} helper="a number" error="Enter a number, or leave it empty" />);
    expect(screen.getByRole('alert').textContent).toBe('Enter a number, or leave it empty');
    expect(screen.queryByText('a number')).toBeNull();
    const box = [...container.querySelectorAll('[data-style]')].find((n) => n.getAttribute('data-style').includes('borderColor'));
    expect(JSON.parse(box.getAttribute('data-style')).borderColor).toBe('#b73737');
  });
});
