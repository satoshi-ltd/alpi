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
  const TextInput = ({ style, placeholderTextColor }) => React.createElement('input', { 'data-placeholder-color': placeholderTextColor });
  const Modal = ({ children, visible, supportedOrientations }) =>
    visible
      ? React.createElement('div', { 'data-orientations': (supportedOrientations ?? []).join(',') }, children)
      : null;
  const ScrollView = ({ children, keyboardShouldPersistTaps }) => React.createElement('div', { 'data-scroll': 'true', 'data-persist': keyboardShouldPersistTaps }, children);
  const Keyboard = { addListener: () => ({ remove() {} }) };
  return { Keyboard, Modal, Pressable, ScrollView, Text, TextInput, View };
});

vi.mock('react-native-reanimated', () => ({
  default: {
    View: ({ children, pointerEvents, style }) =>
      React.createElement('div', { 'data-pe': pointerEvents ?? '', 'data-shadow': [style].flat().find((x) => x?.shadowColor)?.shadowColor ?? '' }, children),
  },
  Easing: { bezier: (...points) => `bezier(${points.join(',')})` },
  useAnimatedStyle: (fn) => fn(),
  useSharedValue: (initial) => React.useRef({ value: initial }).current,
  withTiming: (toValue, config) => {
    h.calls.push({ to: toValue, ...config });
    return toValue;
  },
}));

vi.mock('../lib/haptics', () => ({ selection: vi.fn(), warning: vi.fn(), tap: vi.fn(), success: vi.fn() }));
vi.mock('./Button', () => ({ Button: ({ title, disabled, variant }) => React.createElement('button', { type: 'button', disabled, 'data-variant': variant ?? 'primary' }, title) }));

vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { bgPane: '#fff', field: '#fafafa', ink: '#000', ink2: '#333', ink3: '#666', ink4: '#999', line2: '#eee', danger: '#f00' },
    fonts: { sans: { regular: 'Geist_400Regular', semibold: 'Geist_600SemiBold' }, mono: 'GeistMono_400Regular', monoMedium: 'GeistMono_500Medium' },
    fontSizes: { xs: 11, sm: 12, md: 14, xl: 18 },
    shadow: { dialog: { shadowColor: '#token-shadow', shadowRadius: 24 } },
  }),
}));

import { ConfirmDialog } from './ConfirmDialog';

describe('ConfirmDialog rotation', () => {
  it('lets the device rotate while the dialog is open', () => {
    const { container } = render(
      <ConfirmDialog open onClose={() => {}} title="Delete profile" body="This is permanent." expected="roma" />,
    );
    expect(container.querySelector('[data-orientations]').getAttribute('data-orientations')).toBe(
      'portrait,landscape-left,landscape-right',
    );
  });
});

describe('ConfirmDialog on a short screen', () => {
  it('scrolls its body and keeps taps working under the keyboard, so the buttons never clip', () => {
    const { container } = render(<ConfirmDialog open onClose={() => {}} title="Delete profile" body="Permanent." expected="roma" />);
    const scroll = container.querySelector('[data-scroll="true"]');
    expect(scroll).toBeTruthy();
    expect(scroll.getAttribute('data-persist')).toBe('handled');
    expect(scroll.textContent).toContain('Delete');
    expect(scroll.textContent).toContain('Cancel');
  });
});

describe('ConfirmDialog elevation', () => {
  it('casts the theme shadow, not a literal one', () => {
    const { container } = render(<ConfirmDialog open onClose={() => {}} title="Delete profile" body="Permanent." expected="roma" />);
    expect(container.querySelector('[data-shadow="#token-shadow"]')).toBeTruthy();
    expect(container.querySelector('[data-shadow="#000"]')).toBeNull();
  });
});

describe('ConfirmDialog dismissal contract', () => {
  it('keeps a worded Cancel — here the two buttons are real alternatives, not a dismissal', () => {
    render(<ConfirmDialog open onClose={() => {}} title="Delete profile" body="Permanent." expected="roma" />);
    expect(screen.getByText('Cancel')).toBeTruthy();
    expect(screen.getByText('Delete')).toBeTruthy();
  });

  it('is the one surface with no icon close — Cancel already carries the choice', () => {
    render(<ConfirmDialog open onClose={() => {}} title="Delete profile" body="Permanent." expected="roma" />);
    expect(screen.queryByLabelText('Close')).toBeNull();
  });
});

