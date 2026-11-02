import React from 'react';
import { cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

afterEach(cleanup);

vi.mock('react-native', () => {
  const flat = (style) => Object.assign({}, ...[typeof style === 'function' ? style({ pressed: false }) : style].flat(Infinity).filter(Boolean));
  const View = ({ children, style }) => React.createElement('div', { 'data-style': JSON.stringify(flat(style)) }, children);
  const Text = ({ children }) => React.createElement('span', {}, children);
  const Pressable = ({ children, onPress, style, accessibilityRole, accessibilityState, accessibilityLabel }) =>
    React.createElement(
      'button',
      {
        type: 'button',
        onClick: onPress,
        role: accessibilityRole,
        'aria-checked': accessibilityState ? String(!!accessibilityState.checked) : undefined,
        'aria-label': accessibilityLabel,
        'data-style': JSON.stringify(flat(style)),
      },
      children,
    );
  return { View, Text, Pressable, Platform: { OS: 'ios', select: (s) => s?.ios ?? s?.default } };
});
vi.mock('../../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { ink: '#141414', ink3: '#6b6b6b', ink4: '#b4b4b4', bgPane: '#ffffff', selected: '#eaeaea', line: '#eee', bgSide: '#f6f6f6' },
    fonts: { mono: 'mono', sans: { regular: 'sans' } },
    fontSizes: { xs: 11, sm: 13 },
  }),
}));
vi.mock('../../components/Icon', () => ({ Icon: ({ name }) => React.createElement('i', { 'data-icon': name }) }));

const { ScopeToggles, ALP_SCOPES } = await import('./ScopeToggles');
const { mobile } = await import('../../theme/tokens');

describe('ScopeToggles', () => {
  it('announces each scope as a checkbox with its state', () => {
    const { container } = render(<ScopeToggles value={new Set(['link.ping'])} onToggle={() => {}} />);
    const boxes = [...container.querySelectorAll('[role="checkbox"]')];
    expect(boxes.map((b) => b.getAttribute('aria-checked'))).toEqual(['true', 'false', 'false']);
    expect(boxes[1].getAttribute('aria-label')).toBe(`link.ask, ${ALP_SCOPES[1].desc}`);
  });

  it('gives every row at least the touch target', () => {
    const { container } = render(<ScopeToggles value={new Set()} onToggle={() => {}} />);
    for (const b of container.querySelectorAll('[role="checkbox"]')) {
      expect(JSON.parse(b.getAttribute('data-style')).minHeight).toBeGreaterThanOrEqual(mobile.tap);
    }
  });

  it('hands the tapped scope back', () => {
    const onToggle = vi.fn();
    const { container } = render(<ScopeToggles value={new Set()} onToggle={onToggle} />);
    fireEvent.click(container.querySelectorAll('[role="checkbox"]')[2]);
    expect(onToggle).toHaveBeenCalledWith('link.cancel');
  });

  it('serves both peer screens, so the scope list lives in one place', async () => {
    const { readFileSync } = await import('node:fs');
    const { join } = await import('node:path');
    for (const screen of ['new.jsx', 'accept.jsx']) {
      const src = readFileSync(join(import.meta.dirname, '../../../app/profile/[id]/peers', screen), 'utf8');
      expect(src).toMatch(/<ScopeToggles value=\{scopes\}/);
      expect(src).not.toMatch(/link\.ping', (label|desc)/);
    }
  });
});
