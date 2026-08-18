import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({ calls: [] }));

vi.mock('react-native', () => {
  const View = ({ children, style, ...p }) => React.createElement('div', p, children);
  const Text = ({ children, style, ...p }) => React.createElement('span', p, children);
  const Pressable = ({ children, onPress, style, accessibilityLabel, ...p }) =>
    React.createElement('div', { onClick: onPress, 'aria-label': accessibilityLabel }, children);
  const TextInput = ({ style, ...p }) => React.createElement('input', {});
  const Modal = ({ children, visible, supportedOrientations }) =>
    visible
      ? React.createElement('div', { 'data-orientations': (supportedOrientations ?? []).join(',') }, children)
      : null;
  return { Modal, Pressable, Text, TextInput, View };
});

vi.mock('react-native-reanimated', () => ({
  default: {
    View: ({ children, pointerEvents }) =>
      React.createElement('div', { 'data-pe': pointerEvents ?? '' }, children),
  },
  Easing: { bezier: (...points) => `bezier(${points.join(',')})` },
  useAnimatedStyle: (fn) => fn(),
  useSharedValue: (initial) => React.useRef({ value: initial }).current,
  withTiming: (toValue, config) => {
    h.calls.push({ to: toValue, ...config });
    return toValue;
  },
}));

vi.mock('./Button', () => ({ Button: ({ title }) => React.createElement('button', { type: 'button' }, title) }));

vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { bgPane: '#fff', bgInput: '#fafafa', ink: '#000', ink2: '#333', ink3: '#666', ink4: '#999', line2: '#eee', danger: '#f00' },
    fonts: { sans: { regular: 'Inter_400Regular', semibold: 'Inter_600SemiBold' }, mono: 'JetBrainsMono_400Regular', monoMedium: 'JetBrainsMono_500Medium' },
    fontSizes: { xs: 11, sm: 12, md: 14, xl: 18 },
  }),
}));

import { TypedConfirm } from './TypedConfirm';

describe('TypedConfirm rotation', () => {
  it('lets the device rotate while the dialog is open', () => {
    const { container } = render(
      <TypedConfirm open onClose={() => {}} title="Delete profile" body="This is permanent." expected="roma" />,
    );
    expect(container.querySelector('[data-orientations]').getAttribute('data-orientations')).toBe(
      'portrait,landscape-left,landscape-right',
    );
  });
});

describe('TypedConfirm dismissal contract', () => {
  it('keeps a worded Cancel — here the two buttons are real alternatives, not a dismissal', () => {
    render(<TypedConfirm open onClose={() => {}} title="Delete profile" body="Permanent." expected="roma" />);
    expect(screen.getByText('Cancel')).toBeTruthy();
    expect(screen.getByText('Delete')).toBeTruthy();
  });

  it('is the one surface with no icon close — Cancel already carries the choice', () => {
    render(<TypedConfirm open onClose={() => {}} title="Delete profile" body="Permanent." expected="roma" />);
    expect(screen.queryByLabelText('Close')).toBeNull();
  });
});

describe('TypedConfirm exit', () => {
  it('fades out on the time-reverse of its entrance curve', () => {
    h.calls.length = 0;
    const { rerender } = render(
      <TypedConfirm open onClose={() => {}} title="Delete profile" body="Permanent." expected="roma" />,
    );
    const entering = h.calls.map((c) => c.easing);
    h.calls.length = 0;
    rerender(<TypedConfirm open={false} onClose={() => {}} title="Delete profile" body="Permanent." expected="roma" />);
    const leaving = h.calls.map((c) => c.easing);

    expect(entering).toContain('bezier(0.2,0.7,0.2,1)');
    expect(leaving).toContain('bezier(0.8,0,0.8,0.3)');
    expect(leaving).not.toContain('bezier(0.2,0.7,0.2,1)');
  });

  it('holds the copy it was showing while it animates out', () => {
    const { rerender } = render(
      <TypedConfirm open onClose={() => {}} title="Forget casa" body="Removes the token." expected="casa" confirmLabel="Forget daemon" />,
    );
    rerender(<TypedConfirm open={false} onClose={() => {}} title="Forget " body={null} expected="" confirmLabel="Forget daemon" />);

    expect(screen.getByText('Forget casa')).toBeTruthy();
    expect(screen.getByText('Removes the token.')).toBeTruthy();
    expect(screen.getByText('casa')).toBeTruthy();
  });

  it('stops taking taps the moment it starts leaving', () => {
    const { container, rerender } = render(
      <TypedConfirm open onClose={() => {}} title="Delete profile" body="Permanent." expected="roma" />,
    );
    expect([...container.querySelectorAll('[data-pe]')].map((n) => n.getAttribute('data-pe'))).toContain('auto');
    rerender(<TypedConfirm open={false} onClose={() => {}} title="Delete profile" body="Permanent." expected="roma" />);
    expect([...container.querySelectorAll('[data-pe]')].map((n) => n.getAttribute('data-pe'))).toContain('none');
  });
});
