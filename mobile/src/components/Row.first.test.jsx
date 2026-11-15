import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => {
  const View = ({ children, style, onLayout, ...p }) => React.createElement('div', { ...p, 'data-pt': [style].flat(Infinity).filter(Boolean).reduce((v, s) => s.paddingTop ?? v, undefined) }, children);
  const Text = ({ children, style, ...p }) => React.createElement('span', p, children);
  return { View, Text, Pressable: View, Platform: { OS: 'ios' } };
});
vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({ colors: { ink3: '#666' }, fonts: { sans: { medium: 'm' } }, fontSizes: { sm: 14 } }),
}));

import { SectionHeader } from './Row';

describe('SectionHeader first', () => {
  it('opens the first header 8 pt from the top and later ones 24 pt', () => {
    const first = render(<SectionHeader first>Overview</SectionHeader>);
    expect(first.container.firstChild.getAttribute('data-pt')).toBe('8');
    cleanup();
    const later = render(<SectionHeader>Overview</SectionHeader>);
    expect(later.container.firstChild.getAttribute('data-pt')).toBe('24');
  });
});