describe('ConfirmDialog exit', () => {
  it('fades out on the time-reverse of its entrance curve', () => {
    h.calls.length = 0;
    const { rerender } = render(
      <ConfirmDialog open onClose={() => {}} title="Delete profile" body="Permanent." expected="roma" />,
    );
    const entering = h.calls.map((c) => c.easing);
    h.calls.length = 0;
    rerender(<ConfirmDialog open={false} onClose={() => {}} title="Delete profile" body="Permanent." expected="roma" />);
    const leaving = h.calls.map((c) => c.easing);

    expect(entering).toContain('bezier(0.2,0.7,0.2,1)');
    expect(leaving).toContain('bezier(0.8,0,0.8,0.3)');
    expect(leaving).not.toContain('bezier(0.2,0.7,0.2,1)');
  });

  it('holds the copy it was showing while it animates out', () => {
    const { rerender } = render(
      <ConfirmDialog open onClose={() => {}} title="Forget casa" body="Removes the token." expected="casa" confirmLabel="Forget daemon" />,
    );
    rerender(<ConfirmDialog open={false} onClose={() => {}} title="Forget " body={null} expected="" confirmLabel="Forget daemon" />);

    expect(screen.getByText('Forget casa')).toBeTruthy();
    expect(screen.getByText('Removes the token.')).toBeTruthy();
    expect(screen.getByText('casa')).toBeTruthy();
  });

  it('stops taking taps the moment it starts leaving', () => {
    const { container, rerender } = render(
      <ConfirmDialog open onClose={() => {}} title="Delete profile" body="Permanent." expected="roma" />,
    );
    expect([...container.querySelectorAll('[data-pe]')].map((n) => n.getAttribute('data-pe'))).toContain('auto');
    rerender(<ConfirmDialog open={false} onClose={() => {}} title="Delete profile" body="Permanent." expected="roma" />);
    expect([...container.querySelectorAll('[data-pe]')].map((n) => n.getAttribute('data-pe'))).toContain('none');
  });

  it('offers a plain neutral confirm for reversible actions: no typing, no red', () => {
    render(<ConfirmDialog open onClose={() => {}} title="Promote to admin" body="ok" confirmLabel="Promote" tone="neutral" typed={false} onConfirm={() => {}} />);
    expect(screen.queryByText(/TO CONFIRM/)).toBeNull();
    const btn = screen.getByText('Promote');
    expect(btn.disabled).toBe(false);
    expect(btn.getAttribute('data-variant')).toBe('primary');
  });
});


describe('ConfirmDialog contract', () => {
  it('asks for a typed word only when one is expected, in the readable placeholder ink', () => {
    const { container, rerender } = render(<ConfirmDialog open onClose={() => {}} title="Delete" body="Gone." expected="roma" />);
    expect(container.querySelector('input').getAttribute('data-placeholder-color')).toBe('#666');
    expect(screen.getByText(/TO CONFIRM/)).toBeTruthy();
    rerender(<ConfirmDialog open onClose={() => {}} title="Discard changes?" body="Unsaved edits." confirmLabel="Discard" />);
    expect(container.querySelector('input')).toBeNull();
    expect(screen.queryByText(/TO CONFIRM/)).toBeNull();
  });

  it('gives the primary the danger variant and a worded cancel', () => {
    render(<ConfirmDialog open onClose={() => {}} title="Discard changes?" body="Unsaved." confirmLabel="Discard" cancelLabel="Keep editing" />);
    expect(screen.getByText('Discard').getAttribute('data-variant')).toBe('danger');
    expect(screen.getByText('Keep editing')).toBeTruthy();
  });

  it('shows a secondary third action only when one is given', () => {
    const { rerender } = render(<ConfirmDialog open onClose={() => {}} title="Changed elsewhere" body="x" typed={false} confirmLabel="Overwrite" alternateLabel="Reload (discard)" />);
    expect(screen.getByText('Reload (discard)').getAttribute('data-variant')).toBe('secondary');
    rerender(<ConfirmDialog open onClose={() => {}} title="Changed elsewhere" body="x" typed={false} confirmLabel="Overwrite" />);
    expect(screen.queryByText('Reload (discard)')).toBeNull();
  });
});
