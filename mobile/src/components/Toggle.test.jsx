import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => ({
  Switch: ({ value, onValueChange, disabled, accessibilityLabel, trackColor }) =>
    React.createElement('button', {
      type: 'button',
      role: 'switch',
      'aria-checked': value ? 'true' : 'false',
      'aria-label': accessibilityLabel,
      disabled,
      'data-track-on': trackColor?.true,
      onClick: () => onValueChange?.(!value),
    }),
}));

vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({ colors: { line2: '#ddd', accent: '#c90', bgPane: '#fff' } }),
}));

import { Toggle } from './Toggle';

describe('Toggle', () => {
  it('reports the next value and shows it at once, before the prop catches up', () => {
    const onChange = vi.fn();
    render(<Toggle on={false} label="Paused" onChange={onChange} />);
    const sw = screen.getByLabelText('Paused');
    expect(sw.getAttribute('aria-checked')).toBe('false');
    fireEvent.click(sw);
    expect(onChange).toHaveBeenCalledWith(true);
    expect(sw.getAttribute('aria-checked')).toBe('true');
  });

  it('follows the prop when the daemon answers differently', () => {
    const { rerender } = render(<Toggle on={false} label="Paused" onChange={() => {}} />);
    fireEvent.click(screen.getByLabelText('Paused'));
    rerender(<Toggle on={false} label="Paused" onChange={() => {}} />);
    expect(screen.getByLabelText('Paused').getAttribute('aria-checked')).toBe('true');
    rerender(<Toggle on={true} label="Paused" onChange={() => {}} />);
    expect(screen.getByLabelText('Paused').getAttribute('aria-checked')).toBe('true');
    rerender(<Toggle on={false} label="Paused" onChange={() => {}} />);
    expect(screen.getByLabelText('Paused').getAttribute('aria-checked')).toBe('false');
  });

  it('ignores taps while disabled and tints the on state with the given colour', () => {
    const onChange = vi.fn();
    render(<Toggle on label="Sandbox network" disabled color="#3d7ea6" onChange={onChange} />);
    const sw = screen.getByLabelText('Sandbox network');
    expect(sw.getAttribute('disabled')).not.toBeNull();
    fireEvent.click(sw);
    expect(onChange).not.toHaveBeenCalled();
    expect(sw.getAttribute('data-track-on')).toBe('#3d7ea6');
  });
});
