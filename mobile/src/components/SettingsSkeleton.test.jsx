import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => {
  const View = ({ children, style, accessibilityLabel, ...p }) =>
    React.createElement('div', { ...p, ...(accessibilityLabel ? { 'aria-label': accessibilityLabel } : {}) }, children);
  return {
    View,
    Animated: {
      Value: class { setValue() {} stopAnimation() {} interpolate() { return 0; } },
      View: ({ children, style, ...p }) => React.createElement('div', { ...p, 'data-bar': 'true' }, children),
      timing: () => ({ start() {}, stop() {} }),
      sequence: () => ({ start() {}, stop() {} }),
      loop: () => ({ start() {}, stop() {} }),
    },
  };
});

vi.mock('../theme/ThemeContext', () => ({ useTheme: () => ({ colors: { hover: '#eee' } }) }));

import { SettingsSkeleton } from './SettingsSkeleton';

describe('SettingsSkeleton', () => {
  it('draws a section eyebrow and five label · helper · value rows', () => {
    render(<SettingsSkeleton />);
    expect(screen.getByLabelText('Loading settings')).toBeTruthy();
    expect(document.querySelectorAll('[data-bar]').length).toBe(1 + 5 * 3);
  });
});
